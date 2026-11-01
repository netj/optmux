"""optmux-split-fits: does a plain vertical split still leave room? (real tmux, private socket)"""

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "optmux" / "data" / "bin" / "optmux-split-fits"
pytestmark = pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux not installed")


@pytest.fixture
def tmux():
    sock = "optmux-test-" + uuid.uuid4().hex[:8]

    def run(*args):
        return subprocess.run(["tmux", "-f", "/dev/null", "-L", sock, *args],
                              capture_output=True, text=True)

    run("new-session", "-d", "-x", "80", "-y", "24", "sleep 60")
    yield run
    run("kill-server")


def fits(tmux):
    # run-shell, not subprocess: it points the script's own `tmux` at this server
    out = tmux("run-shell", f'"{SCRIPT}" #{{pane_id}} && echo fits || echo nofit').stdout
    return out.strip() == "fits"


def test_roomy_pane_fits(tmux):
    assert fits(tmux)


def test_short_pane_does_not_fit(tmux):
    tmux("split-window", "-d", "-b", "-l", "19", "sleep 60")  # active pane left with 3 rows
    assert not fits(tmux)


def test_zoomed_pane_is_judged_by_its_unzoomed_height(tmux):
    tmux("split-window", "-d", "-b", "-l", "19", "sleep 60")
    tmux("resize-pane", "-Z")  # reports 24 rows while zoomed, really 3
    assert not fits(tmux)
