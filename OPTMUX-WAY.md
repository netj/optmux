# The optmux Way

**Are you steering your AI coding tool, or just signing off on what it hands back?** You approve diffs you only skimmed. The code has moved three steps past what you understand. The actual code, data, and files feel several layers removed, seen only through a chat transcript.

The optmux Way is how to stay on top of your work with AI coding tools like Claude Code. optmux sets up a terminal workspace (built on TMUX) where several tasks run side by side, each in its own checkout, and you review, correct, and steer them from the keyboard, with the real files one keystroke away.

**Be the master mechanic, not the customer.** The customer hands over the keys and takes the shop's word for what got fixed. The master mechanic knows what's wrong from the sound of the car pulling in. That sense only comes from keeping your hands in the engine, and no tool can hand it to you. So keep yours in: set bold, challenging goals for your AI coding tools, then guide the work with a sharp eye for detail until it comes out beautiful. Every task gets its own workdir and its own window. The coding tool runs in one pane; lazygit, your editor, and a shell are a keystroke away in sibling panes, already in that same workdir. You review its work, step in with a surgical example edit, and start the next task, without leaving the keyboard.

1. **One task, one workdir, one window.** `C-M-c` starts a task: new git worktree, new window, your coding tool running.
2. **Look over its shoulder.** `C-M-g` lazygit, `C-M-d` the PR diff, `C-M-s` a shell, `C-M-f` your editor. Each opens right beside the tool. A command in its output you want to run? `C-M-x` picks it off the screen and types it in.
3. **Teach by example.** Fix one spot yourself and tell your coding tool "do it like this".
4. **Keep many going.** `C-M-c` again starts the next task in a fresh workdir and window while the others keep working, undisturbed. A bell tells you which task needs you; `C-t n` takes you there.

## Setup

```bash
brew install netj/tap/optmux   # optmux + tmux, wtcode, lazygit, delta, less, fzf, gh
cd myproject
optmux .
```

