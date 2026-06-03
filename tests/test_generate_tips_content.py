from optmux.cli import generate_tips_content


def test_basic_tips():
    shortcuts = {
        "C-M-g": {"command": "lazygit", "tip": "lazygit"},
        "C-M-s": {"command": "", "tip": "shell in same dir"},
    }
    result = generate_tips_content(shortcuts)
    assert "C-M-g" in result
    assert "lazygit" in result
    assert "C-M-s" in result
    assert "shell in same dir" in result


def test_fallback_to_command():
    shortcuts = {"C-M-g": {"command": "lazygit"}}
    result = generate_tips_content(shortcuts)
    assert "lazygit" in result


def test_fallback_to_send_keys():
    shortcuts = {"E": {"send-keys": "vim ."}}
    result = generate_tips_content(shortcuts)
    assert "vim ." in result


def test_bare_string_value():
    shortcuts = {"C-M-g": "lazygit"}
    result = generate_tips_content(shortcuts)
    assert "lazygit" in result


def test_empty_string_no_tip():
    shortcuts = {"C-M-s": ""}
    result = generate_tips_content(shortcuts)
    assert result == ""


def test_tip_only_entry():
    shortcuts = {"C-t C-t": {"tip": "last window"}}
    result = generate_tips_content(shortcuts)
    assert "C-t C-t" in result
    assert "last window" in result


def test_prefix_added_for_simple_keys():
    shortcuts = {"z": {"tmux": "resize-pane -Z", "tip": "toggle zoom"}}
    result = generate_tips_content(shortcuts)
    assert "C-t z" in result


def test_no_prefix_for_c_m_keys():
    shortcuts = {"C-M-z": {"tmux": "resize-pane -Z", "tip": "toggle zoom"}}
    result = generate_tips_content(shortcuts)
    assert "C-M-z" in result
    assert "C-t C-M-z" not in result


def test_no_prefix_for_keys_with_spaces():
    shortcuts = {"C-t C-t": {"tip": "last window"}}
    result = generate_tips_content(shortcuts)
    assert "C-t C-t" in result
    # should NOT double the C-t prefix
    lines = result.strip().split("\n")
    assert not any("C-t C-t C-t" in line for line in lines)


def test_no_prefix_for_keys_with_slashes():
    shortcuts = {"C-t h/j/k/l": {"tip": "navigate panes"}}
    result = generate_tips_content(shortcuts)
    assert "C-t h/j/k/l" in result


def test_empty_shortcuts():
    assert generate_tips_content({}) == ""


def test_alignment():
    shortcuts = {
        "C-M-g": {"tip": "git-ui"},
        "C-t h/j/k/l": {"tip": "navigate"},
    }
    result = generate_tips_content(shortcuts)
    lines = result.rstrip("\n").split("\n")
    assert len(lines) == 2
    # both tip texts should start at the same column
    git_col = lines[0].index("git-ui")
    nav_col = lines[1].index("navigate")
    assert git_col == nav_col


def test_invalid_value_skipped():
    shortcuts = {"C-M-x": 42, "C-M-g": {"tip": "lazygit"}}
    result = generate_tips_content(shortcuts)
    assert "C-M-g" in result
    assert "C-M-x" not in result
