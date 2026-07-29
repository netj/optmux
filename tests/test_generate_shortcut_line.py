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
    # new_window SHOULD get remain_wrap (heredoc + pause on error)
    assert "_script=$(cat <<" in line
    assert "$SHELL" in line and "-euc" in line
    assert "||" in line and "read -p" in line


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


def test_detached_split():
    # default remain: on-error → wrap cmd in heredoc; pause with read on failure.
    # split with -d (focus stays on origin, no last-pane needed, no flicker).
    # zoom captured in @_optmux_zoom (also true when window has only one pane).
    line = generate_shortcut_line("C-M-b", {"command": "htop", "detached": True})
    assert "split-window -v -d" in line
    assert "_script=$(cat <<" in line
    assert "$SHELL" in line and "-euc" in line
    assert "||" in line and "read -p" in line
    assert "last-pane" not in line
    assert "set-option -F @_optmux_zoom" in line
    assert "#{window_panes},1" in line
    assert "if -F '#{@_optmux_zoom}' 'resize-pane -Z'" in line


def test_detached_pause_rings_bell():
    # the pause happens out of sight (behind the restored zoom, or in a background
    # window) → BEL flags it in the status line; a clean exit closes silently
    line = generate_shortcut_line("C-M-b", {"command": "htop", "detached": True})
    # single quotes are escaped for the surrounding tmux '...' argument
    assert """|| bash -c "printf '\\''\\a'\\''; echo;""" in line


def test_non_detached_window_pause_does_not_ring_bell():
    # the window is in front of the user already
    line = generate_shortcut_line("C-M-c", {"command": "wtcode", "new_window": True})
    assert "read -p" in line
    assert "\\a" not in line


def test_detached_split_no_zoom():
    line = generate_shortcut_line("C-M-b", {"command": "htop", "detached": True, "zoom": False})
    assert "split-window -v -d" in line
    assert "_script=$(cat <<" in line
    assert "last-pane" not in line
    assert "@_optmux_zoom" not in line
    assert "resize-pane -Z" not in line


def test_detached_split_send_keys():
    # send-keys + detached pane: real send-keys to the newly created pane (:.+)
    line = generate_shortcut_line("C-M-b", {"send-keys": "make test", "detached": True})
    assert "split-window -v -d" in line
    assert "send-keys -t :.+ 'make test' Enter" in line
    assert "_script=$(cat <<" not in line  # no command-style heredoc wrap
    assert "last-pane" not in line


def test_detached_split_always_close():
    line = generate_shortcut_line("C-M-b", {"command": "htop", "detached": True, "remain": False})
    assert "split-window -v -d" in line
    assert "_script=$(cat <<" not in line
    assert "read -p" not in line
    assert "last-pane" not in line


def test_detached_split_always_open():
    # remain: true → always pause (semicolon, not || )
    line = generate_shortcut_line("C-M-b", {"command": "htop", "detached": True, "remain": True})
    assert "split-window -v -d" in line
    assert "_script=$(cat <<" in line
    assert '"$_script" ;' in line
    assert "read -p" in line
    assert "last-pane" not in line


def test_float_window():
    # a floating pane is outside the layout: no split, no zoom bookkeeping at all.
    # while zoomed it falls back to a background window, since tmux 3.7b segfaults
    # when a float created in a zoomed window later closes
    line = generate_shortcut_line("C-M-b", {"command": "htop", "float_window": True, "detached": True})
    assert line.startswith("bind -n C-M-b if -F '#{window_zoomed_flag}' {")
    assert "new-pane -d -c '#{pane_current_path}'" in line
    assert "new-window -d -c '#{pane_current_path}'" in line
    assert "split-window" not in line
    assert "_script=$(cat <<" in line
    assert "@_optmux_zoom" not in line
    assert "resize-pane -Z" not in line