That's it. Press **`C-M-h`** (Ctrl+Alt+h, or Control+Option+h on a Mac) any time for the cheatsheet, and **`C-M-c`** to start your first task.
Want the same windows every time, say Claude Code already running? Write a small YAML file for the project; see [As a shebang](docs/usage.md#as-a-shebang).

> **Mouse:** optmux turns on mouse mode everywhere: in TMUX (click panes, drag borders, scroll), in `less` (scroll and click links), and in lazygit.
> Keyboard works too, but clicking is often the fastest way to review.

## 1. One task, one workdir, one window

One checkout for every task gets old fast. Give every task its own [git worktree](https://git-scm.com/docs/git-worktree) so tasks never step on each other's files, and give every worktree its own TMUX window:

> **one task = one branch = one worktree = one TMUX window**

The window name is the worktree's directory, so the status bar reads like your task list.
Everything you need for a task is one keystroke away, as extra panes in *that same window*, already `cd`'d into *that same worktree*:

| Key | Pane | |
|---|---|---|
| `C-M-s` | shell | run tests, poke around |
| `C-M-g` | lazygit | review, stage, commit |
| `C-M-d` | diff | what the PR will contain |
| `C-M-f` | editor | find a file or a tag (ranked together, omni) or a line (git grep) and edit it; `C-M-f` again cycles, it resumes where you left off |

Each opens zoomed over the coding tool; `C-M-z` toggles the zoom, and `C-M-o` jumps back to it.

**`C-M-x`** picks a command off the screen (the one the tool tells you to run, or a whole script) and types it into the pane you're in: the `C-M-s` shell, or Claude Code after `!`. More in [Teach by example](#3-teach-by-example).

**Start a task instantly with `C-M-c`** ([wtcode](https://github.com/netj/wtcode)): fzf-pick an existing branch or worktree, or type `:new-branch:` to make one off `origin/HEAD`. wtcode creates the worktree (under `<repo>.worktrees/`) and launches Claude Code in it, in a new window. Describe the task and move on.

## 2. Look over its shoulder: watch and steer

Press **`C-M-g`** in the coding tool's pane: [lazygit](https://github.com/jesseduffield/lazygit) opens beside it, in that worktree.
**`C-M-o`** or **`C-M-\`** flips back to the coding tool and zooms it, so you can go between *the tool* and *its changes* with one key.

While the tool works, lazygit refreshes by itself.
optmux sets lazygit up to render diffs with [delta](https://github.com/dandavison/delta), so you get syntax highlighting, word-level changes, and line numbers.

**Use the staging area as a checkpoint.** This is the habit that pays off most:

- The tool finishes a step → skim the diff in lazygit → **stage what you accept** (`space` on a file, or `enter` to stage single hunks and lines).
- Anything *unstaged* now is new since your last review, so the next step's diff is small and only shows what changed.
- Didn't like a hunk? **Discard just that hunk** (`d` in the hunk view) and tell the tool why. Its other edits stay put.
- Happy with the whole thing? Commit from lazygit (`c`), or ask the tool to commit what's staged.

Some lazygit keys optmux adds:

| Key | Action |
|---|---|
| `Ctrl-g` | Diff the branch against the default branch (`origin/HEAD`). This is what the PR will contain. |
| click a line number | Open that line in your `$EDITOR` |

Your own lazygit config still loads, with optmux's settings on top. Change optmux's under `+lazygit:` in `~/.optmux.yaml`; see [lazygit](docs/config.md#lazygit).

## 3. Teach by example

Some changes take a paragraph to explain but one edit to show: "rename these the way I like," "this error message style, not that one," "split it like *this*."
So edit the file yourself, then point the tool at your edit:

1. Open the exact spot. From any diff, **click a line number** and your `$EDITOR` opens at that line.
   Or press **`C-M-f`** to fuzzy-find a file to edit.
   Or, if the spot is named on screen (a path in a stack trace, a function in the tool's reply), pick it with **`C-M-x`** and press **`C-M-f`** to find it.
2. Make **one** example change. Save, and don't stage it.
3. Tell the tool:
   > I changed `parse_args` in `cli.py` the way I want. See `git diff`. Do the same to the other subcommands.

The tool reads `git diff` and gets your intent exactly, down to naming, formatting, and edge cases.
Because you left the example unstaged, your edit and the tool's follow-up show up together in lazygit, and you can check that it really did it *the same way*.

To hand the tool a few lines from another pane (a failing test, a log, a stack trace), press **`C-M-x`**: a picker lists the lines on screen (in order, duplicates and all, so a multiline script survives), you pick some with `Tab`, and `Enter` types them into the active pane. In Claude Code, press `!` first so they land in its shell mode. `C-M-x` again switches to spans: what a program highlighted (the command or path) mixed with URLs, paths, hashes, PR numbers and versions. `Ctrl-f`, `Ctrl-g` and `C-M-f` look the pick up in the project instead (files, grep, everything). `C-t X` is the same picker behind the prefix.

This works in reverse too: when the tool's diff is *almost* right, fix the one line yourself instead of describing the fix.
The tool picks up the change the next time it looks at the file.

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
Tweak the settings with [`+git_config:`](docs/config.md#git_config) and [`+env:`](docs/config.md#env).

## 4. Keep many going

- An urgent bug report, a sudden idea, a chore you keep putting off: none of them has to wait for the current task to finish. **`C-M-c`** spins up the next task in its own worktree and window, while every task already running carries on in its own: their files, panes, and progress stay untouched. Start one, start five.
- When a task needs you, the bell flags its window. **`C-t n`** / **`C-t p`** jumps to the next or previous window *with a bell*, skipping the quiet ones. (In Claude Code, set `/config` → notifications to *terminal bell*.)
- Many projects? `optmux pick` lists every project you've started optmux in (● running) and drops you into the one you choose. Handy from a phone: it's the one command to remember.
- Too many windows? `optmux ~/myproject warp .` from inside a worktree opens a focused session with only that worktree's windows, which you can also open from an IDE's terminal. See [Warp sessions](docs/usage-warp.md).
- **`C-M-w`** opens the current branch's PR on GitHub, or the repo page if there's no PR yet.

A typical rhythm:

1. `C-M-c` → `:hotfix-login:` → describe the bug → move on.
2. `C-M-c` → `:try-dark-mode:` → describe the idea → move on.
3. `C-M-c` → `:bump-deps:` → describe the chore → move on.
4. A bell rings → `C-t n` → `C-M-g` to review → stage, discard a hunk, or make an example edit → tell the tool → `C-t n` to the next one.
5. Done? Ask the tool to open a PR, then `C-M-w` to look at it.

## Where to go next

- [optmux YAML config](docs/config.md): the full `+optmux:` reference (shortcuts, menus, plugins)
- [Using optmux](docs/usage.md), [`optmux pick`](docs/usage-pick.md), and [`optmux warp`](docs/usage-warp.md)
- [optmux Find](docs/usage-find.md), [optmux eXtract](docs/usage-extract.md), and [clipboard over SSH](docs/usage-extract.md#clipboard-and-osc-52)
- Make it yours with `~/.optmux.yaml`: personal shortcuts, plugins, `+env`, `+git_config`, and `+lazygit` settings for every session. See [Personal config](docs/config.md#personal-config-optmuxyaml).
