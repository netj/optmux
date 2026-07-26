# optmux

<p align="center">
  <img src="https://raw.githubusercontent.com/netj/optmux/main/optmux.svg" width="192" alt="optmux logo">
</p>

Optimal, opinionated, batteries-included TMUX that's neat and easy for any project.

A [tmuxp](https://tmuxp.git-pull.com) wrapper that creates per-project tmux config directories with [TPM](https://github.com/tmux-plugins/tpm) and plugins pre-configured.

## Quick Start

```bash
# run optmux anywhere (installs on first use via uv)
uvx optmux

# strongly recommended: install wtcode + lazygit for the full experience
brew install netj/tap/optmux
```

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

### Without arguments

```bash
optmux
```

Opens plain `tmux` using `.optmux.d/` in the current directory — useful for a quick, isolated tmux session with the bundled config.

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
      window: true                                  # in a new-window
    E:
      send-keys: ${VISUAL:-${EDITOR:-vim}} .        # send-keys (given command is run in a new shell)
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
      window: true                                  # open in a new-window
    E:
      send-keys: ${VISUAL:-${EDITOR:-vim}} .        # send-keys (runs in a new shell)
      zoom: false                                   # do not zoom (default: true for splits)
  tmux_config:
    project-settings: |
      set -g status-style bg=blue
```

### Shortcuts

Shortcuts bind tmux keys to commands:

- **`C-M-*` keys** are bound globally (no prefix needed)
- **Other keys** require the tmux prefix (`C-t`)
- **`command:`** executes directly (default for string values)
- **`send-keys:`** sends the command to a new shell (supports shell expansion)
- **`window: true`** opens in a new window instead of a split
- **`zoom: false`** disables auto-zoom on splits (default: true)
- **`detached: true`** runs in a background window without stealing focus — the current window is left completely alone, zoom included. If the command fails, the window stays open with a prompt and rings the bell so tmux flags it in the status line

### tmux_config

Entries under `tmux_config:` are written as `tmux.optmux-extras.{name}.conf` files and auto-sourced by tmux.

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
