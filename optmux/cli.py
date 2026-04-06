import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path


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
    shutil.copy2(bundled / "tmux.conf", tmux_conf)  # always regenerated; use tmux.*.conf for customizations
    setup_script = tmux_dir / "plugins-update.sh"
    if not setup_script.exists():
        shutil.copy2(bundled / "plugins-update.sh", setup_script)
        setup_script.chmod(0o755)
    tips_script = tmux_dir / "tips.sh"
    if not tips_script.exists():
        shutil.copy2(bundled / "tips.sh", tips_script)
        tips_script.chmod(0o755)

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
