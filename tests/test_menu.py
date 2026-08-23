import pytest

from optmux import menu


def test_render_context_star_expands_all_defaults_in_order():
    items = menu.render_context("session", ["*"])
    expected = " ".join(menu._chunk(d) for d in menu.DEFAULT_MENUS["session"])
    assert items == expected


def test_render_context_default_ref_by_bare_string():
    items = menu.render_context("session", ["Detach"])
    assert items == "'Detach' 'd' {detach-client}"


def test_render_context_default_ref_by_dict():
    items = menu.render_context("session", [{"default": "Detach"}])
    assert items == "'Detach' 'd' {detach-client}"


def test_render_context_retitle_default_item():
    items = menu.render_context("session", [{"default": "Detach", "title": "Bye"}])
    assert items == "'Bye' 'd' {detach-client}"


def test_render_context_remap_default_item():
    items = menu.render_context("session", [{"default": "Detach", "key": "q"}])
    assert items == "'Detach' 'q' {detach-client}"


def test_render_context_conditional_default_item_retitle_preserves_conditional():
    items = menu.render_context("pane", [{"default": "Horizontal Split", "title": "Split Right"}])
    assert items == "'#{?#{!:#{pane_floating_flag}},Split Right,}' 'h' {split-window -h}"


def test_render_context_separator():
    assert menu.render_context("session", ["separator"]) == "''"
    assert menu.render_context("session", [""]) == "''"


def test_render_context_unknown_default_name_warns_and_skips(capsys):
    items = menu.render_context("session", [{"default": "Nope"}], source="test.yaml")
    assert items == ""
    err = capsys.readouterr().err
    assert "unknown default item 'Nope'" in err


def test_render_context_custom_item_with_command_opens_new_window():
    items = menu.render_context("pane", [{"key": "w", "title": "New Window"}])
    assert items == "'New Window' 'w' { new-window -c '#{pane_current_path}' }"


def test_render_context_custom_item_with_shell_command():
    # command: shares the shortcuts vocabulary, so it gets the same on-error
    # remain_wrap heredoc a `command:` shortcut would (new_window defaults true).
    items = menu.render_context("pane", [{"key": "e", "title": "Edit", "command": "vim"}])
    assert items.startswith("'Edit' 'e' { new-window -c '#{pane_current_path}' '")
    assert "_script=$(cat <<" in items
    assert "$SHELL" in items and "-euc" in items
    assert items.endswith("}")


def test_render_context_custom_item_split_instead_of_window():
    # A split (not a new window) gets shortcuts' default auto-zoom too.
    items = menu.render_context(
        "pane", [{"key": "e", "title": "Edit", "command": "vim", "new_window": False}]
    )
    assert items == "'Edit' 'e' { split-window -v -c '#{pane_current_path}' 'vim' ; resize-pane -Z }"


def test_render_context_custom_item_raw_tmux():
    items = menu.render_context("pane", [{"key": "z", "title": "Zoom", "tmux": "resize-pane -Z"}])
    assert items == "'Zoom' 'z' { resize-pane -Z }"


def test_render_context_custom_item_missing_key_warns_and_skips(capsys):
    items = menu.render_context("pane", [{"title": "No Key"}], source="test.yaml")
    assert items == ""
    assert "needs a 'key'" in capsys.readouterr().err


def test_render_context_custom_item_escapes_single_quotes():
    items = menu.render_context("pane", [{"key": "e", "title": "it's", "command": "echo it's"}])
    assert "it'\\''s" in items


def test_generate_menu_conf_absent_context_untouched():
    conf = menu.generate_menu_conf({"pane": ["Kill"]})
    assert "MouseDown3Pane" in conf
    assert "MouseDown3Status" not in conf
    assert "MouseDown3StatusLeft" not in conf


def test_generate_menu_conf_empty_produces_nothing():
    assert menu.generate_menu_conf({}) == ""
    assert menu.generate_menu_conf(None) == ""


def test_generate_menu_conf_pane_binds_three_key_paths():
    conf = menu.generate_menu_conf({"pane": ["Kill"]})
    assert "bind -N 'Display pane menu' >" in conf
    assert "bind -n MouseDown3Pane" in conf
    assert "bind -n M-MouseDown3Pane" in conf


def test_generate_menu_conf_unknown_context_warns(capsys):
    menu.generate_menu_conf({"bogus": ["*"]}, source="test.yaml")
    assert "unrecognized context 'bogus'" in capsys.readouterr().err


@pytest.mark.parametrize("context", menu.CONTEXTS)
def test_default_menus_cover_every_context(context):
    assert menu.DEFAULT_MENUS[context]
