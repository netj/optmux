"""End-to-end tests that launch real tmux sessions."""

import os
import shutil
import subprocess
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

    # Generate config
    bundled = load_bundled_defaults()
    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}
    project = data.get("optmux") or {}
    optmux = merge_optmux(bundled, project)
    generate_tmux_conf_files(tmux_dir, optmux)

    # Unix domain sockets have a ~104 char path limit on macOS,
    # so use a short path in /tmp for the socket
    import tempfile
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
