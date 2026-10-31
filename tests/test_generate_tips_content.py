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
    shortcuts = {"E": {"send_keys": "vim ."}}
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


def test_bundled_shortcuts_grouped_direct_then_prefix():
    shortcuts = {
        "C-t z": {"tip": "toggle zoom"},
        "C-M-g": {"tip": "lazygit"},
        "C-M-b": {"tip": "mine"},
    }
    result = generate_tips_content(shortcuts, bundled_keys={"C-t z", "C-M-g"})
    groups = [g.splitlines() for g in result.rstrip("\n").split("\n\n")]
    assert [len(g) for g in groups] == [1, 1]
    assert "C-M-g" in groups[0][0]  # bundled direct keys
    assert "C-t z" in groups[1][0]  # then prefix keys
    assert "C-M-b" not in result  # yours are listed separately


def test_custom_tips_are_the_non_bundled_shortcuts():
    from optmux.cli import generate_custom_tips_content
    shortcuts = {
        "C-t z": {"tip": "toggle zoom"},
        "C-M-b": {"tip": "mine"},
        "C-M-q": "gh browse .",
    }
    result = generate_custom_tips_content(shortcuts, bundled_keys={"C-t z"})
    assert "C-M-b" in result and "mine" in result
    assert "C-M-q" in result
    assert "toggle zoom" not in result
    assert generate_custom_tips_content({"C-t z": {"tip": "x"}}, bundled_keys={"C-t z"}) == ""


def test_bundled_reference_lists_window_chooser_and_text_picker_next_to_fingers():
    from optmux.cli import load_bundled_defaults
    shortcuts = load_bundled_defaults()["shortcuts"]
    keys = list(shortcuts)
    assert "list all windows" in shortcuts["C-t w"]["tip"]
    assert "pick" in shortcuts["X"]["tip"]
    assert keys.index("X") == keys.index("C-t F") + 1  # right after fingers


def test_multiline_tip_is_collapsed_to_one_line():
    shortcuts = {"C-M-g": {"tip": "Open lazygit and see\nthe diff of commits\n"}}
    assert generate_tips_content(shortcuts) == "  C-M-g    Open lazygit and see the diff of commits\n"


def test_bundled_c_m_g_opens_lazygit_on_the_branch_diff():
    from optmux.cli import load_bundled_defaults
    value = load_bundled_defaults()["shortcuts"]["C-M-g"]
    assert '"$OPTMUX_DIR/bin/optmux-env" lazygit --screen-mode normal branch' in value["command"]
    assert "send-keys Enter '*' Enter" in value["command"]
