"""Tests for the tips screen script (tips.sh): OSC 52 terminal detection, structure, scrolling."""

import os
import subprocess
from importlib.resources import files as pkg_files

import pytest

from conftest import skip_no_tmux

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
    headings = ["Keyboard Shortcuts", "Bundled Tools", "Plugins", "Good to Know"]
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


def test_notes_list_tips_and_warnings(tmp_path):
    out = run_tips(tmp_path, TERM="xterm-256color")
    notes = out[out.index("Good to Know"):]
    assert "  (.) optmux env CMD..." in notes  # tips are quiet bullets
    assert "  [!] Could not confirm OSC 52 support" in notes  # warnings keep [!], after the tips
    assert notes.index("(.) optmux env") < notes.index("[!]")
    assert "Heads Up" not in out


def test_no_warnings_when_nothing_to_warn(tmp_path):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    (bin_dir / "fc-list").write_text("#!/bin/sh\necho 'Hack Nerd Font'\n")
    (bin_dir / "fc-list").chmod(0o755)
    out = run_tips(tmp_path, TERM="xterm-ghostty", PATH=f"{bin_dir}:/usr/bin:/bin")
    assert "[!]" not in out
    assert "Good to Know" in out


def test_title_oneliner_and_prefix_key_first(tmp_path):
    out = run_tips(tmp_path, TERM="xterm-256color")
    assert "New to tmux? https://github.com/tmux/tmux/wiki/Getting-Started" in out
    assert out.index("New to tmux?") < out.index("Keyboard Shortcuts")
    shortcuts = out[out.index("Keyboard Shortcuts"):]
    assert shortcuts.split("\n")[3].strip().startswith("TMUX Prefix key: Ctrl+T (C-t)")


def test_rule_before_footer(tmp_path):
    out = run_tips(tmp_path, TERM="xterm-256color")
    lines = out.rstrip("\n").split("\n")
    footer = next(i for i, l in enumerate(lines) if l.startswith("q/Enter: dismiss"))
    assert set(lines[footer - 1]) == {"─"}  # divider directly above the footer
    assert len(lines[footer - 1]) >= 20


@skip_no_tmux
def test_tall_screen_opens_in_tmux_copy_mode_at_the_top(tmp_path):
    """The tips window must not open scrolled to the bottom: it enters copy-mode at the top."""
    import time
    sock = f"optmux-tips-test-{os.getpid()}"
    tmux = ["tmux", "-L", sock, "-f", "/dev/null"]

    def tmux_out(*args):
        return subprocess.run([*tmux, *args], capture_output=True, text=True).stdout.strip()

    try:
        subprocess.run(
            [*tmux, "new-session", "-d", "-x", "100", "-y", "10",
             f"OPTMUX_DIR={tmp_path} TERM=screen-256color bash {TIPS_SH} --force; "
             f"echo $? > {tmp_path}/exit-status; sleep 30"],
            check=True,
        )
        state = ""
        for _ in range(50):  # wait for the script to print and enter copy-mode
            state = tmux_out("display-message", "-p", "#{pane_in_mode} #{scroll_position} #{history_size}")
            if state.startswith("1 "):
                break
            time.sleep(0.1)
        in_mode, position, history = state.split()
        assert in_mode == "1"
        assert position == history and int(history) > 0  # top of the scrollback
        assert "scroll" in tmux_out("show-options", "-wv", "window-status-current-format")
        # scrolling past the end leaves copy-mode, back at the footer prompt
        subprocess.run([*tmux, "send-keys", "-X", "-N", "500", "scroll-down"], check=True)
        time.sleep(0.5)
        assert tmux_out("display-message", "-p", "#{pane_in_mode}") == "0"
        assert "q/Enter: dismiss" in tmux_out("capture-pane", "-p")
        # dismissing exits cleanly (no unbound-variable error from the cleanup trap)
        subprocess.run([*tmux, "send-keys", "q"], check=True)
        for _ in range(50):
            if (tmp_path / "exit-status").exists():
                break
            time.sleep(0.1)
        assert (tmp_path / "exit-status").read_text().strip() == "0"
    finally:
        subprocess.run([*tmux, "kill-server"], capture_output=True)


def test_osc52_warning_follows_clipboard_tip_and_nerd_font_is_last(tmp_path):
    out = run_tips(tmp_path, TERM="xterm-256color")
    notes = out[out.index("Good to Know"):]
    assert notes.index("copy-mode yank") < notes.index("OSC 52 support") < notes.index("Nerd Font")
    between = notes[notes.index("copy-mode yank"):notes.index("OSC 52 support")]
    assert "Nerd Font" not in between and between.count("\n") == 1  # adjacent lines
