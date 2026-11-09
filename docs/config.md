# optmux YAML config

Add an `+optmux:` section to your tmuxp YAML to configure shortcuts and tmux settings. For ideas to copy, see [`transform.optmux.yaml`](../transform.optmux.yaml): options for tmux-fingers, tmux-yank, tmux-resurrect and claritmux, shortcut ideas, and tool settings, mostly commented out.

A leading `+` marks a word optmux defines (`+optmux:`, `+shortcuts:`, `+command:`); names you choose (a shortcut's key, a plugin, an environment variable, a language) stay bare. Everything outside `+optmux:` is plain tmuxp. The same sections work in `~/.optmux.yaml`.

> **Upgrading from 0.14 and earlier:** the bare `optmux:` with `shortcuts:`, `command:`, ... still loads, with a deprecation warning. To upgrade, put a `+` before each of optmux's words (`optmux:` → `+optmux:`, `shortcuts:` → `+shortcuts:`, `command:` → `+command:`, `_tip_url:` → `+tip_url:`, and so on). Your own names and everything under `+lazygit:`, which is lazygit's own config, stay as they are.

```yaml
+optmux:
  +shortcuts:
    C-M-b: gh browse .                              # Ctrl+Alt+b (Control+Option+b on a Mac): run command directly
    C-M-e:
      +command: ${VISUAL:-${EDITOR:-vim}} README.md  # exec directly (no shell)
      +new_window: true                              # open in a new-window
    E:
      +send_keys: ${VISUAL:-${EDITOR:-vim}} .        # send_keys (runs in a new shell)
      +zoom: false                                   # do not zoom (default: true for splits)
  +tmux_config:
    project-settings: |
      set -g status-style bg=blue
```

## Shortcuts

Shortcuts bind tmux keys to commands:

- **`C-M-*` keys** are bound globally (no prefix needed)
- **Other keys** require the tmux prefix (`C-t`)

What a shortcut's value can *do* — `+command:`, `+send_keys:`, `+new_window:`,
etc. — is the [action block](#action-block), shared with `+menu:` custom
items below.

## Detached shortcuts

`+detached: true` runs a command without moving your cursor — handy for things like `open -R .git` or `gh browse .` that do their real work elsewhere. It comes in three flavors:

| | where it runs | when it finishes |
|---|---|---|
| `+detached: true` | a split pane in the current window | **drops the window's zoom** (see below) |
| `+detached` + `+float_window: true` | a floating pane over the current window | disappears, layout and zoom untouched |
| `+detached` + `+new_window: true` | a background window | nothing on screen changes |

`+remain` controls what happens on exit: `on-error` (the default) closes silently on success and holds the pane open with a dismiss prompt on failure, `false` always closes, `true` always holds. Whenever a detached shortcut holds itself open it rings the bell, so tmux flags the window in the status line rather than leaving you to find it.

**Known issue: a quick detached split loses your zoom.** tmux unzooms a window whenever any pane in it dies, so a detached split pane drops the origin pane's zoom the moment the command finishes. The binding does re-zoom when it opens the split, and that holds for as long as the command runs — but nothing survives to re-apply it afterwards (a `pane-exited` hook fires *before* tmux fixes the layout, so it cannot help). Long-running commands are unaffected in practice; short ones like `open -R .git` unzoom you.

Workarounds, in order of preference:

1. **`+float_window: true`** — a floating pane sits outside the layout, so opening and closing it never touches the zoom. Best fit for quick commands, and it works whatever state the window is in: because tmux 3.7b crashes if a float is created while the window is zoomed, the binding checks at press time and falls back to a background window in exactly that case, which leaves the zoom alone too. Requires tmux 3.7+; see [Troubleshooting floating panes](troubleshooting/tmux-floating-panes.md) for the details.
2. **`+new_window: true`** — always safe, at the cost of the command living in a separate window you may be surprised to find later.
3. **`+remain: true`** — the pane never dies, so the zoom never drops; you dismiss it by hand. Note that each invocation leaves a pane behind, and once the window is full the split fails *and* the zoom is lost anyway.

## Action block

`+shortcuts:` values and `+menu:` custom items describe an action the same
way — this is the shared vocabulary compiled by `optmux/actions.py`:

- **`+command:`** — shell command, run directly (default for a plain string value)
- **`+send_keys:`** — sends the command to a fresh shell instead of running it directly (supports shell expansion; one line at a time)
- **`+tmux:`** — a raw tmux command, run as-is (bypasses everything below)
- **`+new_window: true`** — opens in a new window instead of a split
- **`+float_window: true`** — opens in a floating pane (tmux 3.7+) — see [detached shortcuts](#detached-shortcuts) above
- **`+zoom: false`** — disables auto-zoom on splits (default: true)
- **`+detached: true`** — runs it without stealing focus, and holds it open on failure (see [`+remain`](#detached-shortcuts))
- **`+remain:`** — `on-error` (default when detached/new_window/float_window), `true`, or `false` — see [detached shortcuts](#detached-shortcuts)

One default differs between the two: a **shortcut** with none of
`+new_window`/`+float_window` set opens a **split** (it's a keybinding, so
you're usually mid-task in the current window); a **menu** custom item with
neither set opens a **new window** (a menu click is more often "go start
this over there"). Set either explicitly to override.

## +plugins

`+plugins:` maps each [TPM](https://github.com/tmux-plugins/tpm) plugin to its options: a dict of option → value (rendered as `set -g @option "value"`; `@` optional, `$VAR` expands, YAML `on`/`off` booleans are written as `on`/`off`), or a list of raw tmux config lines. Leave it empty for none. optmux installs them on launch and writes `optmux-plugins.conf`, sourced before TPM runs:

```yaml
+optmux:
  +plugins:
    netj/claritmux:
      claritmux_status_hostname: 1          # same as: set -g @claritmux_status_hostname "1"
    tmux-plugins/tmux-resurrect:
    - set -g @resurrect-dir "$OPTMUX_DIR/tmux/resurrect"   # or raw tmux lines
    Morantron/tmux-fingers: false    # disable a bundled plugin
```

A dict entry may also carry `+tip_url` (a string or a list) to showcase a great page or video; other keys are the plugin's tmux options. The tips screen lists every plugin with its GitHub URL (derived from `user/repo`) plus any `+tip_url` links beneath it:

```yaml
+optmux:
  +plugins:
    netj/claritmux:
      +tip_url: https://www.youtube.com/watch?v=VIDEO_ID
      claritmux_status_hostname: 1
```

Layers merge by plugin (bundled, then project, then `~/.optmux.yaml`); a later entry replaces that plugin's lines whole (including `+tip_url`). See `optmux/data/optmux-defaults.yaml` for the bundled list.

## +tmux_config

Entries under `+tmux_config:` are written as `tmux.optmux-extras.{name}.conf` files and auto-sourced by tmux.

## Menu

tmux has no API for editing its built-in right-click menus (session, window,
pane) — the only way to change one is to redefine it whole. `+menu:` lets you
do that from YAML: list the items you want, in order, and optmux compiles a
static `bind`/`display-menu` config for you. A bare `"*"` pulls in the rest
of tmux's own default items for that menu, unchanged, so you only spell out
what you're adding or reordering:

```yaml
+optmux:
  +menu:
    +pane:
      - +key: w
        +title: New Window (C-t c)
        +new_window: true      # bundled default: adds "New Window" ahead of tmux's own items
      - "*"
```

The bundled defaults also add **Find** (`C-M-f`) and **eXtract** (`C-M-x`) to the pane and window menus, so they are one right-click away. Menu layers add up (yours come after the bundled items), so a key of yours that is also `f` or `x` loses its accelerator to them: pick another.

- **`+key:` / `+title:`** — the accelerator and label for a custom item, plus the [action block](#action-block) fields (`+command:`, `+tmux:`, `+send_keys:`, `+new_window:`, `+float_window:`, `+zoom:`, `+detached:`, `+remain:`)
- **`+default: <name>`** (or a bare string) — reuses one of tmux's own items by name; add `+title:`/`+key:` alongside it to retitle or remap that item without changing what it does
- **`separator`** (or `""`) — a divider line
- Supported contexts: `session`, `window`, `pane`. A context left out of `+menu:` keeps tmux's untouched default.

**Reordering/retitling only touches items you name.** `"*"` inserts *unclaimed*
defaults (in tmux's own order) wherever it appears — it doesn't replace a
default item you've already referenced by name, and it doesn't drop one just
because you added a same-key custom item ahead of it. To actually replace a
default item's behavior (not just its label or key), leave `"*"` out and
list every item you want, in order — see the session example below.

More examples:

```yaml
+optmux:
  +menu:
    # Pane menu: a floating lazygit, a "run tests" that types into a split,
    # and a background clipboard copy -- then everything tmux ships by default.
    +pane:
      - +key: g
        +title: lazygit
        +command: lazygit
        +float_window: true          # floats over the window; layout/zoom untouched
      - +key: t
        +title: Run tests
        +send_keys: pytest -x        # types the command into a fresh split and runs it
      - +key: y
        +title: Copy path
        +command: printf '%s' "$PWD" | pbcopy
        +detached: true              # menu items default to new_window, so this is a
                                     # background window -- nothing on screen changes
      - "*"

    # Window menu: keep everything, just rename/remap Kill to something less
    # trigger-happy under the mouse.
    +window:
      - +default: Kill
        +title: Close Window
        +key: q
      - "*"

    # Session menu: replace Detach with a confirm-before version, and add
    # tmux's own window/pane picker (normally only reachable via prefix w).
    # No "*" here -- confirm-before *replaces* the item at 'd', so the rest
    # is spelled out in tmux's own order to keep Detach's original binding
    # from also showing up. 'T' avoids colliding with New Window's 'w'.
    +session:
      - +key: d
        +title: Detach (confirm)
        +tmux: confirm-before -p "detach? (y/n)" detach-client
      - +key: T
        +title: Windows/Panes
        +tmux: choose-tree -Zw
      - Next
      - Previous
      - separator
      - Renumber
      - Rename
      - separator
      - New Session
      - New Window
```

A context left out of `+menu:` entirely keeps tmux's untouched default. Supported contexts: `session`, `window`, `pane`.

## +env

Environment variables for commands run through [`optmux-env`](#optmux-env). `$VAR` expands at launch, and a null value unsets the variable. Layers merge by variable name.

```yaml
+optmux:
  +env:
    EDITOR: nvim
    LESS: -R --mouse   # replaces the bundled -XRiMWSc --mouse
    PAGER:             # null: unset
```

## optmux-env

`env`, `git_config`, and `lazygit` are all written to `$OPTMUX_DIR/env.sh`. **They apply only to commands started through `optmux-env`**, and to everything those commands start in turn. Your shells inside optmux behave exactly as they do outside it.

The bundled shortcuts use it, by absolute path (`"$OPTMUX_DIR/bin/optmux-env"`), since your shell startup files may rebuild `PATH`: `C-M-g` runs lazygit and `C-M-d` runs the PR diff through it. Inside those, optmux's settings override yours: lazygit runs git, git runs delta as its pager, delta runs less, and less runs the link handler, all with optmux's settings. Use it in your own shortcuts the same way:

```yaml
+optmux:
  +shortcuts:
    C-M-l:
      +command: |
        "$OPTMUX_DIR/bin/optmux-env" git log -p
```

Your shell rc may rebuild `PATH` and drop `optmux-env`; `optmux env COMMAND...` always works. To use optmux's settings in every shell inside optmux, add this to your shell rc. It also puts the `optmux-*` helpers back on `PATH` if your rc reorders it:

```bash
[ -n "$OPTMUX_DIR" ] && . "$OPTMUX_DIR/env.sh"
```

## +git_config

git config for commands run through [`optmux-env`](#optmux-env), passed through `GIT_CONFIG_PARAMETERS` (the env equivalent of `git -c`, which, unlike `GIT_CONFIG_COUNT`, delta also reads for its `delta.*` settings). It takes precedence over `~/.gitconfig` and repo config without modifying either. Keys merge across layers. A pager setting (`core.pager`, `interactive.diffFilter`, `pager.*`) whose command isn't installed is skipped, so a missing delta falls back to your own pager.

```yaml
+optmux:
  +git_config:
    delta.side-by-side: true
    delta.line-numbers: false
    core.pager:          # null: drop the bundled delta pager
```

## +lazygit

[lazygit config](https://github.com/jesseduffield/lazygit/blob/master/docs/Config.md), written to `$OPTMUX_DIR/lazygit/config.yml` and loaded *after* your own lazygit config via `LG_CONFIG_FILE`. Settings optmux doesn't mention keep your values, and the ones it does mention use optmux's. Layers deep-merge (lists replace). A `git.diffRenderers` entry whose command isn't installed is skipped.

```yaml
+optmux:
  +lazygit:
    gui:
      nerdFontsVersion: "3"
    git:
      diffRenderers:
      - colorArg: always
        command: delta --paging=never --side-by-side
```

## Personal config (`~/.optmux.yaml`)

Create `~/.optmux.yaml` to define personal defaults that apply to all optmux sessions:

```yaml
+optmux:
  +shortcuts:
    C-M-g: lazygit
  +tmux_config:
    my-defaults: |
      set -g status-style bg=green
```

Personal config is merged with per-project config. When both define the same key, **personal settings take precedence**.

## Applying changes

- Change tmux settings with [`+tmux_config:`](#tmux_config), not by editing `tmux/tmux.conf`: it is [generated](usage.md#what-optmux-generates) and read-only
- Press `prefix I` (or `U`) to install/update plugins and reload the config (runs `tmux/plugins-update.sh`; TPM's own `I`/`U` only print DONE)
- Press `prefix + R` to reload the config
