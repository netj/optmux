# Using optmux

The `optmux` command, what it sets up for each project, and the environment it runs in. For the `+optmux:` section of the YAML, see [optmux YAML config](config.md).

## First run

Try the included example:

```bash
git clone https://github.com/netj/optmux.git && cd optmux
./example.optmux.yaml
```

On first run, optmux will:

1. Create `.example.optmux.d/tmux/` next to the YAML file
2. Seed a default `tmux.conf` with TPM and plugins
3. Bootstrap TPM; the first attach opens a popup that installs/updates all plugins (same as `prefix I`) and then shows the tips (`C-M-h` shows them again)
4. Launch tmuxp with an isolated tmux server

## Commands

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
optmux pick [--list] [--live] [-1] [--title TITLE] [--title-without-hostname] [QUERY]
```

Every project has its own TMUX server, so nothing shows what is running across projects. optmux remembers each project it was started in (`${XDG_STATE_HOME:-~/.local/state}/optmux/projects.tsv`), and `optmux pick` lists them with [fzf](https://github.com/junegunn/fzf) (a numbered menu if fzf is missing): ● has a running session, ○ doesn't; running ones come first, most recently active on top. The preview shows the session's windows and their directories, with a `[bell]` on those that rang. The prompt names the machine (`optmux pick@myhost>`), handy when you ssh or mosh into several (`--title-without-hostname` leaves it out).

- `Enter` attaches to the project's session, starting it if needed
- `C-x` stops the highlighted project's session, or forgets the project if it isn't running, after a `y/N` (projects whose directory or YAML is gone are dropped automatically)
- `Esc` or `C-d` quits
- `QUERY` pre-filters; `-1` picks without asking when exactly one project matches; `--live` hides projects that aren't running; `--list` prints TSV (`state kind target session socket`) for scripts

`optmux pick` is one action: it returns after you detach or exit (status 0), so a shell wrapper can offer to pick again. Exit status is 130 if you cancelled, and 1 if there was nothing to pick.

### Running a command with optmux's settings

```bash
optmux [DIR | YAML] env COMMAND [ARGS...]
```

Runs the command with optmux's opinionated environment (delta as git's pager, less with the mouse and clickable links, the layered lazygit config, …). It's [`optmux-env`](config.md#optmux-env) as a subcommand, so it works in any shell, even where your rc has rebuilt `PATH`: `optmux env git log -p`, `optmux env lazygit`. Inside an optmux pane it uses that project's settings; elsewhere, give it the DIR or YAML (e.g. `optmux . env git diff`).

## What optmux generates

You configure optmux in your YAML ([`+optmux:`](config.md)), never in a directory. Each launch compiles that YAML, layered over the bundled defaults and `~/.optmux.yaml`, into a `.$NAME.optmux.d/` directory next to the YAML (`.optmux.d/` in a project directory), along with the project's runtime state. It is git-ignored (it seeds its own `.gitignore`), so there is nothing to commit and nothing to edit here: change the YAML and relaunch.

**Generated on every launch** (edits are overwritten, and the read-only ones refuse them):

| Path | What it is |
|---|---|
| `tmux/tmux.conf` | optmux's tmux config, bundled with optmux and read-only. Your settings reach tmux through the files below |
| `tmux/tmux.optmux-shortcuts.conf`, `tmux.optmux-menu.conf`, `tmux.optmux-extras.*.conf`, `optmux-plugins.conf` | Compiled from [`+shortcuts:`](config.md#shortcuts), [`+menu:`](config.md#menu), [`+tmux_config:`](config.md#tmux_config) and [`+plugins:`](config.md#plugins), sourced by `tmux.conf` |
| `tmux/tips.sh`, `tmux/plugins-update.sh` | The tips screen (`C-M-h`) and the plugin installer/updater (`prefix I`) |
| `env.sh` | optmux's settings from [`+env:`](config.md#env), [`+git_config:`](config.md#git_config) and [`+lazygit:`](config.md#lazygit), applied by [`optmux-env`](config.md#optmux-env) |
| `lazygit/config.yml` | Compiled from [`+lazygit:`](config.md#lazygit) |
| `bin/` | Helper scripts (`optmux-*`), on `PATH` for shortcuts (and in shells that source `env.sh`) |

**State that builds up while you work** (kept between launches, per project):

| Path | What it is |
|---|---|
| `tmux/tmux.sock` | The project's tmux server socket, which is what isolates it |
| `tmux/plugins/` | Plugins TPM installed |
| `tmux/resurrect/` | Saved sessions (tmux-resurrect) |
| `find/` | [optmux Find](find.md)'s tags index, history, and recent files |

Deleting the directory, once the session is stopped, is harmless: the next launch generates it again and reinstalls the plugins, and only your saved sessions and Find history are lost. Your own `tmux/tmux.NAME.conf` files are sourced too and left alone, but [`+tmux_config:`](config.md#tmux_config) keeps them in your YAML where they belong.

## Environment variables

optmux sets these before launching tmux/tmuxp:

| Variable | Value |
|---|---|
| `OPTMUX_DIR` | Absolute path to the `.$NAME.optmux.d/` directory |
| `OPTMUX_NAME` | Name derived from YAML filename or cwd (e.g., `myproject`) |
| `TMUX_PLUGIN_MANAGER_PATH` | `$OPTMUX_DIR/tmux/plugins` |
| `PATH` | `$OPTMUX_DIR/bin` prepended (`optmux-*` helper scripts) |

[`optmux-env`](config.md#optmux-env) additionally sets, for the command it runs:

| Variable | Value |
|---|---|
| anything under [`+env:`](config.md#env) | e.g. `PAGER`, `LESS`, `LESS_OSC8_OPEN_ANY` by default |
| `GIT_CONFIG_PARAMETERS` | from [`+git_config:`](config.md#git_config) |
| `LG_CONFIG_FILE` | your own lazygit config, then optmux's from [`+lazygit:`](config.md#lazygit) |
