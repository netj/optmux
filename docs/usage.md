# Using optmux

Start with `optmux .` in a project and press **`C-M-h`** for the tips. Keys come in two kinds: `C-M-` shortcuts (Ctrl+Alt, or Control+Option on a Mac) work directly, and the rest go through the TMUX prefix, **`C-t`** (Ctrl+T) rather than TMUX's usual `C-b`: press it, let go, then the key. A few things are worth learning first, since they are what you'll use all day, and each has a page of its own:

- **[Review changes](usage-review.md)**: `C-M-g` lazygit and `C-M-d` the PR diff, in whichever worktree you're in, with diffs rendered by delta and line numbers you can click to edit.
- **[Extract](usage-extract.md)** what you see: `C-M-x` picks a command, path, URL, hash, or PR number off the screen and types or copies it, over SSH too.
- **[Find](usage-find.md)** and open files: `C-M-f` searches files, live grep, tags, and language-server symbols in one picker.
- **[Pick](usage-pick.md)** among projects: `optmux pick` attaches to any project you've run, and tmux-resurrect brings sessions back after a restart.
- **[Warp](usage-warp.md)** to one workdir: `optmux warp` shows just the windows of a single worktree, and shares them with another terminal or an IDE.

optmux does the setup behind these for you: each launch compiles your YAML (and `~/.optmux.yaml`) into a generated, git-ignored `.optmux.d/` directory, installs the plugins, and starts the project's own tmux server. You change the YAML, never that directory; see [What optmux generates](config.md#what-optmux-generates) if you're curious. To change the shortcuts, plugins, or tool settings, see [optmux YAML config](config.md).

## First run

Try the included example:

```bash
git clone https://github.com/netj/optmux.git && cd optmux
./example.optmux.yaml
```

On first run, optmux sets up the project, bootstraps the plugin manager (TPM), and starts tmux with an isolated server; the first attach opens a popup that installs/updates all plugins (same as `prefix I`) and then shows the tips (`C-M-h` shows them again).

## Commands

The full set of ways to run `optmux`; `pick` and `warp` have their own pages above.

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

### Raw tmux access

```bash
optmux [DIR | YAML] tmux ARGS...
```

Runs `tmux ARGS...` directly against this project's isolated tmux server — no tmuxp bootstrapping, no session creation. Useful for one-off inspection or scripting without hand-rolling the `-S <sock>` path yourself, e.g. `optmux . tmux ls` or `optmux . tmux kill-server`.

### Running a command with optmux's settings

```bash
optmux [DIR | YAML] env COMMAND [ARGS...]
```

Runs the command with optmux's opinionated environment (delta as git's pager, less with the mouse and clickable links, the layered lazygit config, …). It's [`optmux-env`](config.md#optmux-env) as a subcommand, so it works in any shell, even where your rc has rebuilt `PATH`: `optmux env git log -p`, `optmux env lazygit`. Inside an optmux pane it uses that project's settings; elsewhere, give it the DIR or YAML (e.g. `optmux . env git diff`).
