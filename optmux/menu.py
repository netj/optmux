"""Compile optmux `menu:` YAML config into static tmux display-menu bindings.

tmux's built-in session/window/pane menus are C macros (DEFAULT_SESSION_MENU
etc. in key-bindings.c) with no API to edit them at runtime. Rather than
parsing and patching the live binding, optmux keeps a literal copy of each
default menu's items below and lets YAML redeclare the full menu -- default
items referenced by name, reordered/retitled/remapped, plus any custom
items -- which compiles to one static `bind` block per context. Items not
mentioned are dropped, so a bare "*" entry means "everything else, in
tmux's original order".

Source: https://github.com/tmux/tmux/blob/3.7b/key-bindings.c
(only session/window/pane menus exist as of 3.7b; re-sync this file's
DEFAULT_MENUS by hand when tmux changes its default menus, and extend
CONTEXTS if a future tmux adds move/move-resize/empty menus for real).
"""

import sys
from collections import namedtuple

from optmux import actions

DefaultItem = namedtuple("DefaultItem", "name title key command")

CONTEXTS = ("session", "window", "pane")


def _sep():
    return DefaultItem(None, "''", None, None)


def _item(name, title, key, command):
    return DefaultItem(name, title, key, command)


DEFAULT_MENUS = {
    "session": [
        _item("Next", "'Next'", "'n'", "{switch-client -n}"),
        _item("Previous", "'Previous'", "'p'", "{switch-client -p}"),
        _sep(),
        _item("Renumber", "'Renumber'", "'N'", "{move-window -r}"),
        _item(
            "Rename", "'Rename'", "'r'",
            """{command-prompt -I "#S" {rename-session -- '%%'}}""",
        ),
        _item("Detach", "'Detach'", "'d'", "{detach-client}"),
        _sep(),
        _item("New Session", "'New Session'", "'s'", "{new-session}"),
        _item("New Window", "'New Window'", "'w'", "{new-window}"),
    ],
    "window": [
        _item(
            "Swap Left",
            "'#{?#{>:#{session_windows},1},,-}Swap Left'", "'l'",
            "{swap-window -t:-1}",
        ),
        _item(
            "Swap Right",
            "'#{?#{>:#{session_windows},1},,-}Swap Right'", "'r'",
            "{swap-window -t:+1}",
        ),
        _item(
            "Swap Marked",
            "'#{?pane_marked_set,,-}Swap Marked'", "'s'", "{swap-window}",
        ),
        _sep(),
        _item("Kill", "'Kill'", "'X'", "{kill-window}"),
        _item("Respawn", "'Respawn'", "'R'", "{respawn-window -k}"),
        _item("Mark", "'#{?pane_marked,Unmark,Mark}'", "'m'", "{select-pane -m}"),
        _item(
            "Rename", "'Rename'", "'n'",
            """{command-prompt -FI "#W" {rename-window -t '#{window_id}' -- '%%'}}""",
        ),
        _sep(),
        _item("New After", "'New After'", "'w'", "{new-window -a}"),
        _item("New At End", "'New At End'", "'W'", "{new-window}"),
    ],
    "pane": [
        _item(
            "Go To Top",
            "'#{?#{m/r:(copy|view)-mode,#{pane_mode}},Go To Top,}'", "'<'",
            "{send -X history-top}",
        ),
        _item(
            "Go To Bottom",
            "'#{?#{m/r:(copy|view)-mode,#{pane_mode}},Go To Bottom,}'", "'>'",
            "{send -X history-bottom}",
        ),
        _sep(),
        _item(
            "Paste",
            "'#{?#{&&:#{buffer_size},#{!:#{pane_in_mode}}},"
            "Paste #[underscore]#{=/9/...:buffer_sample},}'",
            "'p'", "{paste-buffer}",
        ),
        _sep(),
        _item(
            "Search For",
            "'#{?mouse_word,Search For #[underscore]#{=/9/...:mouse_word},}'",
            "'C-r'",
            """{if -F '#{?#{m/r:(copy|view)-mode,#{pane_mode}},0,1}' """
            """'copy-mode -t='; send -Xt= search-backward -- "#{q:mouse_word}"}""",
        ),
        _item(
            "Type",
            "'#{?mouse_word,Type #[underscore]#{=/9/...:mouse_word},}'",
            "'C-y'",
            """{copy-mode -q; send-keys -l -- "#{q:mouse_word}"}""",
        ),
        _item(
            "Copy",
            "'#{?mouse_word,Copy #[underscore]#{=/9/...:mouse_word},}'",
            "'c'",
            """{copy-mode -q; set-buffer -- "#{q:mouse_word}"}""",
        ),
        _item(
            "Copy Line", "'#{?mouse_line,Copy Line,}'", "'l'",
            """{copy-mode -q; set-buffer -- "#{q:mouse_line}"}""",
        ),
        _sep(),
        _item(
            "Type Hyperlink",
            "'#{?mouse_hyperlink,Type #[underscore]#{=/9/...:mouse_hyperlink},}'",
            "'C-h'",
            """{copy-mode -q; send-keys -l -- "#{q:mouse_hyperlink}"}""",
        ),
        _item(
            "Copy Hyperlink",
            "'#{?mouse_hyperlink,Copy #[underscore]#{=/9/...:mouse_hyperlink},}'",
            "'h'",
            """{copy-mode -q; set-buffer -- "#{q:mouse_hyperlink}"}""",
        ),
        _sep(),
        _item(
            "Horizontal Split",
            "'#{?#{!:#{pane_floating_flag}},Horizontal Split,}'", "'h'",
            "{split-window -h}",
        ),
        _item(
            "Vertical Split",
            "'#{?#{!:#{pane_floating_flag}},Vertical Split,}'", "'v'",
            "{split-window -v}",
        ),
        _sep(),
        _item(
            "Swap Up",
            "'#{?#{&&:#{!:#{pane_floating_flag}},#{>:#{window_panes},1}},Swap Up,}'",
            "'u'", "{swap-pane -U}",
        ),
        _item(
            "Swap Down",
            "'#{?#{&&:#{!:#{pane_floating_flag}},#{>:#{window_panes},1}},Swap Down,}'",
            "'d'", "{swap-pane -D}",
        ),
        _item(
            "Swap Marked",
            "'#{?pane_marked_set,,-}Swap Marked'", "'s'", "{swap-pane}",
        ),
        _sep(),
        _item("Kill", "'Kill'", "'X'", "{kill-pane}"),
        _item("Respawn", "'Respawn'", "'R'", "{respawn-pane -k}"),
        _item("Mark", "'#{?pane_marked,Unmark,Mark}'", "'m'", "{select-pane -m}"),
        _item(
            "Zoom",
            "'#{?#{>:#{window_panes},1},,-}#{?window_zoomed_flag,Unzoom,Zoom}'",
            "'z'", "{resize-pane -Z}",
        ),
    ],
}


