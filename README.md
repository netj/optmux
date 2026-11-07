# optmux

<p align="center">
  <img src="https://raw.githubusercontent.com/netj/optmux/main/optmux.svg" width="192" alt="optmux logo">
</p>

Optimal, opinionated, batteries-included TMUX that's neat and easy for any project.

Run `optmux .` in any project and get its own TMUX, already set up: plugins installed, mouse on everywhere, and one-key shortcuts for the tools you reach for while AI coding agents like Claude Code do the typing. Run several agents side by side, each in its own git worktree and window, and review, correct, and steer them without leaving the keyboard.

**New here?** Read **[The optmux Way](https://github.com/netj/optmux/blob/main/OPTMUX-WAY.md)**: how to stay the master mechanic, not the customer, when working with coding agents.

## What you can do

No prefix needed for the `C-M-` keys: Ctrl+Alt, or Control+Option on a Mac.

| Press | You get |
|---|---|
| `C-M-c` | A new task: a fresh git worktree, a new window, your agent running in it ([wtcode](https://github.com/netj/wtcode)) |
| `C-M-g` | [lazygit](https://github.com/jesseduffield/lazygit) beside the agent, on its uncommitted files or its branch's commits ([review](https://github.com/netj/optmux/blob/main/docs/review.md)) |
| `C-M-d` | The PR diff against the default branch, in delta: scroll with the mouse, click a line number to edit it ([review](https://github.com/netj/optmux/blob/main/docs/review.md)) |
| `C-M-f` | **Find**: files, live grep, tags, and language-server symbols in one picker, opened in your editor at the line ([Find](https://github.com/netj/optmux/blob/main/docs/find.md)) |
| `C-M-x` | **eXtract**: pick a command, path, URL, or hash off the screen and type or copy it ([eXtract](https://github.com/netj/optmux/blob/main/docs/extract.md)) |
| `C-M-s` | A shell in the same workdir |
| `C-M-w` | The branch's PR (or the repo) on GitHub |
| `C-M-z` | Zoom the pane in and out |
| `C-M-h` | The tips screen: every key, plugin, and setting in one place |
| `optmux pick` | Jump to any project you've run optmux in, running or not ([usage](https://github.com/netj/optmux/blob/main/docs/usage.md#picking-a-project)) |
| `optmux warp` | A focused session with only one worktree's windows ([usage](https://github.com/netj/optmux/blob/main/docs/usage.md#warp-sessions)) |

And out of the box:

- **Every project is isolated**: its own TMUX server, config, plugins, and saved layouts, so nothing leaks between projects.
- **Mouse everywhere**: click panes, drag borders, scroll in TMUX, less, and lazygit.
- **Copy reaches your clipboard, even over SSH** (OSC 52), and `C-t C-s` / `C-t C-r` save and restore a project's windows ([clipboard and sessions](https://github.com/netj/optmux/blob/main/docs/terminal.md)).
- **Your dotfiles stay yours**: optmux's git, delta, and lazygit settings apply only to what its shortcuts start.

## Get started

```bash
brew install netj/tap/optmux
cd myproject
optmux .
```

The formula brings tmux, wtcode, lazygit, delta, a recent `less`, fzf, universal-ctags, and gh along. The first attach installs the plugins and shows the tips; press **`C-M-c`** to start your first task.

No Homebrew? `uvx optmux .` runs it straight from PyPI (bring your own tmux and tools).

## Make it yours

Want the same windows every time? Write a [tmuxp](https://tmuxp.git-pull.com/configuration/) YAML with the optmux shebang, and add your own shortcuts under `+optmux:`:

```yaml
#!/usr/bin/env optmux
session_name: myproject
start_directory: .

+optmux:
  +shortcuts:
    C-M-b: gh browse .
    C-M-t:
      +send_keys: pytest -x
windows:
- window_name: agent
  panes:
  - claude
- window_name: shell
  panes:
  - ""
```

```bash
chmod +x myproject.optmux.yaml
./myproject.optmux.yaml
```

Put personal shortcuts, plugins, and tool settings for every project in `~/.optmux.yaml`. For ideas, [`transform.optmux.yaml`](https://github.com/netj/optmux/blob/main/transform.optmux.yaml) shows what optmux's plugins and tools can transform into: delete the `#` in front of the ones you like.

## Docs

- [The optmux Way](https://github.com/netj/optmux/blob/main/OPTMUX-WAY.md): the workflow, step by step
- [Using optmux](https://github.com/netj/optmux/blob/main/docs/usage.md): the commands (`stop`, `warp`, `pick`, `tmux`, `env`), the per-project directory, environment variables
- [optmux YAML config](https://github.com/netj/optmux/blob/main/docs/config.md): shortcuts, menus, plugins, `+env`, `+git_config`, `+lazygit`, `~/.optmux.yaml`
- [Git, diffs, and links](https://github.com/netj/optmux/blob/main/docs/review.md): lazygit, delta, clickable less, and the helper scripts
- [optmux Find](https://github.com/netj/optmux/blob/main/docs/find.md) and [optmux eXtract](https://github.com/netj/optmux/blob/main/docs/extract.md)
- [Clipboard and sessions](https://github.com/netj/optmux/blob/main/docs/terminal.md): OSC 52, Terminal.app, tmux-resurrect
- Troubleshooting: [tmux-fingers](https://github.com/netj/optmux/blob/main/docs/troubleshooting/tmux-fingers.md), [floating panes](https://github.com/netj/optmux/blob/main/docs/troubleshooting/tmux-floating-panes.md)

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
