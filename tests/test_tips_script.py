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


# --- structure: markdown-like headings and sections --------------------------------

def stub_tools(tmp_path, **versions):
    """A bin dir with fake tools; `less` prints the given version for --version."""
    bin_dir = tmp_path / "stubs"
    bin_dir.mkdir(exist_ok=True)
    for name in ("wtcode", "lazygit", "delta", "fzf", "gh"):
        (bin_dir / name).write_text("#!/bin/sh\n")
        (bin_dir / name).chmod(0o755)
    less = bin_dir / "less"
    less.write_text(f'#!/bin/sh\necho "less {versions.get("less", 710)} (PCRE2 regular expressions)"\n')
    less.chmod(0o755)
    return bin_dir


def test_sections_in_order_with_underlined_headings(tmp_path):
    (tmp_path / "tmux").mkdir()
    (tmp_path / "tmux" / "tips-content.txt").write_text("  C-M-g  lazygit\n")
    (tmp_path / "tmux" / "tips-plugins.txt").write_text("  a/b  https://github.com/a/b\n")
    out = run_tips(tmp_path, TERM="xterm-256color")
    headings = ["Keyboard Shortcuts", "Bundled Tools", "Plugins", "Tips", "Heads Up"]
    positions = [out.index(f"\n{h}\n{'=' * len(h)}\n") for h in headings]
    assert positions == sorted(positions)  # shortcuts come first
    assert "\noptmux tips\n===========\n" in out
    assert out.index("optmux tips") < out.index("Keyboard Shortcuts")


def test_bundled_tools_flag_missing_with_brew_hint(tmp_path):
    out = run_tips(tmp_path, TERM="xterm-256color")  # PATH=/usr/bin:/bin: no tools
    assert "✗ wtcode" in out
    assert "(missing: brew install netj/tap/wtcode)" in out
    assert "(missing: brew install git-delta)" in out
    assert "for claude (or $WTCODE_CMD)" in out


def test_bundled_tools_detected_when_installed(tmp_path):
    bin_dir = stub_tools(tmp_path)
    out = run_tips(tmp_path, TERM="xterm-256color", PATH=f"{bin_dir}:/usr/bin:/bin")
    for name in ("wtcode", "lazygit", "delta", "less", "fzf", "gh"):
        assert f"✓ {name}" in out, name
    assert "missing" not in out


def test_old_less_flagged(tmp_path):
    bin_dir = stub_tools(tmp_path, less=487)
    out = run_tips(tmp_path, TERM="xterm-256color", PATH=f"{bin_dir}:/usr/bin:/bin")
    assert "✗ less" in out
    assert "too old for --mouse and links" in out


def test_heads_up_omitted_when_nothing_to_warn(tmp_path):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    (bin_dir / "fc-list").write_text("#!/bin/sh\necho 'Hack Nerd Font'\n")
    (bin_dir / "fc-list").chmod(0o755)
    out = run_tips(tmp_path, TERM="xterm-ghostty", PATH=f"{bin_dir}:/usr/bin:/bin")
    assert "Heads Up" not in out
