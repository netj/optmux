"""End-to-end tests that launch real tmux sessions."""

import fcntl
import os
import pty
import select
import shutil
import struct
import subprocess
import tempfile
import termios
import time
from pathlib import Path

import pytest
import yaml

from tests.conftest import skip_no_tmux

pytestmark = [pytest.mark.e2e, skip_no_tmux]


@pytest.fixture
def e2e_yaml(tmp_path):
    """Create a minimal optmux YAML for E2E testing."""
    content = {
        "session_name": "e2etest",
        "start_directory": str(tmp_path),
        "optmux": {
            "shortcuts": {
                "C-M-b": "echo e2e-test",
            },
        },
        "windows": [
            {"window_name": "shell", "panes": [""]},
        ],
    }
    p = tmp_path / "e2etest.optmux.yaml"
    p.write_text(yaml.dump(content))
    return p


@pytest.fixture
def tmux_env(e2e_yaml):
    """Run optmux setup (everything except attach) and return paths for inspection."""
    from optmux.cli import (
        generate_tmux_conf_files,
        load_bundled_defaults,
        load_optmux_conf,
        merge_optmux,
        parse_project_name,
    )

    yaml_path = e2e_yaml.resolve()
    yaml_dir = yaml_path.parent
    name = parse_project_name(str(e2e_yaml))

    optmux_dir = yaml_dir / f".{name}.optmux.d"
    tmux_dir = optmux_dir / "tmux"
    tmux_dir.mkdir(parents=True, exist_ok=True)

    # Seed bundled files
    from importlib.resources import files as pkg_files

    data_dir = pkg_files("optmux").joinpath("data")
    tmux_conf = tmux_dir / "tmux.conf"
    if tmux_conf.exists():
        tmux_conf.chmod(0o644)
    shutil.copy2(data_dir / "tmux.conf", tmux_conf)
    tmux_conf.chmod(0o444)

    setup_script = tmux_dir / "plugins-update.sh"
    if not setup_script.exists():
        shutil.copy2(data_dir / "plugins-update.sh", setup_script)
        setup_script.chmod(0o755)

    pane_menu_script = tmux_dir / "pane-menu.py"
    shutil.copy2(pkg_files("optmux").joinpath("pane_menu.py"), pane_menu_script)
    pane_menu_script.chmod(0o555)

    # Generate config
    bundled = load_bundled_defaults()
    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}
    project = data.get("optmux") or {}
    optmux = merge_optmux(bundled, project)
    generate_tmux_conf_files(tmux_dir, optmux)

    # Unix domain sockets have a ~104 char path limit on macOS,
    # so use a short path in /tmp for the socket
    sock_dir = tempfile.mkdtemp(prefix="optmux-e2e-")
    sock = os.path.join(sock_dir, "tmux.sock")
    conf = str(tmux_conf)
    tmux_cmd = ["tmux", "-S", sock]

    # Set env vars needed by tmux.conf
    env = os.environ.copy()
    env["OPTMUX_DIR"] = str(optmux_dir)
    env["OPTMUX_NAME"] = name
    env["TMUX_PLUGIN_MANAGER_PATH"] = str(tmux_dir / "plugins")
    # Remove TMUX to avoid "sessions should be nested" error
    env.pop("TMUX", None)

    yield {
        "sock": sock,
        "conf": conf,
        "tmux_cmd": tmux_cmd,
        "tmux_dir": tmux_dir,
        "optmux_dir": optmux_dir,
        "name": name,
        "yaml_path": yaml_path,
        "env": env,
    }

    # Cleanup: kill the tmux server on this socket, remove temp socket dir
    subprocess.run([*tmux_cmd, "kill-server"], capture_output=True, env=env)
    shutil.rmtree(sock_dir, ignore_errors=True)


