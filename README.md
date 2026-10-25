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

`brew install netj/tap/optmux` pulls in tmux, [wtcode](https://github.com/netj/wtcode), [lazygit](https://github.com/jesseduffield/lazygit), [delta](https://github.com/dandavison/delta), a recent `less`, fzf, and gh as dependencies. See [Git, diffs, and links](#git-diffs-and-links).

**New here?** The **[Quick Start guide](QUICKSTART.md)** shows how to be an effective mentor and manager of AI coding agents like Claude Code: one worktree and window per task, with lazygit, your editor, and a shell a keystroke away in sibling panes.

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

Write a [tmuxp YAML config](https://tmuxp.git-pull.com/configuration/) with the optmux shebang line and make it executable. This needs `optmux` on your `PATH` (e.g. `brew install netj/tap/optmux`):

```yaml
#!/usr/bin/env optmux
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

### Picking a project

```bash
optmux pick [--list] [--live] [-1] [QUERY]
```

Every project has its own TMUX server, so nothing shows what is running across projects. optmux remembers each project it was started in (`${XDG_STATE_HOME:-~/.local/state}/optmux/projects.tsv`), and `optmux pick` lists them with [fzf](https://github.com/junegunn/fzf) (a numbered menu if fzf is missing): ● has a running session, ○ doesn't; running ones come first, most recently active on top. The preview shows the session's windows and their directories, with a `[bell]` on those that rang.

- `Enter` attaches to the project's session, starting it if needed
- `ctrl-x` stops the highlighted project's session
- `ctrl-d` forgets the project (projects whose directory or YAML is gone are dropped automatically)
- `QUERY` pre-filters; `-1` picks without asking when exactly one project matches; `--live` hides projects that aren't running; `--list` prints TSV (`state kind target session socket`) for scripts

`optmux pick` is one action: it returns after you detach or exit (status 0), so a shell wrapper can offer to pick again. Exit status is 130 if you cancelled, and 1 if there was nothing to pick.

### Running a command with optmux's settings

```bash
optmux [DIR | YAML] env COMMAND [ARGS...]
```

Runs the command with optmux's opinionated environment (delta as git's pager, less with the mouse and clickable links, the layered lazygit config, …). It's [`optmux-env`](#optmux-env) as a subcommand, so it works in any shell, even where your rc has rebuilt `PATH`: `optmux env git log -p`, `optmux env lazygit`. Inside an optmux pane it uses that project's settings; elsewhere, give it the DIR or YAML (e.g. `optmux . env git diff`).

## Example tmuxp YAML

Here's the included [`example.optmux.yaml`](example.optmux.yaml) showing shortcuts, tmux config, and window layout:

```yaml
#!/usr/bin/env optmux
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
| `tmux/resurrect/` | Saved session state (tmux-resurrect), isolated per project |
| `env.sh` | optmux's opinionated environment ([`env`](#env), [`git_config`](#git_config), [`lazygit`](#lazygit)), applied by [`optmux-env`](#optmux-env) |
| `bin/` | Helper scripts (`optmux-*`), on `PATH` for shortcuts (and in shells that source `env.sh`) |
| `lazygit/config.yml` | Generated from [`lazygit:`](#lazygit) |

`env.sh`, `bin/`, and `lazygit/` are regenerated on every launch.

## optmux YAML config

Add an `optmux:` section to your tmuxp YAML to configure shortcuts and tmux settings:

```yaml
optmux:
  shortcuts:
    C-M-b: gh browse .                              # Ctrl+Alt+b (Control+Option+b on a Mac): run command directly
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

### plugins

`plugins:` maps each [TPM](https://github.com/tmux-plugins/tpm) plugin to its options: a dict of option → value (rendered as `set -g @option "value"`; `@` optional, `$VAR` expands, YAML `on`/`off` booleans are written as `on`/`off`), or a list of raw tmux config lines. Leave it empty for none. optmux installs them on launch and writes `optmux-plugins.conf`, sourced before TPM runs:

```yaml
optmux:
  plugins:
    laktak/extrakto:
      extrakto_grab_area: window recent     # same as: set -g @extrakto_grab_area "window recent"
      extrakto_filter_order: word all line
    tmux-plugins/tmux-resurrect:
    - set -g @resurrect-dir "$OPTMUX_DIR/tmux/resurrect"   # or raw tmux lines
    Morantron/tmux-fingers: false    # disable a bundled plugin
```

A dict entry may also carry `_tip_url:` (a string or a list) to showcase a great page or video; keys starting with `_` are metadata, not options. The tips screen lists every plugin with its GitHub URL (derived from `user/repo`) plus any `_tip_url` links beneath it:

```yaml
optmux:
  plugins:
    laktak/extrakto:
      _tip_url: https://www.youtube.com/watch?v=VIDEO_ID
      extrakto_key: X
```

Layers merge by plugin (bundled, then project, then `~/.optmux.yaml`); a later entry replaces that plugin's lines whole (including `_tip_url`). See `optmux/data/optmux-defaults.yaml` for the bundled list.

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

### env

Environment variables for commands run through [`optmux-env`](#optmux-env). `$VAR` expands at launch, and a null value unsets the variable. Layers merge by variable name.

```yaml
optmux:
  env:
    EDITOR: nvim
    LESS: -R --mouse   # replaces the bundled -XRiMWSc --mouse
    PAGER:             # null: unset
```

### optmux-env

`env`, `git_config`, and `lazygit` are all written to `$OPTMUX_DIR/env.sh`. **They apply only to commands started through `optmux-env`**, and to everything those commands start in turn. Your shells inside optmux behave exactly as they do outside it.

The bundled shortcuts use it, by absolute path (`"$OPTMUX_DIR/bin/optmux-env"`), since your shell startup files may rebuild `PATH`: `C-M-g` runs lazygit and `C-M-d` runs the PR diff through it. Inside those, optmux's settings override yours: lazygit runs git, git runs delta as its pager, delta runs less, and less runs the link handler, all with optmux's settings. Use it in your own shortcuts the same way:

```yaml
optmux:
  shortcuts:
    C-M-l:
      command: |
        "$OPTMUX_DIR/bin/optmux-env" git log -p
```

Your shell rc may rebuild `PATH` and drop `optmux-env`; `optmux env COMMAND...` always works. To use optmux's settings in every shell inside optmux, add this to your shell rc. It also puts the `optmux-*` helpers back on `PATH` if your rc reorders it:

```bash
[ -n "$OPTMUX_DIR" ] && . "$OPTMUX_DIR/env.sh"
```

### git_config

git config for commands run through [`optmux-env`](#optmux-env), passed through `GIT_CONFIG_PARAMETERS` (the env equivalent of `git -c`, which, unlike `GIT_CONFIG_COUNT`, delta also reads for its `delta.*` settings). It takes precedence over `~/.gitconfig` and repo config without modifying either. Keys merge across layers. A pager setting (`core.pager`, `interactive.diffFilter`, `pager.*`) whose command isn't installed is skipped, so a missing delta falls back to your own pager.

```yaml
optmux:
  git_config:
    delta.side-by-side: true
    delta.line-numbers: false
    core.pager:          # null: drop the bundled delta pager
```

### lazygit

[lazygit config](https://github.com/jesseduffield/lazygit/blob/master/docs/Config.md), written to `$OPTMUX_DIR/lazygit/config.yml` and loaded *after* your own lazygit config via `LG_CONFIG_FILE`. Settings optmux doesn't mention keep your values, and the ones it does mention use optmux's. Layers deep-merge (lists replace). A `git.diffRenderers` entry whose command isn't installed is skipped.

```yaml
optmux:
  lazygit:
    gui:
      nerdFontsVersion: "3"
    git:
      diffRenderers:
      - colorArg: always
        command: delta --paging=never --side-by-side
```

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
| `PATH` | `$OPTMUX_DIR/bin` prepended (`optmux-*` helper scripts) |

[`optmux-env`](#optmux-env) additionally sets, for the command it runs:

| Variable | Value |
|---|---|
| anything under [`env:`](#env) | e.g. `PAGER`, `LESS`, `LESS_OSC8_OPEN_ANY` by default |
| `GIT_CONFIG_PARAMETERS` | from [`git_config:`](#git_config) |
| `LG_CONFIG_FILE` | your own lazygit config, then optmux's from [`lazygit:`](#lazygit) |

## Git, diffs, and links

optmux's shortcuts open git review tools with an opinionated setup. It's configured in [`optmux-defaults.yaml`](optmux-defaults.yaml) under [`env`](#env), [`git_config`](#git_config), and [`lazygit`](#lazygit), and applied only to what the shortcuts start, through [`optmux-env`](#optmux-env). Your dotfiles and your shells are left alone. See the [Quick Start guide](QUICKSTART.md) for how it fits into working with coding agents.

- **[lazygit](https://github.com/jesseduffield/lazygit)** (`C-M-g`): optmux's config is layered on top of yours. It adds `Ctrl-g` to diff against the default branch (`origin/HEAD`). Diffs render with delta, and clicking a line number opens it in your editor.
- **Clickable diff** (`C-M-d`, same as `Ctrl-g` in lazygit): what the branch changes against the default branch, rendered by delta in less, so you can scroll with the mouse and click a line number twice to edit it.
- **[delta](https://github.com/dandavison/delta)**: becomes git's pager (`core.pager`, `interactive.diffFilter`), with line numbers, `n`/`N` file navigation, moved-code coloring, and hyperlinked line numbers and commit hashes.
- **less**: mouse mode (`--mouse`) and an [OSC 8](https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda) hyperlink handler. Click a link once to select it and again to open it: `file://…#L<n>` opens `$VISUAL`/`$EDITOR` at that line, and `http(s)` links open your browser. Clicking links needs a recent `less` (Homebrew's; the formula depends on it).

Bundled helper scripts in `$OPTMUX_DIR/bin`, available in every pane:

| Script | What it does |
|---|---|
| `optmux-open-url URI` | Opens a hyperlink: files in your editor at the linked line, web links in the browser |
| `optmux-env CMD...` | Runs a command with optmux's settings. See [optmux-env](#optmux-env) |
| `optmux-diff-base` | Diffs the branch against the default branch (`origin/HEAD`, else `origin/main`): a diffstat, then the patch, i.e. what a PR would contain (`C-M-d`, lazygit's `Ctrl-g`) |
| `optmux-gh-open` | Opens the current branch's PR on GitHub, or the repo page (`C-M-w`) |

## Session persistence

optmux ships [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect):

- **`C-t C-s`** — save the current session (windows, panes, working directories)
- **`C-t C-r`** — restore the last saved session

Because each project has its own `.$NAME.optmux.d/tmux/resurrect/` folder (see [Config directory](#config-directory)), saves never mix between projects. Save project A, then project B — restoring either one brings back only its own layout.

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