def _chunk(item):
    if item.key is None:
        return item.title  # separator: bare '' with no key/command
    return f"{item.title} {item.key} {item.command}"


def _apply_overrides(item, title=None, key=None):
    new_title = item.title
    if title is not None:
        if item.name in new_title:
            new_title = new_title.replace(item.name, title, 1)
        else:
            new_title = "'%s'" % actions.sq(title)
    new_key = "'%s'" % actions.sq(key) if key is not None else item.key
    return item._replace(title=new_title, key=new_key)


def _custom_item(entry, context):
    """Build a menu item from a custom (non-default-referencing) entry.

    Shares the shortcuts action vocabulary (command/tmux/send_keys/
    new_window/float_window/zoom/detached/remain) via actions.build_action_parts,
    so a menu item can do anything a shortcut can. Unlike shortcuts, a bare
    item with no action fields at all defaults to opening a new window.
    """
    key = entry.get("key")
    if not key:
        return None
    title = entry.get("title", key)
    label = "menu.%s item %r" % (context, title)
    if "tmux" in entry:
        command = "{ %s }" % entry["tmux"]
    else:
        opts = dict(entry)
        opts.setdefault("new_window", True)
        parts = actions.build_action_parts(opts, label)
        if parts is None:
            return None
        command = "{ %s }" % " ; ".join(parts)
    return "'%s' '%s' %s" % (actions.sq(title), actions.sq(key), command)


