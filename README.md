# optmux

<p align="center">
  <img src="https://raw.githubusercontent.com/netj/optmux/main/optmux.svg" width="192" alt="optmux logo">
</p>

Optimal, opinionated, batteries-included TMUX that's neat and easy for any project.

A [tmuxp](https://tmuxp.git-pull.com) wrapper that creates per-project tmux config directories with [TPM](https://github.com/tmux-plugins/tpm) and plugins pre-configured.

## Quick Start

```bash
# run optmux anywhere (installs on first use via uv)
uvx optmux .

# strongly recommended: install wtcode + lazygit for the full experience
brew install netj/tap/optmux
```

`brew install netj/tap/optmux` pulls in [wtcode](https://github.com/netj/wtcode) and [lazygit](https://github.com/jesseduffield/lazygit) as dependencies.

Try the included example:

```bash
git clone https://github.com/netj/optmux.git && cd optmux
./example.optmux.yaml
```

On first run, optmux will:

1. Create `.example.optmux.d/tmux/` next to the YAML file
2. Seed a default `tmux.conf` with TPM and plugins
3. Install TPM and all plugins (visible in window 0)
4. Launch tmuxp with an isolated tmux server

## Usage

### With a tmuxp YAML file

Supports `.optmux.yaml`, `.tmuxp.yaml`, and `.optmuxp.yaml` extensions:

```bash
optmux myproject.optmux.yaml
optmux myproject.tmuxp.yaml
```

### With a directory

```bash
optmux .
optmux /path/to/project
```

Opens plain `tmux` using `.optmux.d/` in that directory (`.` for the current directory) — useful for a quick, isolated tmux session with the bundled config.

### Without arguments

```bash
optmux
```

Prints usage and exits.

### As a shebang

Write a [tmuxp YAML config](https://tmuxp.git-pull.com/configuration/) with the optmux shebang line and make it executable:

```yaml
#!/usr/bin/env -S uvx optmux
session_name: myproject
windows:
- window_name: editor
  panes:
  - vim .
- window_name: shell
  panes:
  - ""
```

```bash
chmod +x myproject.optmux.yaml
./myproject.optmux.yaml
```

### Stopping a session

```bash
optmux myproject.optmux.yaml stop
optmux . stop
```

Kills the tmux session tied to that YAML file or directory.

### Warp sessions

```bash
optmux [DIR | YAML] warp [WORKDIR] [NAME]
```

Creates (or updates) a secondary session — named `<main-session>//<workdir-name>` unless you pass `NAME` — that links in only the windows from the main session whose panes are running in `WORKDIR` (defaults to the current directory). Handy when a project spans multiple git worktrees: run `optmux warp` from inside a worktree to get a session showing just that worktree's windows. Windows are linked, not copied, so they stay in sync with the main session.

### Raw tmux access

```bash
optmux [DIR | YAML] tmux ARGS...
```

Runs `tmux ARGS...` directly against this project's isolated tmux server — no tmuxp bootstrapping, no session creation. Useful for one-off inspection or scripting without hand-rolling the `-S <sock>` path yourself, e.g. `optmux . tmux ls` or `optmux . tmux kill-server`.

## Example tmuxp YAML

Here's the included [`example.optmux.yaml`](example.optmux.yaml) showing shortcuts, tmux config, and window layout:

```yaml
#!/usr/bin/env -S uvx optmux
session_name: example
start_directory: .

optmux:
  shortcuts:
    C-M-b: gh browse .
    C-M-e:
      command: ${VISUAL:-${EDITOR:-vim}} README.md  # exec directly (default for str, no latency)
      new_window: true                              # in a new-window
    E:
      send_keys: ${VISUAL:-${EDITOR:-vim}} .        # send_keys (command is run in a new shell)
      zoom: false                                   # do not zoom (defaults to zoom when split-window)
  tmux_config:
    project-settings: |
      set -g status-style bg=blue

windows:
- window_name: editor
  panes:
  - vim .
- window_name: shell
  panes:
  - ""
- window_name: logs
  panes:
  - tail -f /var/log/system.log
```

## Config directory

Each project gets its own `.$NAME.optmux.d/` directory:

| Path | Purpose |
|---|---|
| `tmux/tmux.conf` | Main tmux config (editable after creation) |
| `tmux/tmux.*.conf` | Additional config files you can add |
| `tmux/tmux.sock` | Tmux server socket (isolates this project) |
| `tmux/plugins/` | TPM plugin directory |
| `tmux/plugins-update.sh` | Run manually to update all plugins |

## optmux YAML config

Add an `optmux:` section to your tmuxp YAML to configure shortcuts and tmux settings:

```yaml
optmux:
  shortcuts:
    C-M-b: gh browse .                              # Ctrl-Alt-b: run command directly
    C-M-e:
      command: ${VISUAL:-${EDITOR:-vim}} README.md  # exec directly (no shell)
      new_window: true                              # open in a new-window
    E:
      send_keys: ${VISUAL:-${EDITOR:-vim}} .        # send_keys (runs in a new shell)
      zoom: false                                   # do not zoom (default: true for splits)
  tmux_config:
    project-settings: |
      set -g status-style bg=blue
```

### Shortcuts

Shortcuts bind tmux keys to commands:

- **`C-M-*` keys** are bound globally (no prefix needed)
- **Other keys** require the tmux prefix (`C-t`)

What a shortcut's value can *do* — `command:`, `send_keys:`, `new_window:`,
etc. — is the [action block](#action-block), shared with `menu:` custom
items below.

### Detached shortcuts

`detached: true` runs a command without moving your cursor — handy for things like `open -R .git` or `gh browse .` that do their real work elsewhere. It comes in three flavors:

| | where it runs | when it finishes |
|---|---|---|
| `detached: true` | a split pane in the current window | **drops the window's zoom** (see below) |
| `detached` + `float_window: true` | a floating pane over the current window | disappears, layout and zoom untouched |
| `detached` + `new_window: true` | a background window | nothing on screen changes |

`remain` controls what happens on exit: `on-error` (the default) closes silently on success and holds the pane open with a dismiss prompt on failure, `false` always closes, `true` always holds. Whenever a detached shortcut holds itself open it rings the bell, so tmux flags the window in the status line rather than leaving you to find it.

**Known issue: a quick detached split loses your zoom.** tmux unzooms a window whenever any pane in it dies, so a detached split pane drops the origin pane's zoom the moment the command finishes. The binding does re-zoom when it opens the split, and that holds for as long as the command runs — but nothing survives to re-apply it afterwards (a `pane-exited` hook fires *before* tmux fixes the layout, so it cannot help). Long-running commands are unaffected in practice; short ones like `open -R .git` unzoom you.

Workarounds, in order of preference:

1. **`float_window: true`** — a floating pane sits outside the layout, so opening and closing it never touches the zoom. Best fit for quick commands, and it works whatever state the window is in: because tmux 3.7b crashes if a float is created while the window is zoomed, the binding checks at press time and falls back to a background window in exactly that case, which leaves the zoom alone too. Requires tmux 3.7+; see [TROUBLESHOOTING-tmux-floating-panes.md](TROUBLESHOOTING-tmux-floating-panes.md) for the details.
2. **`new_window: true`** — always safe, at the cost of the command living in a separate window you may be surprised to find later.
3. **`remain: true`** — the pane never dies, so the zoom never drops; you dismiss it by hand. Note that each invocation leaves a pane behind, and once the window is full the split fails *and* the zoom is lost anyway.

### Action block

`shortcuts:` values and `menu:` custom items describe an action the same
way — this is the shared vocabulary compiled by `optmux/actions.py`:

- **`command:`** — shell command, run directly (default for a plain string value)
- **`send_keys:`** — sends the command to a fresh shell instead of running it directly (supports shell expansion; one line at a time)
- **`tmux:`** — a raw tmux command, run as-is (bypasses everything below)
- **`new_window: true`** — opens in a new window instead of a split
- **`float_window: true`** — opens in a floating pane (tmux 3.7+) — see [detached shortcuts](#detached-shortcuts) above
- **`zoom: false`** — disables auto-zoom on splits (default: true)
- **`detached: true`** — runs it without stealing focus, and holds it open on failure (see [`remain`](#detached-shortcuts))
- **`remain:`** — `on-error` (default when detached/new_window/float_window), `true`, or `false` — see [detached shortcuts](#detached-shortcuts)

One default differs between the two: a **shortcut** with none of
`new_window`/`float_window` set opens a **split** (it's a keybinding, so
you're usually mid-task in the current window); a **menu** custom item with
neither set opens a **new window** (a menu click is more often "go start
this over there"). Set either explicitly to override.

### tmux_config

Entries under `tmux_config:` are written as `tmux.optmux-extras.{name}.conf` files and auto-sourced by tmux.

### Menu

tmux has no API for editing its built-in right-click menus (session, window,
pane) — the only way to change one is to redefine it whole. `menu:` lets you
do that from YAML: list the items you want, in order, and optmux compiles a
static `bind`/`display-menu` config for you. A bare `"*"` pulls in the rest
of tmux's own default items for that menu, unchanged, so you only spell out
what you're adding or reordering:

```yaml
optmux:
  menu:
    pane:
      - key: w
        title: New Window (C-t c)
        new_window: true      # bundled default: adds "New Window" ahead of tmux's own items
      - "*"
```

- **`key:` / `title:`** — the accelerator and label for a custom item, plus the [action block](#action-block) fields (`command:`, `tmux:`, `send_keys:`, `new_window:`, `float_window:`, `zoom:`, `detached:`, `remain:`)
- **`default: <name>`** (or a bare string) — reuses one of tmux's own items by name; add `title:`/`key:` alongside it to retitle or remap that item without changing what it does
- **`separator`** (or `""`) — a divider line
- Supported contexts: `session`, `window`, `pane`. A context left out of `menu:` keeps tmux's untouched default.

**Reordering/retitling only touches items you name.** `"*"` inserts *unclaimed*
defaults (in tmux's own order) wherever it appears — it doesn't replace a
default item you've already referenced by name, and it doesn't drop one just
because you added a same-key custom item ahead of it. To actually replace a
default item's behavior (not just its label or key), leave `"*"` out and
list every item you want, in order — see the session example below.

More examples:

```yaml
optmux:
  menu:
    # Pane menu: a floating lazygit, a "run tests" that types into a split,
    # and a background clipboard copy -- then everything tmux ships by default.
    pane:
      - key: g
        title: lazygit
        command: lazygit
        float_window: true          # floats over the window; layout/zoom untouched
      - key: t
        title: Run tests
        send_keys: pytest -x        # types the command into a fresh split and runs it
      - key: y
        title: Copy path
        command: printf '%s' "$PWD" | pbcopy
        detached: true              # menu items default to new_window, so this is a
                                     # background window -- nothing on screen changes
      - "*"

    # Window menu: keep everything, just rename/remap Kill to something less
    # trigger-happy under the mouse.
    window:
      - default: Kill
        title: Close Window
        key: q
      - "*"

    # Session menu: replace Detach with a confirm-before version, and add
    # tmux's own window/pane picker (normally only reachable via prefix w).
    # No "*" here -- confirm-before *replaces* the item at 'd', so the rest
    # is spelled out in tmux's own order to keep Detach's original binding
    # from also showing up. 'T' avoids colliding with New Window's 'w'.
    session:
      - key: d
        title: Detach (confirm)
        tmux: confirm-before -p "detach? (y/n)" detach-client
      - key: T
        title: Windows/Panes
        tmux: choose-tree -Zw
      - Next
      - Previous
      - separator
      - Renumber
      - Rename
      - separator
      - New Session
      - New Window
```

A context left out of `menu:` entirely keeps tmux's untouched default. Supported contexts: `session`, `window`, `pane`.

### Personal config (`~/.optmux.yaml`)

Create `~/.optmux.yaml` to define personal defaults that apply to all optmux sessions:

```yaml
optmux:
  shortcuts:
    C-M-g: lazygit
  tmux_config:
    my-defaults: |
      set -g status-style bg=green
```

Personal config is merged with per-project config. When both define the same key, **personal settings take precedence**.

### Customization

- Edit `tmux/tmux.conf` to change tmux settings
- Drop `tmux/tmux.mysetup.conf` files for additional config (auto-sourced)
- Run `tmux/plugins-update.sh` from inside tmux to update plugins
- Press `prefix + R` to reload the config

### Environment variables

optmux sets these before launching tmux/tmuxp:

| Variable | Value |
|---|---|
| `OPTMUX_DIR` | Absolute path to the `.$NAME.optmux.d/` directory |
| `OPTMUX_NAME` | Name derived from YAML filename or cwd (e.g., `myproject`) |
| `TMUX_PLUGIN_MANAGER_PATH` | `$OPTMUX_DIR/tmux/plugins` |

## Clipboard integration

optmux ships [tmux-yank](https://github.com/netj/tmux-yank) and sets `set-clipboard on` + `allow-passthrough on`, so yanking in copy-mode lands on your system clipboard. Locally that goes through `pbcopy`/`xclip`. **Over SSH, [OSC 52](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands) is the only mechanism** — the remote tmux emits an escape sequence and your local terminal writes it to the clipboard, with no relay, agent, or daemon in between.

### macOS Terminal.app has no OSC 52 support

Local copying still works, but **copying from a remote optmux session over SSH will not reach your pasteboard** — Terminal.app discards the escape sequence, and no tmux configuration can change that. optmux deliberately doesn't ship a clipboard relay to work around it; that means a socket on your laptop accepting arbitrary bytes into your pasteboard, to replace what modern terminals already do natively.

**Workaround:** turn off **View → Allow Mouse Reporting** (`⌘R`), or hold `Fn`, to hand the mouse back to Terminal and drag-select with its own selection, then `⌘C`. `⌘R` again returns the mouse to tmux. You get only what's on screen, and the selection cuts across split panes — zoom first with `prefix + z`.

**Better:** use a terminal that supports OSC 52 — [Ghostty](https://ghostty.org), [iTerm2](https://iterm2.com), [Warp](https://warp.dev), [kitty](https://sw.kovidgoyal.net/kitty/), [WezTerm](https://wezterm.org), or [Alacritty](https://alacritty.org). The tips screen (window 0, or `C-M-h`) nags about this unless it can confirm your terminal, using the attached client's `TERM_PROGRAM` and terminal type — over SSH only the latter survives, so `xterm-ghostty` and friends are still recognized on remote hosts.

## Development

```bash
# install the latest main branch
uvx git+https://github.com/netj/optmux.git

# local editable install for development
uv tool install -e .

# test any local changes directly (best for testing branches)
uv run optmux ./example.optmux.yaml

# run tests
uv run pytest                  # all tests
uv run pytest -m "not e2e"     # skip E2E tests (no tmux needed)
uv run pytest -m e2e           # E2E only (requires tmux)
```

## License

[MIT](LICENSE)
