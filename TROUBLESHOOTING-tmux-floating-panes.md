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

### A floating pane closing in a zoomed window crashes the server

If the window is zoomed at the moment a floating pane closes, the tmux **server
segfaults** and every session on it is lost.

```
EXC_BAD_ACCESS (SIGSEGV)
  layout_destroy_cell ← layout_close_pane ← server_destroy_pane
```

Minimal reproduction — **use a scratch socket**, this kills the whole server:

```bash
tmux -f /dev/null -S /tmp/x.sock new-session -d 'sleep 600' \; split-window -d 'sleep 600' \; resize-pane -Z
tmux -S /tmp/x.sock new-pane -d 'date; sleep 2; date'
sleep 4; tmux -S /tmp/x.sock list-panes   # → no server running
```

Unzoomed windows are unaffected, and the floating pane is fine while it runs — only
its *closing* while zoomed is fatal. Since the zoomed case is exactly what
`float_window` is meant to fix, treat `float_window` as unsafe on 3.7b if you live in
zoomed windows, and prefer `new_window: true` until it is fixed.

### A focused floating pane silently becomes a split when the window is zoomed

`new-pane` *without* `-d` in a zoomed window creates an ordinary split pane
(`pane_floating_flag` is 0) and unzooms, instead of floating. Only `new-pane -d` —
what `detached: true` generates — reliably produces a floating pane in a zoomed
window. This is why `float_window` is most useful together with `detached`.

### `send-keys` cannot target a floating pane

optmux rejects `send-keys:` combined with `float_window:` and tells you so. No tmux
target names a floating pane: it is appended past `:.+`, and `{bottom}`, `{top}` and
friends only walk the layout, which a floating pane is not part of. Targets are not
format-expanded either, so `:.#{window_panes}` does not work. Use `command:` instead,
or `new_window: true` if you need `send-keys`.
