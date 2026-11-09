# Focusing on one workdir

With a window per task, the project's session fills up with windows from many worktrees. `optmux warp` gives you a second session that shows only the windows of one workdir, so you can stay on a single task without the rest in the way. And because those windows are *shared* with the main session, it is also how you take a task's window into another terminal or an IDE.

## Why it exists

tmux attaches a terminal to a *session*, not to a window, and a window normally lives in just one session. That leaves two gaps once you run many tasks:

- **No way to focus.** Everything is in the project's one session, so the status line and the window list carry every task, when you want the current task's coding tool, lazygit, shell, and editor.
- **Nothing to point another terminal at.** An IDE's terminal or a second terminal app can attach to a session, but it can't pick up one window, and starting a new session there would only give you fresh shells, not the running ones.

`optmux warp` closes both with a second session that *links* the task's windows instead of copying them. It is a view onto the same running windows, which is why it can be narrow (one workdir) and shared (any terminal) at once.

## Using it

```bash
optmux [DIR | YAML] warp [WORKDIR] [NAME]
```

`DIR | YAML` names the project (the same first argument as for `optmux`), and `WORKDIR` (default: the current directory, resolved from where you run the command) picks the windows. For a project at `~/myproject`, from inside one of its worktrees:

```bash
optmux ~/myproject warp .
```

That creates (or updates) a secondary session, named `<main-session>//<workdir-name>` unless you pass `NAME`, and attaches to it. It links in only the windows from the main session whose panes are running in `WORKDIR`.

- Windows are linked, not copied, so the warp session stays in sync with the main session: the tools keep running, and what you do in either place shows in both.
- Running it again attaches to the existing warp session, linking any windows that have appeared in that workdir since.
- The status line labels warp sessions `⚡warp`, so you can tell them apart from the main session.
- The main session must be running: start it first with `optmux ~/myproject`, and `optmux warp` tells you if it isn't.

## Sharing a window outside optmux

A warp session is an ordinary session on the project's tmux server, so any terminal can attach to it, not only the one running your main optmux session. Run the warp from a [cmux](https://cmux.com) workspace, an IDE's integrated terminal, or another terminal tab, and it gets the task's window live, while your main session keeps its full view:

```bash
# in the integrated terminal of an editor opened on the worktree
optmux ~/myproject warp .
```

- **Shared, not mirrored.** It is the same window in both places: type in either, and nothing is restarted or duplicated. Detaching (`C-t d`) closes only that terminal's view; the task keeps running in the main session.
- **A terminal per workdir.** Give each worktree its own tab or workspace running `optmux ~/myproject warp .` from that worktree, and each one shows only that task's windows: the coding tool, plus the lazygit, shell and editor panes you opened beside it.
- **Same optmux.** The warp session is still optmux, so reviewing, [Find](usage-find.md), and [eXtract](usage-extract.md) work the same inside an IDE terminal, except that some IDEs claim Ctrl+Alt combinations for themselves, so a `C-M-` key may need rebinding on one side.
- **Remote too.** Over ssh or mosh, run it on the host: it attaches to that host's session.
