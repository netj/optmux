import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from importlib.resources import files
from pathlib import Path

import yaml

# macOS sockaddr_un.sun_path is 104 bytes (including NUL terminator)
_SOCK_PATH_LIMIT = 104


def _short_sock_path(tmux_dir: Path) -> str:
    """Return a socket path under the Unix sun_path limit.

    When the natural path (.optmux.d/tmux/tmux.sock) is too long,
    place the socket under a deterministic temp directory and leave
    a symlink at the original location for discoverability.
    """
    natural = tmux_dir / "tmux.sock"
    natural_str = str(natural)
    if len(natural_str) < _SOCK_PATH_LIMIT:
        return natural_str
    h = hashlib.sha256(natural_str.encode()).hexdigest()[:12]
    short_dir = Path(tempfile.gettempdir()) / f"optmux-{h}"
    short_dir.mkdir(parents=True, exist_ok=True)
    short_sock = str(short_dir / "tmux.sock")
    if tmux_dir.exists():
        if natural.is_symlink():
            natural.unlink()
        if not natural.exists():
            natural.symlink_to(short_sock)
    return short_sock


KNOWN_SUBCOMMANDS = {"start", "stop", "warp"}


def parse_project_name(yaml_path_str):
    """Extract project name from a YAML path by stripping known suffixes."""
    name = Path(yaml_path_str).stem
    for suffix in (".tmuxp", ".optmux", ".optmuxp"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


def load_bundled_defaults():
    """Load bundled optmux defaults from package data."""
    defaults_path = files("optmux").joinpath("data", "optmux-defaults.yaml")
    with open(str(defaults_path)) as f:
        data = yaml.safe_load(f) or {}
    return data.get("optmux") or {}


def load_optmux_conf(conf_path=None):
    """Load personal optmux config from ~/.optmux.yaml if it exists."""
    if conf_path is None:
        conf_path = Path.home() / ".optmux.yaml"
    if conf_path.exists():
        with open(conf_path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("optmux") or {}
    return {}


def merge_optmux(*layers):
    """Merge optmux config layers (later layers win)."""
    merged = {}
    for key in ("shortcuts", "tmux_config"):
        combined = {}
        for layer in layers:
            combined.update(layer.get(key) or {})
        if combined:
            merged[key] = combined
    return merged


def generate_shortcut_line(key, value):
    """Generate a single tmux bind line from a shortcut key and value.

    Returns the line string, or None if the value type is unsupported.
    """
    bind = "bind -n" if key.startswith("C-M-") else "bind"
    # normalize str to dict
    if isinstance(value, str):
        opts = {"command": value} if value else {}
    elif isinstance(value, dict):
        opts = value
    else:
        return None
    if "send-keys" in opts and "remain" in opts:
        print(
            f"optmux: ignoring shortcut {key!r}: 'remain' is incompatible with "
            "'send-keys' (the shell stays alive after the command — send-keys "
            "implicitly means remain: true; drop 'remain' to silence)",
            file=sys.stderr,
        )
        return None
    use_window = opts.get("new_window", False)
    use_zoom = opts.get("zoom", True)
    detached = opts.get("detached", False)

    remain = opts.get("remain", "on-error") if detached else False

    def sq(s):  # escape ' for single-quoted tmux string
        return s.replace("'", "'\\''")

    def remain_wrap(cmd):
        """Wrap user's command so the pane/window can be held open after exit.
        - never:    run cmd directly; pane/window closes on any exit
        - on-error: run cmd via $SHELL -euc heredoc; on failure, pause with read for user
        - always:   same heredoc, but pause unconditionally
        Heredoc lets the user's command contain any quoting without escaping.
        """
        if remain is False or remain == "never":
            return cmd
        sep = ";" if (remain is True or remain == "always") else "||"
        pause = (
            'bash -c "echo; echo; '
            "read -p '[optmux] Exit status $?. Press Return/Enter to dismiss...'\""
        )
        return (
            "_script=$(cat <<'EOC'\n"
            f"{cmd.rstrip()}\n"
            "EOC\n"
            ")\n"
            f'"$SHELL" -euc "$_script" {sep} {pause}'
        )

    def send_keys_parts(text, target=""):
        """One send-keys command per non-empty line — avoids embedded newlines that
        break tmux.conf's bind-directive parser when more args follow the quoted string."""
        target_flag = f" -t {target}" if target else ""
        lines = [l for l in text.splitlines() if l.strip()] or [text]
        return [f"send-keys{target_flag} '{sq(line)}' Enter" for line in lines]

    if detached and not use_window:
        # Detached pane: split with -d so focus never leaves origin. For zoom: capture
        # pre-split state in @_optmux_zoom and re-zoom after; treat a single-pane window
        # as zoomed (since it was effectively full-size).
        # send-keys: split empty shell pane, then send keys to the new pane via :.+
        # command:   run command as the pane's process with remain_wrap heredoc
        parts = []
        if use_zoom:
            parts.append(
                "set-option -F @_optmux_zoom "
                "'#{||:#{window_zoomed_flag},#{==:#{window_panes},1}}'"
            )
        if "send-keys" in opts:
            parts.append("split-window -v -d -c '#{pane_current_path}'")
            parts.extend(send_keys_parts(opts["send-keys"], target=":.+"))
        elif "command" in opts:
            parts.append(f"split-window -v -d -c '#{{pane_current_path}}' '{sq(remain_wrap(opts['command']))}'")
        else:
            parts.append("split-window -v -d -c '#{pane_current_path}'")
        if use_zoom:
            parts.append("if -F '#{@_optmux_zoom}' 'resize-pane -Z'")
        action = " \\; ".join(parts)
    else:
        detach_flag = " -d" if detached else ""
        open_cmd = f"new-window{detach_flag}" if use_window else f"split-window -v{detach_flag}"
        if "send-keys" in opts:
            target = ":$" if detached and use_window else ""  # last window in session
            parts = [f"{open_cmd} -c '#{{pane_current_path}}'"]
            parts.extend(send_keys_parts(opts["send-keys"], target=target))
            action = " \\; ".join(parts)
        elif "command" in opts:
            cmd = opts["command"]
            if detached and use_window:
                cmd = remain_wrap(cmd)
            action = f"{open_cmd} -c '#{{pane_current_path}}' '{sq(cmd)}'"
        else:
            action = f"{open_cmd} -c '#{{pane_current_path}}'"
        if use_zoom and not use_window and not detached:
            action += " \\; resize-pane -Z"
    return f"{bind} {key} {action}\n"


def generate_tmux_conf_files(tmux_dir, optmux):
    """Generate tmux conf files from merged optmux config."""
    # clear all managed files first to avoid stale configs
    for conf_file in tmux_dir.glob("tmux.optmux-*.conf"):
        conf_file.unlink()

    # optmux.shortcuts → tmux.optmux-shortcuts.conf
    shortcuts = optmux.get("shortcuts") or {}
    if shortcuts:
        lines = []
        for key, value in shortcuts.items():
            line = generate_shortcut_line(key, value)
            if line is not None:
                lines.append(line)
        (tmux_dir / "tmux.optmux-shortcuts.conf").write_text("".join(lines))

    # optmux.tmux_config → tmux.optmux-extras.{name}.conf for each entry
    tmux_config = optmux.get("tmux_config") or {}
    for conf_name, content in tmux_config.items():
        (tmux_dir / f"tmux.optmux-extras.{conf_name}.conf").write_text(content)


def resolve_paths(yaml_file):
    """Compute session name, optmux directory, and tmux paths from a YAML filename or CWD."""
    if yaml_file:
        yaml_path = Path(yaml_file).resolve()
        name = parse_project_name(yaml_file)
        optmux_dir = yaml_path.parent / f".{name}.optmux.d"
        # Read session_name from YAML for tmux session targeting
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            session_name = data.get("session_name", name)
        except OSError:
            session_name = name
    else:
        yaml_path = None
        name = Path.cwd().name
        # Strip leading dots from session name - tmux has issues parsing them in targets
        session_name = name.lstrip('.')
        optmux_dir = Path.cwd() / ".optmux.d"
    tmux_dir = optmux_dir / "tmux"
    sock = str(tmux_dir / "tmux.sock")
    return {
        "name": name,
        "session_name": session_name,
        "yaml_path": yaml_path,
        "yaml_file": yaml_file,
        "optmux_dir": optmux_dir,
        "tmux_dir": tmux_dir,
        "sock": sock,
        "tmux_cmd": ["tmux", "-S", sock],
    }


def setup_optmux_env(resolved):
    """Create optmux directories, seed config files, and set environment variables."""
    tmux_dir = resolved["tmux_dir"]
    optmux_dir = resolved["optmux_dir"]
    name = resolved["name"]
    yaml_path = resolved["yaml_path"]

    tmux_dir.mkdir(parents=True, exist_ok=True)

    gitignore = optmux_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")

    data_dir = files("optmux").joinpath("data")
    tmux_conf = tmux_dir / "tmux.conf"
    if tmux_conf.exists():
        tmux_conf.chmod(0o644)
    shutil.copy2(data_dir / "tmux.conf", tmux_conf)
    tmux_conf.chmod(0o444)

    setup_script = tmux_dir / "plugins-update.sh"
    if not setup_script.exists():
        shutil.copy2(data_dir / "plugins-update.sh", setup_script)
        setup_script.chmod(0o755)

    tips_script = tmux_dir / "tips.sh"
    if not tips_script.exists():
        shutil.copy2(data_dir / "tips.sh", tips_script)
        tips_script.chmod(0o755)

    bundled = load_bundled_defaults()
    personal = load_optmux_conf()
    if yaml_path:
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        project = data.get("optmux") or {}
        optmux = merge_optmux(bundled, project, personal)
    else:
        optmux = merge_optmux(bundled, personal)
    generate_tmux_conf_files(tmux_dir, optmux)

    venv_bin = str(Path(sys.executable).parent)
    os.environ["PATH"] = venv_bin + os.pathsep + os.environ.get("PATH", "")
    os.environ["OPTMUX_DIR"] = str(optmux_dir)
    os.environ["OPTMUX_NAME"] = name
    os.environ["TMUX_PLUGIN_MANAGER_PATH"] = str(tmux_dir / "plugins")

    sock = _short_sock_path(tmux_dir)
    resolved["sock"] = sock
    resolved["tmux_cmd"] = ["tmux", "-S", sock]

    return {
        "conf": str(tmux_conf),
        "setup_script": setup_script,
        "tips_script": tips_script,
    }


def create_optmux_window(tmux_cmd, tips_script, setup_script, session_name):
    """Create window 0 with tips + plugins-update panes."""
    # Create window 0 (base-index is 1, so window 0 doesn't auto-exist)
    target = f"{session_name}:0"
    subprocess.run([*tmux_cmd, "new-window", "-t", target, "-n", "optmux", str(tips_script)], check=True)
    subprocess.run([*tmux_cmd, "split-window", "-t", target, "-v", str(setup_script)], check=True)


def cmd_stop(resolved):
    """Stop (kill) an optmux session."""
    # Setup environment to get correct socket path
    setup_optmux_env(resolved)
    tmux = resolved["tmux_cmd"]
    session_name = resolved["session_name"]

    has_session = subprocess.run(
        [*tmux, "has-session", "-t", session_name],
        capture_output=True,
    ).returncode == 0

    if not has_session:
        print(f"optmux: session '{session_name}' is not running", file=sys.stderr)
        sys.exit(1)

    subprocess.run([*tmux, "kill-session", "-t", session_name], check=True)
    print(f"optmux: killed session '{session_name}'")


def cmd_start(resolved, remaining_args):
    """Start or attach to an optmux session."""
    tmux = resolved["tmux_cmd"]
    sock = resolved["sock"]
    name = resolved["name"]
    session_name = resolved["session_name"]
    yaml_path = resolved["yaml_path"]
    yaml_file = resolved["yaml_file"]

    outer_tmux = os.environ.get("TMUX")
    if outer_tmux:
        outer_sock = outer_tmux.split(",")[0]
        if os.path.realpath(outer_sock) == os.path.realpath(sock):
            # Same server: switch to the main session (e.g., from a warp session)
            os.execvp(tmux[0], [*tmux, "switch-client", "-t", session_name])
            return
        print("optmux: nesting inside outer tmux session", file=sys.stderr)
        del os.environ["TMUX"]

    env = setup_optmux_env(resolved)
    conf = env["conf"]
    tmux = resolved["tmux_cmd"]
    sock = resolved["sock"]

    subprocess.run([str(env["setup_script"])], check=True)

    if yaml_path:
        has_session = subprocess.run(
            [*tmux, "has-session", "-t", session_name],
            capture_output=True,
        ).returncode == 0
        if has_session:
            os.execvp(tmux[0], [*tmux, "attach-session", "-t", session_name])
        subprocess.run(
            ["tmuxp", "load", "--yes", "-d", "-S", sock, "-f", conf,
             yaml_file, *remaining_args],
            check=True,
        )
        create_optmux_window(tmux, env["tips_script"], env["setup_script"], session_name)
        os.execvp(tmux[0], [*tmux, "attach-session", "-t", session_name])
    else:
        has_session = subprocess.run(
            [*tmux, "has-session", "-t", session_name],
            capture_output=True,
        ).returncode == 0
        if has_session:
            os.execvp(tmux[0], [*tmux, "attach-session", "-t", session_name])
        else:
            subprocess.run([*tmux, "-f", conf, "new-session", "-d", "-s", session_name], check=True)
            create_optmux_window(tmux, env["tips_script"], env["setup_script"], session_name)
            os.execvp(tmux[0], [*tmux, "attach-session", "-t", session_name])


def _patch_warp_status(tmux, warp_name):
    """Patch global status formats to show short name for warp sessions (no-op for main)."""
    warp_fmt = "#{s|//.*|⚡warp|:session_name}"
    for option in ("status-left", "status-right", "set-titles-string"):
        result = subprocess.run(
            [*tmux, "show", "-gv", option],
            capture_output=True, text=True,
        )
        raw = result.stdout.strip()
        if result.returncode != 0 or warp_fmt in raw:
            continue
        if "#{session_name}" in raw:
            patched = raw.replace("#{session_name}", warp_fmt)
        elif "#S" in raw:
            patched = raw.replace("#S", warp_fmt)
        else:
            continue
        subprocess.run([*tmux, "set", "-g", option, patched], capture_output=True)


def _attach_or_switch(tmux_cmd, session_name, sock, outer_tmux, *, warp=False):
    """Attach to a session, or switch-client if already inside the same server."""
    if warp:
        _patch_warp_status(tmux_cmd, session_name)
    if outer_tmux:
        outer_sock = outer_tmux.split(",")[0]
        if os.path.realpath(outer_sock) == os.path.realpath(sock):
            os.execvp(tmux_cmd[0], [*tmux_cmd, "switch-client", "-t", session_name])
            return
    os.execvp(tmux_cmd[0], [*tmux_cmd, "attach-session", "-t", session_name])


def cmd_warp(resolved, args, original_cwd=None):
    """Create or update a warp session linking windows whose panes match a workdir."""
    tmux = resolved["tmux_cmd"]
    sock = resolved["sock"]
    main_session = resolved["session_name"]

    if original_cwd is None:
        original_cwd = os.getcwd()

    warp_name = None
    workdir = None
    if len(args) >= 1:
        workdir = args[0]
    if len(args) >= 2:
        warp_name = args[1]
    if len(args) > 2:
        print("optmux warp: too many arguments", file=sys.stderr)
        print("usage: optmux [DIR | YAML] warp [WORKDIR] [NAME]", file=sys.stderr)
        sys.exit(1)

    # Resolve workdir relative to original cwd (before any chdir from DIR arg)
    workdir = os.path.realpath(os.path.join(original_cwd, workdir or "."))
    if warp_name is None:
        warp_name = f"{main_session}//{Path(workdir).name}"

    outer_tmux = os.environ.get("TMUX")
    if outer_tmux:
        outer_sock = outer_tmux.split(",")[0]
        if os.path.realpath(outer_sock) != os.path.realpath(sock):
            print("optmux: nesting inside outer tmux session", file=sys.stderr)
            del os.environ["TMUX"]

    if subprocess.run(
        [*tmux, "has-session", "-t", main_session], capture_output=True,
    ).returncode != 0:
        yaml_hint = f" {resolved['yaml_file']}" if resolved["yaml_file"] else ""
        print(f"optmux warp: session '{main_session}' is not running", file=sys.stderr)
        print(f"optmux warp: start it first with: optmux{yaml_hint}", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        [*tmux, "list-panes", "-s", "-t", main_session,
         "-F", "#{window_id}\t#{window_index}\t#{pane_current_path}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"optmux warp: failed to list panes: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    matching_windows = {}  # window_id -> window_index
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        win_id, win_idx, pane_path = line.split("\t", 2)
        if os.path.realpath(pane_path) == workdir:
            matching_windows[win_id] = win_idx

    if not matching_windows:
        print(f"optmux warp: no windows in '{main_session}' have panes in {workdir}", file=sys.stderr)
        sys.exit(1)

    warp_exists = subprocess.run(
        [*tmux, "has-session", "-t", warp_name], capture_output=True,
    ).returncode == 0

    already_linked = set()
    if warp_exists:
        result = subprocess.run(
            [*tmux, "list-panes", "-s", "-t", warp_name, "-F", "#{window_id}"],
            capture_output=True, text=True,
        )
        already_linked = set(result.stdout.strip().splitlines())

    windows_to_link = {wid: idx for wid, idx in matching_windows.items()
                       if wid not in already_linked}

    if not windows_to_link and warp_exists:
        _attach_or_switch(tmux, warp_name, sock, outer_tmux, warp=True)
        return

    initial_window_id = None
    if not warp_exists:
        result = subprocess.run(
            [*tmux, "new-session", "-d", "-s", warp_name, "-P", "-F", "#{window_id}"],
            capture_output=True, text=True, check=True,
        )
        initial_window_id = result.stdout.strip()

    for win_id, win_idx in windows_to_link.items():
        subprocess.run(
            [*tmux, "link-window", "-s", f"{main_session}:{win_idx}", "-t", warp_name],
            check=True,
        )

    if initial_window_id and initial_window_id not in matching_windows:
        subprocess.run(
            [*tmux, "kill-window", "-t", initial_window_id],
            capture_output=True,
        )

    _attach_or_switch(tmux, warp_name, sock, outer_tmux, warp=True)


USAGE = """\
usage: optmux [DIR | YAML] [start | stop | warp [WORKDIR] [NAME]]

  optmux DIR                          open tmux in DIR (use . for cwd)
  optmux YAML                         load a tmuxp session from YAML
  optmux YAML start                   same as above (explicit)
  optmux [DIR | YAML] stop            kill the tmux session
  optmux [DIR | YAML] warp [WORKDIR] [NAME]
                                      create a warp session linking windows
                                      whose panes match WORKDIR (default: cwd)
"""


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print(USAGE, file=sys.stderr)
        sys.exit(0)

    argv = list(argv)
    original_cwd = os.getcwd()

    # First positional is either a directory (plain tmux) or a YAML file (tmuxp session)
    yaml_file = None
    if argv and argv[0] not in KNOWN_SUBCOMMANDS:
        candidate = argv[0]
        if Path(candidate).is_dir():
            os.chdir(argv.pop(0))
        elif Path(candidate).suffix in ('.yaml', '.yml'):
            yaml_file = argv.pop(0)

    if argv and argv[0] in KNOWN_SUBCOMMANDS:
        subcommand = argv.pop(0)
    elif argv and not argv[0].startswith('-'):
        print(f"optmux: unknown argument: {argv[0]}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)
    else:
        subcommand = "start"

    resolved = resolve_paths(yaml_file)

    if subcommand == "start":
        cmd_start(resolved, argv)
    elif subcommand == "stop":
        cmd_stop(resolved)
    elif subcommand == "warp":
        cmd_warp(resolved, argv, original_cwd)
