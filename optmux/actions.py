"""Shared tmux-action compiler for optmux.yaml's `shortcuts:` and `menu:` items.

Both sections describe the same vocabulary -- run a shell command or
send_keys, optionally in a new window or floating pane, with zoom/detached/
remain tweaks -- so both compile through build_action_parts() into the same
list of tmux sub-commands. The caller decides how to join them: a shortcut's
bind line joins with ' \\; ' (tmux's separator outside a { } block); a menu
item is already inside '{ }' and joins with plain ' ; '.
"""

import sys


def sq(s):  # escape ' for single-quoted tmux string
    return s.replace("'", "'\\''")


def build_action_parts(opts, label):
    """Build the tmux command parts for an action opts dict.

    Supports: command, send_keys, new_window, float_window, zoom, detached,
    remain. `label` (e.g. "shortcut 'C-M-x'") names the entry in warnings.
    Returns None when the combination is invalid.
    """
    if "send_keys" in opts and "remain" in opts:
        print(
            f"optmux: ignoring {label}: 'remain' is incompatible with "
            "'send_keys' (the shell stays alive after the command — send_keys "
            "implicitly means remain: true; drop 'remain' to silence)",
            file=sys.stderr,
        )
        return None
    use_window = opts.get("new_window", False)
    use_float = opts.get("float_window", False)
    use_zoom = opts.get("zoom", True)
    detached = opts.get("detached", False)
    if use_float and use_window:
        print(
            f"optmux: {label}: 'float_window' and 'new_window' are mutually "
            "exclusive — using float_window",
            file=sys.stderr,
        )
        use_window = False
    if use_float and "send_keys" in opts:
        print(
            f"optmux: ignoring {label}: 'send_keys' is incompatible with "
            "'float_window' (no tmux target names a floating pane — it is appended "
            "past ':.+' and sits outside the layout that '{bottom}' & co. walk; use "
            "'command:' instead, or 'new_window: true')",
            file=sys.stderr,
        )
        return None
    is_split = not (use_window or use_float)

    # Enable remain_wrap for detached actions AND for new_window/float_window
    # ones (so they don't close before the user sees output/errors).
    remain = opts.get("remain", "on-error") if (detached or use_window or use_float) else False

    def remain_wrap(cmd):
        """Wrap the command so the pane/window can be held open after exit.
        - never:    run cmd directly; pane/window closes on any exit
        - on-error: run cmd via $SHELL -euc heredoc; on failure, pause with read for user
        - always:   same heredoc, but pause unconditionally
        Heredoc lets the command contain any quoting without escaping.
        """
        if remain is False or remain == "never":
            return cmd
        sep = ";" if (remain is True or remain == "always") else "||"
        # A detached pane/window pauses out of sight, so ring the terminal bell —
        # tmux flags the window in the status line (monitor-bell) to point at it.
        bel = "printf '\\a'; " if detached else ""
        pause = (
            'bash -c "%secho; echo; '
            "read -p '[optmux] Exit status $?. Press Return/Enter to dismiss...'\""
        ) % bel
        return (
            "_script=$(cat <<'EOC'\n"
            "%s\n"
            "EOC\n"
            ")\n"
            '"$SHELL" -euc "$_script" %s %s'
        ) % (cmd.rstrip(), sep, pause)

    def send_keys_parts(text, target=""):
        """One send-keys command per non-empty line — avoids embedded newlines that
        break tmux.conf's bind-directive parser when more args follow the quoted string."""
        target_flag = " -t %s" % target if target else ""
        lines = [l for l in text.splitlines() if l.strip()] or [text]
        return ["send-keys%s '%s' Enter" % (target_flag, sq(line)) for line in lines]

    detach_flag = " -d" if detached else ""
    if use_float:
        # A floating pane (tmux 3.7+) sits outside the window layout, so it neither
        # rearranges the layout nor drops the origin pane's zoom when it closes.
        open_cmd = "new-pane" + detach_flag
    elif use_window:
        open_cmd = "new-window" + detach_flag
    else:
        open_cmd = "split-window -v" + detach_flag
    # A detached split unzooms the window twice over: split-window unzooms as it
    # makes room, and tmux unzooms again when the pane dies. Capture the origin
    # pane's zoom (also true of a lone pane) so the split can restore it.
    preserve_zoom = is_split and detached and use_zoom

    def open_with(cmd_name):
        if opts.get("command"):
            return "%s -c '#{pane_current_path}' '%s'" % (cmd_name, sq(remain_wrap(opts["command"])))
        return "%s -c '#{pane_current_path}'" % cmd_name

    parts = []
    if preserve_zoom:
        parts.append(
            "set-option -F @_optmux_zoom "
            "'#{||:#{window_zoomed_flag},#{==:#{window_panes},1}}'"
        )
    if use_float:
        # tmux 3.7b: a floating pane created while the window is zoomed gets a
        # broken layout cell and segfaults the server whenever it later closes —
        # the zoom state at close time is irrelevant. Unzooming first cannot help
        # from within one command list, where new-pane still sees the window as
        # zoomed and quietly makes an ordinary split instead. So pick at press
        # time: while zoomed, fall back to a background window, which leaves the
        # zoom alone too. See TROUBLESHOOTING-tmux-floating-panes.md.
        parts.append(
            "if -F '#{window_zoomed_flag}' "
            "{ %s } { %s }" % (open_with("new-window" + detach_flag), open_with(open_cmd))
        )
    elif "send_keys" in opts:
        target = (":$" if use_window else ":.+") if detached else ""
        parts.append("%s -c '#{pane_current_path}'" % open_cmd)
        parts.extend(send_keys_parts(opts["send_keys"], target=target))
    else:
        parts.append(open_with(open_cmd))
    if preserve_zoom:
        parts.append("if -F '#{@_optmux_zoom}' 'resize-pane -Z'")
    elif is_split and use_zoom:
        parts.append("resize-pane -Z")
    return parts
