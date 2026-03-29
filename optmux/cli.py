import os
import shutil
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

    # seed tmux.conf from bundled default if not present
    tmux_conf = optmux_dir / "tmux.conf"
    if not tmux_conf.exists():
        bundled = files("optmux").joinpath("data/tmux.conf")
        shutil.copy2(bundled, tmux_conf)

    # also source any tmux.*.conf files from the optmux dir
    # (tmux -f only takes one file, but the bundled conf can source-file extras)

    os.environ["TMUX_PLUGIN_MANAGER_PATH"] = str(optmux_dir / "tmux-plugins")

    sock = str(optmux_dir / "tmux.sock")
    conf = str(tmux_conf)

    if len(sys.argv) > 1:
        os.execvp(
            "tmuxp",
            ["tmuxp", "load", "-S", sock, "-f", conf, tmuxp_yaml, *remaining_args],
        )
    else:
        os.execvp("tmux", ["tmux", "-S", sock, "-f", conf])
