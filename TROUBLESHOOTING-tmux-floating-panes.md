# Floating panes (`float_window: true`)

tmux 3.7 added floating panes — panes that live outside the window layout, drawn on
top of it (`prefix + *`, or `new-pane`). optmux exposes them as `float_window: true`,
which is the cleanest fit for `detached: true` shortcuts: opening and closing a
floating pane neither rearranges the layout nor drops the window's zoom, unlike a
split pane.

```yaml
C-M-a:
  command: open -R .git
  detached: true
  float_window: true
```

Requires **tmux 3.7 or newer**. On older tmux the generated `new-pane` command does
not exist and the binding fails to load.

## Known problems in tmux 3.7b

These are upstream tmux bugs, not optmux behavior. They are expected to disappear as
tmux stabilizes floating panes; until then, this is what to expect.

### A float created in a zoomed window crashes the server when it closes

A floating pane created while the window is **zoomed** apparently never gets a proper
layout cell, and destroying it later segfaults the tmux **server**, taking every
session on it with it.

```
EXC_BAD_ACCESS (SIGSEGV)
  layout_destroy_cell ← layout_close_pane ← server_destroy_pane
```

What matters is the zoom state when the pane is **created**, not when it closes:

| created | closed | result |
|---|---|---|
| unzoomed | unzoomed | fine |
| unzoomed | zoomed (zoomed in meanwhile) | fine |
| zoomed | zoomed | **segfault** |
| zoomed | unzoomed (unzoomed in meanwhile) | **segfault** |

Minimal reproduction — **use a scratch socket**, this kills the whole server:

```bash
tmux -f /dev/null -S /tmp/x.sock new-session -d 'sleep 600' \; split-window -d 'sleep 600' \; resize-pane -Z
tmux -S /tmp/x.sock new-pane -d 'date; sleep 2; date'
sleep 4; tmux -S /tmp/x.sock list-panes   # → no server running
```

**optmux works around this**, so `float_window: true` is safe to use meanwhile: the
generated binding checks the zoom at press time and opens a background window instead
of a float while zoomed, which leaves the layout and zoom alone just as well.

```tmux
bind -n C-M-a if -F '#{window_zoomed_flag}' { new-window -d ... } { new-pane -d ... }
```

Unzooming first and re-zooming afterwards — the obvious fix — does not work from
inside one binding: tmux applies the unzoom only once the whole command list has run,
so `new-pane` still sees a zoomed window and quietly creates an ordinary split pane
instead of a float. `new-pane -dZ` does create a real float and keeps the zoom, but
crashes on close just the same.

### A focused floating pane silently becomes a split when the window is zoomed

`new-pane` *without* `-d` in a zoomed window creates an ordinary split pane
(`pane_floating_flag` is 0) and unzooms, instead of floating. Only `new-pane -d` —
what `detached: true` generates — reliably produces a floating pane in a zoomed
window. This is why `float_window` is most useful together with `detached`.

### `send-keys` cannot target a floating pane

optmux rejects `send_keys:` combined with `float_window:` and tells you so. No tmux
target names a floating pane: it is appended past `:.+`, and `{bottom}`, `{top}` and
friends only walk the layout, which a floating pane is not part of. Targets are not
format-expanded either, so `:.#{window_panes}` does not work. Use `command:` instead,
or `new_window: true` if you need `send_keys`.
