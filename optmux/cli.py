import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path


def main():
    if len(sys.argv) > 1:
        # optmux WORKFLOW.optmuxp.yaml [TMUXP_ARGS...]
        tmuxp_yaml = sys.argv[1]
        remaining_args = sys.argv[2:]

        yaml_path = Path(tmuxp_yaml).resolve()
        yaml_dir = yaml_path.parent

        # strip .yaml, then .tmuxp, then .optmux suffixes
        workflow = yaml_path.stem
        for suffix in (".tmuxp", ".optmux", ".optmuxp"):
            if workflow.endswith(suffix):
                workflow = workflow[: -len(suffix)]

        optmux_dir = yaml_dir / f"{workflow}.optmux.d"
    else:
        # optmux (no args) — just open tmux in cwd
        optmux_dir = Path.cwd() / ".optmux.d"

    optmux_dir.mkdir(parents=True, exist_ok=True)

    # seed bundled files if not present
    bundled = files("optmux").joinpath("data")
    tmux_conf = optmux_dir / "tmux.conf"
    if not tmux_conf.exists():
        shutil.copy2(bundled / "tmux.conf", tmux_conf)
    setup_script = optmux_dir / "tmux-plugins-setup.sh"
    if not setup_script.exists():
        shutil.copy2(bundled / "tmux-plugins-setup.sh", setup_script)
        setup_script.chmod(0o755)

    os.environ["OPTMUX_DIR"] = str(optmux_dir)
    os.environ["OPTMUX_BASENAME"] = optmux_dir.name.removesuffix(".optmux.d")
    os.environ["TMUX_PLUGIN_MANAGER_PATH"] = str(optmux_dir / "tmux-plugins")

    # bootstrap/update tmux plugins before starting tmux
    subprocess.run([str(setup_script)], check=True)

    sock = str(optmux_dir / "tmux.sock")
    conf = str(tmux_conf)

    if len(sys.argv) > 1:
        os.execvp(
            "tmuxp",
            ["tmuxp", "load", "-S", sock, "-f", conf, tmuxp_yaml, *remaining_args],
        )
    else:
        os.execvp("tmux", ["tmux", "-S", sock, "-f", conf])