def test_e2e_session_lifecycle(tmux_env):
    """Start a tmux session, verify it exists, then kill it."""
    env = tmux_env["env"]
    tmux = tmux_env["tmux_cmd"]
    conf = tmux_env["conf"]

    # Create a detached session
    result = subprocess.run(
        [*tmux, "-f", conf, "new-session", "-d", "-s", "e2etest"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"new-session failed: {result.stderr}"

    # Verify session exists
    result = subprocess.run(
        [*tmux, "has-session", "-t", "e2etest"],
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0

    # List sessions
    result = subprocess.run(
        [*tmux, "list-sessions"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "e2etest" in result.stdout


def test_e2e_shortcuts_bound(tmux_env):
    """Start a session and verify shortcuts are bound via list-keys."""
    env = tmux_env["env"]
    tmux = tmux_env["tmux_cmd"]
    conf = tmux_env["conf"]

    # Create session
    subprocess.run(
        [*tmux, "-f", conf, "new-session", "-d", "-s", "e2etest"],
        capture_output=True,
        env=env,
    )

    # Check key bindings
    result = subprocess.run(
        [*tmux, "list-keys"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    # Bundled default
    assert "C-M-s" in result.stdout
    # Project shortcut
    assert "C-M-b" in result.stdout


def test_e2e_pane_menu_preserves_tmux_default_and_reload_is_idempotent(tmux_env):
    """The live menu gains one item without copying or dropping tmux defaults."""
    from optmux.pane_menu import MENU_ITEM

    env = tmux_env["env"]
    tmux = tmux_env["tmux_cmd"]
    conf = tmux_env["conf"]

    subprocess.run(
        [*tmux, "-f", conf, "new-session", "-d", "-s", "e2etest"],
        check=True,
        capture_output=True,
        env=env,
    )

    control_dir = tempfile.mkdtemp(prefix="optmux-menu-control-")
    control_sock = os.path.join(control_dir, "tmux.sock")
    control = ["tmux", "-S", control_sock]
    subprocess.run(
        [*control, "-f", "/dev/null", "new-session", "-d", "-s", "control"],
        check=True,
        capture_output=True,
        env=env,
    )
    try:
        default_binding = subprocess.run(
            [*control, "list-keys", "-T", "root", "MouseDown3Pane"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        ).stdout.strip()
        binding = subprocess.run(
            [*tmux, "list-keys", "-T", "root", "MouseDown3Pane"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        ).stdout.strip()

        assert binding.count(MENU_ITEM) == 1
        assert binding.replace(f"{MENU_ITEM} ", "", 1) == default_binding

        subprocess.run(
            [*tmux, "source-file", conf],
            check=True,
            capture_output=True,
            env=env,
        )
        reloaded = subprocess.run(
            [*tmux, "list-keys", "-T", "root", "MouseDown3Pane"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        ).stdout.strip()
        assert reloaded == binding
    finally:
        subprocess.run([*control, "kill-server"], capture_output=True, env=env)
        shutil.rmtree(control_dir, ignore_errors=True)


def test_e2e_pane_menu_new_window_uses_clicked_pane_cwd(tmux_env, tmp_path):
    """A real right-click menu selection targets the clicked, inactive pane."""
    env = tmux_env["env"]
    tmux = tmux_env["tmux_cmd"]
    conf = tmux_env["conf"]
    active_dir = tmp_path / "active"
    clicked_dir = tmp_path / "clicked"
    active_dir.mkdir()
    clicked_dir.mkdir()

    subprocess.run(
        [
            *tmux,
            "-f",
            conf,
            "new-session",
            "-d",
            "-s",
            "e2etest",
            "-c",
            str(active_dir),
        ],
        check=True,
        capture_output=True,
        env=env,
    )
    active_pane = subprocess.run(
        [*tmux, "display-message", "-p", "#{pane_id}"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()
    clicked_pane = subprocess.run(
        [
            *tmux,
            "split-window",
            "-h",
            "-P",
            "-F",
            "#{pane_id}",
            "-c",
            str(clicked_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()
    subprocess.run(
        [*tmux, "select-pane", "-t", active_pane],
        check=True,
        capture_output=True,
        env=env,
    )

    panes = subprocess.run(
        [
            *tmux,
            "list-panes",
            "-F",
            "#{pane_id}\t#{pane_active}\t#{pane_left}\t#{pane_top}"
            "\t#{pane_width}\t#{pane_height}",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip().splitlines()
    pane_fields = {line.split("\t")[0]: line.split("\t") for line in panes}
    clicked = pane_fields[clicked_pane]
    assert clicked[1] == "0"
    mouse_x = int(clicked[2]) + int(clicked[4]) // 2 + 1
    mouse_y = int(clicked[3]) + int(clicked[5]) // 2 + 1

    master_fd, slave_fd = pty.openpty()
    fcntl.ioctl(
        slave_fd,
        termios.TIOCSWINSZ,
        struct.pack("HHHH", 24, 100, 0, 0),
    )
    client_env = env.copy()
    client_env["TERM"] = "xterm-256color"
    client = subprocess.Popen(
        [*tmux, "attach-session", "-t", "e2etest"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=client_env,
        start_new_session=True,
        close_fds=True,
    )
    os.close(slave_fd)
    os.set_blocking(master_fd, False)
    try:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            clients = subprocess.run(
                [*tmux, "list-clients", "-F", "#{client_tty}"],
                capture_output=True,
                text=True,
                env=env,
            )
            if clients.stdout.strip():
                break
            time.sleep(0.05)
        else:
            pytest.fail("tmux PTY client did not attach")

        # Drain the initial screen so the assertion below observes this menu open.
        time.sleep(0.1)
        while select.select([master_fd], [], [], 0)[0]:
            try:
                os.read(master_fd, 65536)
            except BlockingIOError:
                break

        # SGR mouse button 2 is a right-click. Coordinates are one-based.
        os.write(master_fd, f"\x1b[<2;{mouse_x};{mouse_y}M".encode())
        menu_output = b""
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and b"New Window" not in menu_output:
            if select.select([master_fd], [], [], 0.1)[0]:
                try:
                    menu_output += os.read(master_fd, 65536)
                except BlockingIOError:
                    pass
        assert b"New Window" in menu_output

        # Select the displayed menu item's accelerator, not its underlying command.
        os.write(master_fd, b"w")
        deadline = time.monotonic() + 3
        windows = []
        while time.monotonic() < deadline:
            output = subprocess.run(
                [
                    *tmux,
                    "list-windows",
                    "-F",
                    "#{window_active}\t#{pane_current_path}",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            ).stdout.strip()
            windows = [line.split("\t", 1) for line in output.splitlines() if line]
            if len(windows) == 2:
                break
            time.sleep(0.05)

        assert len(windows) == 2
        new_window = next(fields for fields in windows if fields[0] == "1")
        assert os.path.realpath(new_window[1]) == os.path.realpath(clicked_dir)
    finally:
        subprocess.run([*tmux, "kill-server"], capture_output=True, env=env)
        try:
            client.wait(timeout=3)
        except subprocess.TimeoutExpired:
            client.kill()
            client.wait()
        os.close(master_fd)


def test_e2e_generated_files(tmux_env):
    """Verify that generated config files exist and have expected content."""
    tmux_dir = tmux_env["tmux_dir"]

    shortcuts_conf = tmux_dir / "tmux.optmux-shortcuts.conf"
    assert shortcuts_conf.exists()
    content = shortcuts_conf.read_text()
    assert "C-M-b" in content
    assert "C-M-s" in content

    tmux_conf = tmux_dir / "tmux.conf"
    assert tmux_conf.exists()
    # tmux.conf should be read-only
    assert not os.access(tmux_conf, os.W_OK)


def test_e2e_reattach(tmux_env):
    """Starting a second session on the same socket reuses the existing one."""
    env = tmux_env["env"]
    tmux = tmux_env["tmux_cmd"]
    conf = tmux_env["conf"]

    # Create first session
    subprocess.run(
        [*tmux, "-f", conf, "new-session", "-d", "-s", "e2etest"],
        capture_output=True,
        env=env,
    )

    # Verify has-session succeeds (what optmux checks before deciding to attach)
    result = subprocess.run(
        [*tmux, "has-session"],
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0

    # List sessions — should be exactly one
    result = subprocess.run(
        [*tmux, "list-sessions"],
        capture_output=True,
        text=True,
        env=env,
    )
    lines = [l for l in result.stdout.strip().split("\n") if l]
    assert len(lines) == 1