def test_float_window_not_detached():
    # focus moves to the float; still held open on error since it is a new pane
    line = generate_shortcut_line("C-M-b", {"command": "htop", "float_window": True})
    assert "{ new-pane -c '#{pane_current_path}'" in line
    assert "{ new-window -c '#{pane_current_path}'" in line
    assert "new-pane -d" not in line and "new-window -d" not in line
    assert "read -p" in line
    assert "\\a" not in line  # only detached shortcuts ring


def test_float_window_fallback_runs_the_same_command():
    # both branches must carry the user's command, not just the float one
    line = generate_shortcut_line("C-M-b", {"command": "htop", "float_window": True, "detached": True})
    assert line.count("htop") == 2
    zoomed_branch, float_branch = line.split("{ new-pane")[0], line.split("{ new-pane")[1]
    assert "htop" in zoomed_branch and "htop" in float_branch


def test_float_window_send_keys_rejected(capsys):
    # no target names a floating pane, and creating one focused (so untargeted
    # send-keys would reach it) silently degrades to a split in a zoomed window
    result = generate_shortcut_line("C-M-b", {"send-keys": "make test", "float_window": True})
    assert result is None
    err = capsys.readouterr().err
    assert "send-keys" in err and "float_window" in err and "C-M-b" in err


def test_float_window_wins_over_new_window(capsys):
    line = generate_shortcut_line("C-M-b", {"command": "htop", "float_window": True, "new_window": True})
    assert "new-pane" in line  # floats, rather than opening a window outright
    assert line.startswith("bind -n C-M-b if -F '#{window_zoomed_flag}' {")
    err = capsys.readouterr().err
    assert "mutually exclusive" in err and "C-M-b" in err


def test_detached_window():
    line = generate_shortcut_line("C-M-b", {"command": "htop", "new_window": True, "detached": True})
    assert "new-window -d" in line
    assert "_script=$(cat <<" in line
    assert "||" in line and "read -p" in line
    assert "split-window" not in line
    assert "resize-pane -Z" not in line


def test_detached_window_always_open():
    line = generate_shortcut_line("C-M-m", {"command": "uvx marimo edit", "new_window": True, "detached": True, "remain": True})
    assert "new-window -d" in line
    assert "_script=$(cat <<" in line
    assert '"$_script" ;' in line
    assert "send-keys" not in line


def test_detached_window_send_keys():
    # send-keys + detached + new_window: real send-keys targeted at :{end}
    line = generate_shortcut_line("C-M-d", {"send-keys": "echo hi", "new_window": True, "detached": True})
    assert "new-window -d" in line
    assert "send-keys -t :$ 'echo hi' Enter" in line
    assert "_script=$(cat <<" not in line


def test_invalid_value_type():
    assert generate_shortcut_line("C-M-x", 42) is None


def test_send_keys_with_remain_rejected(capsys):
    # send-keys implicitly keeps the shell alive; combining with remain is rejected
    result = generate_shortcut_line("C-M-x", {"send-keys": "cmd", "remain": True, "detached": True})
    assert result is None
    err = capsys.readouterr().err
    assert "send-keys" in err and "remain" in err and "C-M-x" in err


def test_tmux_raw_action():
    line = generate_shortcut_line("C-M-z", {"tmux": "resize-pane -Z"})
    assert line == "bind -n C-M-z resize-pane -Z\n"


def test_tmux_raw_action_regular_key():
    line = generate_shortcut_line("z", {"tmux": "resize-pane -Z"})
    assert line == "bind z resize-pane -Z\n"


def test_tip_only_returns_none():
    assert generate_shortcut_line("C-t C-t", {"tip": "last window"}) is None


def test_tip_field_ignored_in_bind():
    line = generate_shortcut_line("C-M-g", {"command": "lazygit", "tip": "git UI"})
    assert "'lazygit'" in line
    assert "tip" not in line


def test_empty_command_with_tip():
    line = generate_shortcut_line("C-M-s", {"command": "", "tip": "shell"})
    assert "split-window -v" in line
    assert "resize-pane -Z" in line
    assert "''" not in line
