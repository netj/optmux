# Reviewing changes

With an agent per worktree, most of your time goes to reading what they did. optmux puts the review tools one key from any agent's pane, each opening in that pane's worktree:

- **`C-M-g`** lazygit, to skim the working tree, stage what you accept, and discard what you don't
- **`C-M-d`** the diff of the whole branch against the default branch, which is what the PR will contain
- **`C-M-w`** the branch's PR on GitHub, or the repo page if there is no PR yet
- **`C-M-f`** and **`C-M-x`** to jump to a file or pick text from the screen: [Find](usage-find.md) and [eXtract](usage-extract.md)

[The optmux Way](../OPTMUX-WAY.md#2-look-over-its-shoulder-watch-and-steer) shows how to turn these into a rhythm (the staging area as a checkpoint, a bell when an agent needs you). The rest of this page is what optmux sets up behind them.

## What it sets up

optmux's shortcuts open git review tools with an opinionated setup. It's configured in [`optmux-defaults.yaml`](../optmux-defaults.yaml) under [`env`](config.md#env), [`git_config`](config.md#git_config), and [`lazygit`](config.md#lazygit), and applied only to what the shortcuts start, through [`optmux-env`](config.md#optmux-env). Your dotfiles and your shells are left alone. See [The optmux Way](../OPTMUX-WAY.md) for how it fits into working with coding agents.

- **[lazygit](https://github.com/jesseduffield/lazygit)** (`C-M-g`): It opens on files when there are uncommitted changes or the branch has no diff against the default branch yet, and otherwise on the branch's commits. optmux's config is layered on top of yours. It adds `Ctrl-g` to diff against the default branch (`origin/HEAD`). Diffs render with delta, and clicking a line number opens it in your editor.
- **Clickable diff** (`C-M-d`, same as `Ctrl-g` in lazygit): what the branch changes against the default branch, rendered by delta in less, so you can scroll with the mouse and click a line number twice to edit it.
- **[delta](https://github.com/dandavison/delta)**: becomes git's pager (`core.pager`, `interactive.diffFilter`), with line numbers, `n`/`N` file navigation, moved-code coloring, and hyperlinked line numbers and commit hashes.
- **less**: mouse mode (`--mouse`) and an [OSC 8](https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda) hyperlink handler. Click a link once to select it and again to open it: `file://…#L<n>` opens `$VISUAL`/`$EDITOR` at that line, and `http(s)` links open your browser. Clicking links needs a recent `less` (Homebrew's; the formula depends on it).

## Helper scripts

Bundled helper scripts in `$OPTMUX_DIR/bin`, available in every pane:

| Script | What it does |
|---|---|
| `optmux-open-url URI` | Opens a hyperlink: files in your editor at the linked line, web links in the browser |
| `optmux-env CMD...` | Runs a command with optmux's settings. See [optmux-env](config.md#optmux-env) |
| `optmux-diff-base` | Diffs the branch against the default branch (`origin/HEAD`, else `origin/main`): a diffstat, then the patch, i.e. what a PR would contain (`C-M-d`, lazygit's `Ctrl-g`) |
| `optmux-find [PANE]` | Finds a file, a line (live `git grep`), a ctags tag, a language-server symbol, or tags and files ranked together (omni) and opens it in an editor split at that line (`C-M-f`). Resumes where you left off (mode, query, cursor). See [optmux Find](usage-find.md) |
| `optmux-extract [PANE]` | Picks lines, styled spans, URLs/paths/hashes/PR numbers/versions from a pane's screen and types or copies them (`C-t X`, `C-M-x`). See [optmux eXtract](usage-extract.md) |
| `optmux-gh-open` | Opens the current branch's PR on GitHub, or the repo page (`C-M-w`) |