def render_context(context, entries, source="<menu>"):
    """Render one context's YAML entries into a tmux display-menu items string."""
    defaults = DEFAULT_MENUS[context]
    by_name = {d.name: d for d in defaults if d.name}
    used = set()
    chunks = []
    for entry in entries or []:
        if entry == "*":
            for d in defaults:
                if d.name is None or d.name not in used:
                    chunks.append(_chunk(d))
                    if d.name:
                        used.add(d.name)
            continue
        if entry in ("separator", ""):
            chunks.append("''")
            continue
        if isinstance(entry, str):
            entry = {"default": entry}
        if not isinstance(entry, dict):
            print(f"optmux: {source}: menu.{context}: unrecognized item {entry!r}", file=sys.stderr)
            continue
        if "default" in entry:
            name = entry["default"]
            item = by_name.get(name)
            if item is None:
                print(
                    f"optmux: {source}: menu.{context}: unknown default item {name!r} "
                    f"(available: {', '.join(sorted(by_name))})",
                    file=sys.stderr,
                )
                continue
            chunks.append(_chunk(_apply_overrides(item, entry.get("title"), entry.get("key"))))
            used.add(name)
            continue
        chunk = _custom_item(entry, context)
        if chunk is None:
            print(
                f"optmux: {source}: menu.{context}: item {entry!r} needs a 'key'",
                file=sys.stderr,
            )
            continue
        chunks.append(chunk)
    return " ".join(chunks)


def _session_lines(items):
    menu = "display-menu -t= -xM -yW -T '#[align=centre]#{session_name}' %s" % items
    return [
        "bind -n MouseDown3StatusLeft { %s }" % menu,
        "bind -n M-MouseDown3StatusLeft { %s }" % menu,
    ]


def _window_lines(items):
    title = "#[align=centre]#{window_index}:#{window_name}"
    prefix_menu = "display-menu -xW -yW -T '%s' %s" % (title, items)
    mouse_menu = "display-menu -t= -xW -yW -T '%s' %s" % (title, items)
    return [
        "bind -N 'Display window menu' < { %s }" % prefix_menu,
        "bind -n MouseDown3Status { %s }" % mouse_menu,
        "bind -n M-MouseDown3Status { %s }" % mouse_menu,
    ]


def _pane_lines(items):
    title = "#[align=centre]#{pane_index} (#{pane_id})"
    prefix_menu = "display-menu -xP -yP -T '%s' %s" % (title, items)
    mouse_menu = "display-menu -t= -xM -yM -T '%s' %s" % (title, items)
    click_passthrough_guard = (
        "if -Ft= '#{||:#{mouse_any_flag},#{&&:#{pane_in_mode},"
        "#{?#{m/r:(copy|view)-mode,#{pane_mode}},0,1}}}' "
        "{ select-pane -t=; send -M } "
    )
    return [
        "bind -N 'Display pane menu' > { %s }" % prefix_menu,
        "bind -n MouseDown3Pane { %s{ %s } }" % (click_passthrough_guard, mouse_menu),
        "bind -n M-MouseDown3Pane { %s }" % mouse_menu,
    ]


_BIND_LINE_BUILDERS = {
    "session": _session_lines,
    "window": _window_lines,
    "pane": _pane_lines,
}


def generate_menu_conf(menu_cfg, source="<menu>"):
    """Compile an optmux `menu:` config dict into tmux bind-key lines.

    Contexts absent from menu_cfg are left untouched (tmux's own default
    menu still applies).
    """
    menu_cfg = menu_cfg or {}
    for context in menu_cfg:
        if context not in CONTEXTS:
            print(
                f"optmux: {source}: menu: unrecognized context {context!r} "
                f"(allowed: {', '.join(CONTEXTS)})",
                file=sys.stderr,
            )

    lines = []
    for context in CONTEXTS:
        if context not in menu_cfg:
            continue
        items = render_context(context, menu_cfg[context], source)
        lines.extend(_BIND_LINE_BUILDERS[context](items))

    return "\n".join(lines) + ("\n" if lines else "")
