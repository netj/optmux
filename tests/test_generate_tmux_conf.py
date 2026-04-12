from pathlib import Path

from optmux.cli import generate_tmux_conf_files, load_bundled_defaults

GOLDEN_DIR = Path(__file__).parent / "golden"


def test_shortcuts_defaults(tmp_path, update_golden):
    """Golden-file test: bundled defaults produce expected shortcuts conf."""
    config = load_bundled_defaults()
    generate_tmux_conf_files(tmp_path, config)
    actual = (tmp_path / "tmux.optmux-shortcuts.conf").read_text()
    golden_path = GOLDEN_DIR / "shortcuts-defaults.conf"
    if update_golden:
        golden_path.write_text(actual)
    expected = golden_path.read_text()
    assert actual == expected


def test_stale_files_cleared(tmp_path):
    """Pre-existing tmux.optmux-*.conf files are deleted."""
    stale = tmp_path / "tmux.optmux-old.conf"
    stale.write_text("stale content")
    generate_tmux_conf_files(tmp_path, {})
    assert not stale.exists()


def test_empty_config(tmp_path):
    """Empty config produces no files."""
    generate_tmux_conf_files(tmp_path, {})
    assert list(tmp_path.glob("tmux.optmux-*.conf")) == []


def test_no_shortcuts_key(tmp_path):
    """Config with only tmux_config, no shortcuts."""
    config = {"tmux_config": {"mouse": "set -g mouse on\n"}}
    generate_tmux_conf_files(tmp_path, config)
    assert not (tmp_path / "tmux.optmux-shortcuts.conf").exists()
    assert (tmp_path / "tmux.optmux-extras.mouse.conf").read_text() == "set -g mouse on\n"


def test_tmux_config_extras(tmp_path, sample_optmux_config):
    """Extras conf files generated from tmux_config entries."""
    generate_tmux_conf_files(tmp_path, sample_optmux_config)
    extras = tmp_path / "tmux.optmux-extras.project-settings.conf"
    assert extras.exists()
    assert extras.read_text() == "set -g status-style bg=blue\n"


def test_shortcuts_with_various_types(tmp_path, sample_optmux_config):
    """Config with mixed shortcut types generates valid conf."""
    generate_tmux_conf_files(tmp_path, sample_optmux_config)
    content = (tmp_path / "tmux.optmux-shortcuts.conf").read_text()
    lines = content.strip().split("\n")
    assert len(lines) == 4
    # C-M-s: empty split with zoom
    assert lines[0].startswith("bind -n C-M-s split-window")
    assert "resize-pane -Z" in lines[0]
    # C-M-g: command string
    assert "'lazygit'" in lines[1]
    # C-M-e: new_window command
    assert "new-window" in lines[2]
    # E: send-keys without zoom
    assert lines[3].startswith("bind E")
    assert "send-keys" in lines[3]
    assert "resize-pane -Z" not in lines[3]
