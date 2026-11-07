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
optmux pick [--list] [--live] [-1] [QUERY]
```

Every project has its own TMUX server, so nothing shows what is running across projects. optmux remembers each project it was started in (`${XDG_STATE_HOME:-~/.local/state}/optmux/projects.tsv`), and `optmux pick` lists them with [fzf](https://github.com/junegunn/fzf) (a numbered menu if fzf is missing): ● has a running session, ○ doesn't; running ones come first, most recently active on top. The preview shows the session's windows and their directories, with a `[bell]` on those that rang.

- `Enter` attaches to the project's session, starting it if needed
- `ctrl-x` stops the highlighted project's session, or forgets the project if it isn't running, after a `y/N` (projects whose directory or YAML is gone are dropped automatically)
- `Esc` or `ctrl-d` quits
- `QUERY` pre-filters; `-1` picks without asking when exactly one project matches; `--live` hides projects that aren't running; `--list` prints TSV (`state kind target session socket`) for scripts

`optmux pick` is one action: it returns after you detach or exit (status 0), so a shell wrapper can offer to pick again. Exit status is 130 if you cancelled, and 1 if there was nothing to pick.

### Running a command with optmux's settings

```bash
optmux [DIR | YAML] env COMMAND [ARGS...]
```

Runs the command with optmux's opinionated environment (delta as git's pager, less with the mouse and clickable links, the layered lazygit config, …). It's [`optmux-env`](config.md#optmux-env) as a subcommand, so it works in any shell, even where your rc has rebuilt `PATH`: `optmux env git log -p`, `optmux env lazygit`. Inside an optmux pane it uses that project's settings; elsewhere, give it the DIR or YAML (e.g. `optmux . env git diff`).

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
| `env.sh` | optmux's opinionated environment ([`env`](config.md#env), [`git_config`](config.md#git_config), [`lazygit`](config.md#lazygit)), applied by [`optmux-env`](config.md#optmux-env) |
| `bin/` | Helper scripts (`optmux-*`), on `PATH` for shortcuts (and in shells that source `env.sh`) |
| `lazygit/config.yml` | Generated from [`+lazygit:`](config.md#lazygit) |

`env.sh`, `bin/`, and `lazygit/` are regenerated on every launch.

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
