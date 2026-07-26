"""Tests for the OSC 52 terminal detection in optmux-tips.sh."""

import subprocess
from importlib.resources import files as pkg_files

import pytest

TIPS_SH = str(pkg_files("optmux").joinpath("data", "tips.sh"))

# env vars that would leak the real terminal into the test
CLEARED = {
    "TMUX": "",
    "TERM_PROGRAM": "",
    "TERM": "",
    "__CFBundleIdentifier": "",
}


def run_tips(tmp_path, **env):
    """Run tips.sh outside tmux with a synthetic environment, return stdout."""
    full_env = {"PATH": "/usr/bin:/bin", "OPTMUX_DIR": str(tmp_path), **CLEARED, **env}
    full_env = {k: v for k, v in full_env.items() if v}
    result = subprocess.run(
        ["bash", TIPS_SH, "--force"],
        input="q",
        env=full_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize(
    "env",
    [
        {"TERM_PROGRAM": "ghostty", "TERM": "xterm-ghostty"},
        {"TERM_PROGRAM": "iTerm.app", "TERM": "xterm-256color"},
        {"TERM_PROGRAM": "WezTerm"},
        {"TERM_PROGRAM": "WarpTerminal"},
        {"TERM": "xterm-kitty"},  # kitty sets no TERM_PROGRAM
        {"TERM": "alacritty"},
        {"TERM": "xterm-ghostty"},  # over SSH only TERM survives
    ],
)
def test_tip_hidden_for_known_osc52_terminals(tmp_path, env):
    assert "ghostty.org" not in run_tips(tmp_path, **env)


def test_tip_shown_for_terminal_app(tmp_path):
    out = run_tips(
        tmp_path,
        TERM_PROGRAM="Apple_Terminal",
        TERM="xterm-256color",
        __CFBundleIdentifier="com.apple.Terminal",
    )
    assert "Terminal.app has no OSC 52 support" in out
    assert "Allow Mouse Reporting" in out  # the native-selection workaround
    assert "ghostty.org" in out


def test_tip_shown_when_terminal_unknown(tmp_path):
    """Default is to warn — e.g. bare SSH, where nothing identifies the terminal."""
    out = run_tips(tmp_path, TERM="xterm-256color")
    assert "Could not confirm" in out
    assert "ghostty.org" in out
