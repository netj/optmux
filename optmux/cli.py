import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import yaml


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
    use_window = opts.get("new_window", False)
    use_zoom = opts.get("zoom", True)
    open_cmd = "new-window" if use_window else "split-window -v"
    # build the tmux action
    if "send-keys" in opts:
        escaped = opts["send-keys"].replace("'", "'\\''")
        action = f"{open_cmd} -c '#{{pane_current_path}}' \\; send-keys '{escaped}' Enter"
    elif "command" in opts:
        escaped = opts["command"].replace("'", "'\\''")
        action = f"{open_cmd} -c '#{{pane_current_path}}' '{escaped}'"
    else:
        action = f"{open_cmd} -c '#{{pane_current_path}}'"
    if use_zoom and not use_window:
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


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv:
        # optmux NAME.optmux.yaml [TMUXP_ARGS...]
        tmuxp_yaml = argv[0]
        remaining_args = argv[1:]

        yaml_path = Path(tmuxp_yaml).resolve()
        yaml_dir = yaml_path.parent

        name = parse_project_name(tmuxp_yaml)

        optmux_dir = yaml_dir / f".{name}.optmux.d"
    else:
        # optmux (no args) — just open tmux in cwd
        name = Path.cwd().name
        optmux_dir = Path.cwd() / ".optmux.d"

    tmux_dir = optmux_dir / "tmux"
    tmux_dir.mkdir(parents=True, exist_ok=True)

    # seed bundled files if not present
    data_dir = files("optmux").joinpath("data")
    tmux_conf = tmux_dir / "tmux.conf"
    # make writable before overwriting (it's set read-only below)
    if tmux_conf.exists():
        tmux_conf.chmod(0o644)
    shutil.copy2(data_dir / "tmux.conf", tmux_conf)  # always regenerated; use tmux.*.conf for customizations
    tmux_conf.chmod(0o444)  # read-only to discourage direct edits
    setup_script = tmux_dir / "plugins-update.sh"
    if not setup_script.exists():
        shutil.copy2(data_dir / "plugins-update.sh", setup_script)
        setup_script.chmod(0o755)
    tips_script = tmux_dir / "tips.sh"
    if not tips_script.exists():
        shutil.copy2(data_dir / "tips.sh", tips_script)
        tips_script.chmod(0o755)

    # generate tmux conf files from optmux YAML merged with personal config
    bundled = load_bundled_defaults()
    personal = load_optmux_conf()
    if argv:
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        project = data.get("optmux") or {}
        optmux = merge_optmux(bundled, project, personal)
    else:
        optmux = merge_optmux(bundled, personal)
    generate_tmux_conf_files(tmux_dir, optmux)

    # ensure scripts from optmux's own venv (e.g., tmuxp) are on PATH
    venv_bin = str(Path(sys.executable).parent)
    os.environ["PATH"] = venv_bin + os.pathsep + os.environ.get("PATH", "")

    os.environ["OPTMUX_DIR"] = str(optmux_dir)
    os.environ["OPTMUX_NAME"] = name
    os.environ["TMUX_PLUGIN_MANAGER_PATH"] = str(tmux_dir / "plugins")

    # bootstrap TPM (clone only); plugin install happens inside tmux via tmux.conf
    subprocess.run([str(setup_script)], check=True)

    sock = str(tmux_dir / "tmux.sock")
    conf = str(tmux_conf)

    tmux = ["tmux", "-S", sock]

    # Handle nested tmux/optmux gracefully
    outer_tmux = os.environ.get("TMUX")
    if outer_tmux:
        outer_sock = outer_tmux.split(",")[0]  # $TMUX format: /path/to/socket,pid,index
        if os.path.realpath(outer_sock) == os.path.realpath(sock):
            print(f"optmux: already inside this session ({name})", file=sys.stderr)
            return
        print(f"optmux: nesting inside outer tmux session", file=sys.stderr)
        # unset so tmux allows nested attach with our isolated socket
        del os.environ["TMUX"]

    def create_optmux_window():
        """Create window 0 with tips + plugins-update panes."""
        subprocess.run([*tmux, "new-window", "-t", "0", "-n", "optmux", str(tips_script)], check=True)
        subprocess.run([*tmux, "split-window", "-t", "0", "-v", str(setup_script)], check=True)

    if argv:
        has_session = subprocess.run(
            [*tmux, "has-session"],
            capture_output=True,
        ).returncode == 0
        if has_session:
            os.execvp(tmux[0], [*tmux, "attach-session"])
        # Load detached so we can create the optmux window after tmuxp is done
        subprocess.run(
            ["tmuxp", "load", "--yes", "-d", "-S", sock, "-f", conf, tmuxp_yaml, *remaining_args],
            check=True,
        )
        create_optmux_window()
        os.execvp(tmux[0], [*tmux, "attach-session"])
    else:
        # attach to existing session on this socket, or create a new one
        has_session = subprocess.run(
            [*tmux, "has-session"],
            capture_output=True,
        ).returncode == 0
        if has_session:
            os.execvp(tmux[0], [*tmux, "attach-session"])
        else:
            subprocess.run([*tmux, "-f", conf, "new-session", "-d", "-s", f"optmux {name}"], check=True)
            create_optmux_window()
            os.execvp(tmux[0], [*tmux, "attach-session"])
