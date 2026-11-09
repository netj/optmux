# Clipboard and sessions

## Clipboard integration

optmux ships [tmux-yank](https://github.com/netj/tmux-yank) and sets `set-clipboard on` + `allow-passthrough on`, so yanking in copy-mode lands on your system clipboard. Locally that goes through `pbcopy`/`xclip`. **Over SSH, [OSC 52](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands) is the only mechanism** — the remote tmux emits an escape sequence and your local terminal writes it to the clipboard, with no relay, agent, or daemon in between.

### macOS Terminal.app has no OSC 52 support

Local copying still works, but **copying from a remote optmux session over SSH will not reach your pasteboard** — Terminal.app discards the escape sequence, and no tmux configuration can change that. optmux deliberately doesn't ship a clipboard relay to work around it; that means a socket on your laptop accepting arbitrary bytes into your pasteboard, to replace what modern terminals already do natively.

**Workaround:** turn off **View → Allow Mouse Reporting** (`⌘R`), or hold `Fn`, to hand the mouse back to Terminal and drag-select with its own selection, then `⌘C`. `⌘R` again returns the mouse to tmux. You get only what's on screen, and the selection cuts across split panes — zoom first with `prefix + z`.

**Better:** use a terminal that supports OSC 52 — [Ghostty](https://ghostty.org), [iTerm2](https://iterm2.com), [Warp](https://warp.dev), [kitty](https://sw.kovidgoyal.net/kitty/), [WezTerm](https://wezterm.org), or [Alacritty](https://alacritty.org). The tips screen (shown on first attach, or `C-M-h`) nags about this unless it can confirm your terminal, using the attached client's `TERM_PROGRAM` and terminal type — over SSH only the latter survives, so `xterm-ghostty` and friends are still recognized on remote hosts.

## Session persistence

optmux ships [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect):

- **`C-t C-s`** — save the current session (windows, panes, working directories)
- **`C-t C-r`** — restore the last saved session

Because each project has its own `.$NAME.optmux.d/tmux/resurrect/` folder (see [What optmux generates](usage.md#what-optmux-generates)), saves never mix between projects. Save project A, then project B — restoring either one brings back only its own layout.
