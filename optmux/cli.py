import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import yaml

MANAGED_MARKER = "# optmux:managed\n"


def generate_tmux_conf_files(tmux_dir, yaml_path):
    """Generate tmux conf files from optmux YAML keys."""
    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}
    optmux = data.get("optmux") or {}

    managed_files = set()

    # optmux.shortcuts → tmux.shortcuts.conf
    shortcuts = optmux.get("shortcuts") or {}
    shortcuts_conf = tmux_dir / "tmux.shortcuts.conf"
    if shortcuts:
        lines = [MANAGED_MARKER]
        for key, command in shortcuts.items():
            lines.append(
                f'bind -n {key} split-window -v -c "#{{pane_current_path}}" {command} \\; resize-pane -Z\n'
            )
        shortcuts_conf.write_text("".join(lines))
        managed_files.add(shortcuts_conf)
    elif shortcuts_conf.exists() and shortcuts_conf.read_text().startswith(MANAGED_MARKER):
        shortcuts_conf.unlink()

    # optmux.tmux_config → tmux.{name}.conf for each entry
    tmux_config = optmux.get("tmux_config") or {}
    for conf_name, content in tmux_config.items():
        conf_file = tmux_dir / f"tmux.{conf_name}.conf"
        conf_file.write_text(MANAGED_MARKER + content)
        managed_files.add(conf_file)

    # clean up stale managed files from previous runs
    for conf_file in tmux_dir.glob("tmux.*.conf"):
        if conf_file not in managed_files:
            try:
                if conf_file.read_text().startswith(MANAGED_MARKER):
                    conf_file.unlink()
            except OSError:
                pass


def main():
    if len(sys.argv) > 1:
        # optmux NAME.optmux.yaml [TMUXP_ARGS...]
        tmuxp_yaml = sys.argv[1]
        remaining_args = sys.argv[2:]

        yaml_path = Path(tmuxp_yaml).resolve()
        yaml_dir = yaml_path.parent

        # strip .yaml, then .tmuxp, then .optmux suffixes
        name = yaml_path.stem
        for suffix in (".tmuxp", ".optmux", ".optmuxp"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]

        optmux_dir = yaml_dir / f".{name}.optmux.d"
    else:
        # optmux (no args) — just open tmux in cwd
        name = Path.cwd().name
        optmux_dir = Path.cwd() / ".optmux.d"

    tmux_dir = optmux_dir / "tmux"
    tmux_dir.mkdir(parents=True, exist_ok=True)

    # seed bundled files if not present
    bundled = files("optmux").joinpath("data")
    tmux_conf = tmux_dir / "tmux.conf"
    if not tmux_conf.exists():
        shutil.copy2(bundled / "tmux.conf", tmux_conf)
    setup_script = tmux_dir / "plugins-update.sh"
    if not setup_script.exists():
        shutil.copy2(bundled / "plugins-update.sh", setup_script)
        setup_script.chmod(0o755)

    # generate tmux conf files from optmux YAML
    if len(sys.argv) > 1:
        generate_tmux_conf_files(tmux_dir, yaml_path)

    os.environ["OPTMUX_DIR"] = str(optmux_dir)
    os.environ["OPTMUX_NAME"] = name
    os.environ["TMUX_PLUGIN_MANAGER_PATH"] = str(tmux_dir / "plugins")

    # bootstrap TPM (clone only); plugin install happens inside tmux via tmux.conf
    subprocess.run([str(setup_script)], check=True)

    sock = str(tmux_dir / "tmux.sock")
    conf = str(tmux_conf)

    if len(sys.argv) > 1:
        os.execvp(
            "tmuxp",
            ["tmuxp", "load", "-S", sock, "-f", conf, tmuxp_yaml, *remaining_args],
        )
    else:
        # attach to existing session on this socket, or create a new one
        has_session = subprocess.run(
            ["tmux", "-S", sock, "has-session"],
            capture_output=True,
        ).returncode == 0
        if has_session:
            os.execvp("tmux", ["tmux", "-S", sock, "attach-session"])
        else:
            os.execvp("tmux", ["tmux", "-S", sock, "-f", conf, "new-session", "-s", f"optmux {name}"])
