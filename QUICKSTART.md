# Quick Start

**Your coding agent edits files. Git already knows how to show, stage, and undo file edits. optmux puts them side by side.**

Run [Claude Code](https://claude.com/claude-code) (or any agent) in one pane, with lazygit, a shell, and your editor a keystroke away in the same TMUX window. Then:

1. **Watch and steer.** See each change as it lands. Keep the good hunks, throw out the rest.
2. **Show, don't tell.** Make one example edit yourself, and tell the agent "do it like this".
3. **Run a dozen agents at once.** One task, one worktree, one window.

## Setup

```bash
brew install netj/tap/optmux   # optmux + tmux, wtcode, lazygit, delta, less, fzf, gh
```

Put a small `.optmux.yaml` in your repo (check it in, or keep it in `.git/info/exclude`):

```yaml
#!/usr/bin/env optmux
session_name: myproject
start_directory: .
windows:
- window_name: claude
  panes:
  - claude
```

Then `chmod +x .optmux.yaml && ./.optmux.yaml`, or just run `optmux .` for a plain session. Press **`C-M-h`** (Ctrl+Alt+h, or Control+Option+h on a Mac) any time for the cheatsheet.

> **Mouse:** optmux turns on mouse mode everywhere: in TMUX (click panes, drag borders, scroll), in `less` (scroll and click links), and in lazygit.
> Keyboard works too, but clicking is often the fastest way to review.

## 1. Watch and steer: lazygit beside the agent

Press **`C-M-g`** in the agent's pane.
[lazygit](https://github.com/jesseduffield/lazygit) opens in a split, zoomed to fill the window.
**`C-M-o`** or **`C-M-\`** jumps back to the other pane and zooms it, so you can flip between *agent* and *changes* with one key.

While the agent works, lazygit refreshes by itself.
optmux sets lazygit up to render diffs with [delta](https://github.com/dandavison/delta), so you get syntax highlighting, word-level changes, and line numbers.

**Use the staging area as a checkpoint.** This is the habit that pays off most:

- Agent finishes a step → skim the diff in lazygit → **stage what you accept** (`space` on a file, or `enter` to stage single hunks and lines).
- Anything *unstaged* now is new since your last review, so the next step's diff is small and only shows what changed.
- Didn't like a hunk? **Discard just that hunk** (`d` in the hunk view) and tell the agent why. Its other edits stay put.
- Happy with the whole thing? Commit from lazygit (`c`), or ask the agent to commit what's staged.

Some lazygit keys optmux adds:

| Key | Action |
|---|---|
| `Ctrl-g` | Diff the branch against the default branch (`origin/HEAD`). This is what the PR will contain. |
| click a line number | Open that line in your `$EDITOR` |

Your own lazygit config still loads, with optmux's settings on top. Change optmux's under `lazygit:` in `~/.optmux.yaml`; see [lazygit](README.md#lazygit).

## 2. Show, don't tell: example edits

Some changes take a paragraph to explain but one edit to show: "rename these the way I like," "this error message style, not that one," "split it like *this*."
So edit the file yourself, then point the agent at your edit:

1. Open the exact spot. From any diff, **click a line number** and your `$EDITOR` opens at that line.
   Or press **`C-M-f`** to fuzzy-find a file to edit.
2. Make **one** example change. Save, and don't stage it.
3. Tell the agent:
   > I changed `parse_args` in `cli.py` the way I want. See `git diff`. Do the same to the other subcommands.

The agent reads `git diff` and gets your intent exactly, down to naming, formatting, and edge cases.
Because you left the example unstaged, your edit and the agent's follow-up show up together in lazygit, and you can check that it really did it *the same way*.

To hand the agent a few lines from another pane (a failing test, a log, a stack trace), press **`C-M-x`** from the agent's pane: [extrakto](https://github.com/laktak/extrakto) lists the lines on screen, you pick some with `Tab`, and `Enter` types them into Claude Code's `!` shell mode.

This works in reverse too: when the agent's diff is *almost* right, fix the one line yourself instead of describing the fix.
The agent picks up the change the next time it looks at the file.

### Clickable diffs: delta + less

Press **`C-M-d`** for a diff you can click: the branch against the default branch, what the PR will contain (the same as `Ctrl-g` in lazygit).
It renders with delta and opens in less with mouse support and link handling:

- **Scroll** with the mouse wheel; `n`/`N` jumps between files.
- **Click a line number** to select the link, **click again** to open that file at that line in `$EDITOR`. Quit the editor and you're back in the diff, where you left it.
- **Click a commit hash** to open it on GitHub.

`$EDITOR` can be vim, nvim, emacs, nano, helix, or VS Code-style editors (`code`, `cursor`, …); optmux passes the line number the way each one expects.

optmux applies these settings only to what its shortcuts start, so your own shells and `~/.gitconfig` behave as usual.
For anything else, prefix the command with `optmux env`: `optmux env git log -p`, `optmux env git show HEAD`.
To get clickable `git diff`, `git show`, and `git log -p` in every shell inside optmux without the prefix, add `[ -n "$OPTMUX_DIR" ] && . "$OPTMUX_DIR/env.sh"` to your shell rc.
Tweak the settings with [`git_config:`](README.md#git_config) and [`env:`](README.md#env).

## 3. Multitask: one task, one worktree, one window

One agent per checkout gets old fast. Give every task its own [git worktree](https://git-scm.com/docs/git-worktree) so agents never step on each other's files, and give every worktree its own TMUX window:

> **one task = one branch = one worktree = one TMUX window**

The window name is the worktree's directory, so the status bar reads like your task list.
Everything you need for a task is one keystroke away, as extra panes in *that same window*, already `cd`'d into *that same worktree*:

| Key | Pane | |
|---|---|---|
| `C-M-s` | shell | run tests, poke around |
| `C-M-g` | lazygit | review, stage, commit |
| `C-M-d` | diff | what the PR will contain |
| `C-M-f` | editor | fuzzy-find a file and edit it |

Each opens zoomed over the agent; `C-M-z` toggles the zoom, and `C-M-o` jumps back to the agent.

**Start a task instantly with `C-M-c`** ([wtcode](https://github.com/netj/wtcode)): fzf-pick an existing branch or worktree, or type `:new-branch:` to make one off `origin/HEAD`. wtcode creates the worktree (under `<repo>.worktrees/`) and launches Claude Code in it, in a new window. Describe the task and move on.

Then juggle the windows:

- When an agent needs you, the bell flags its window. **`C-t n`** / **`C-t p`** jumps to the next or previous window *with a bell*, skipping the quiet ones. (In Claude Code, set `/config` → notifications to *terminal bell*.)
- Too many windows? `optmux warp` from inside a worktree opens a focused session with only that worktree's windows. See [Warp sessions](README.md#warp-sessions).
- **`C-M-w`** opens the current branch's PR on GitHub, or the repo page if there's no PR yet.

A typical rhythm:

1. `C-M-c` → `:fix-flaky-test:` → describe the task → move on.
2. `C-M-c` → `:add-export-csv:` → describe the task → move on.
3. A bell rings → `C-t n` → `C-M-g` to review → stage, discard a hunk, or make an example edit → tell the agent → `C-t n` to the next one.
4. Done? Ask the agent to open a PR, then `C-M-w` to look at it.

## Where to go next

- [README](README.md): the full `optmux:` config reference (shortcuts, menus, plugins), warp sessions, clipboard over SSH
- Make it yours with `~/.optmux.yaml`: personal shortcuts, plugins, `env`, `git_config`, and `lazygit` settings for every session. See [Personal config](README.md#personal-config-optmuxyaml).
