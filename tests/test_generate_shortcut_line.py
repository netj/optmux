from optmux.cli import generate_shortcut_line


def test_ctrl_meta_uses_bind_n():
    line = generate_shortcut_line("C-M-s", "")
    assert line.startswith("bind -n C-M-s ")


def test_regular_key_uses_bind():
    line = generate_shortcut_line("E", "vim")
    assert line.startswith("bind E ")
    assert "bind -n" not in line


def test_command_string():
    line = generate_shortcut_line("C-M-g", "lazygit")
    assert "'lazygit'" in line
    assert "resize-pane -Z" in line


def test_command_dict():
    line = generate_shortcut_line("C-M-e", {"command": "vim"})
    assert "'vim'" in line
    assert "split-window -v" in line
    assert "resize-pane -Z" in line


def test_new_window():
    line = generate_shortcut_line("C-M-c", {"command": "wtcode", "new_window": True})
    assert "new-window" in line
    assert "split-window" not in line
    # new_window should NOT get resize-pane -Z
    assert "resize-pane -Z" not in line


def test_send_keys():
    line = generate_shortcut_line("E", {"send-keys": "vim ."})
    assert "send-keys 'vim .'" in line
    assert "Enter" in line


def test_zoom_false():
    line = generate_shortcut_line("E", {"send-keys": "vim", "zoom": False})
    assert "resize-pane -Z" not in line


def test_zoom_default_true():
    line = generate_shortcut_line("C-M-g", "lazygit")
    assert "resize-pane -Z" in line


def test_empty_string_split():
    line = generate_shortcut_line("C-M-s", "")
    assert "split-window -v" in line
    assert "#{pane_current_path}" in line
    assert "resize-pane -Z" in line


def test_single_quote_escaping():
    line = generate_shortcut_line("C-M-x", "echo 'hello'")
    assert "'echo '\\''hello'\\'''" in line


def test_invalid_value_type():
    assert generate_shortcut_line("C-M-x", 42) is None
