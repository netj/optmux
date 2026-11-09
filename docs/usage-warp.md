# Focusing on one workdir

With a window per task, the project's session fills up with windows from many worktrees. `optmux warp` gives you a second session that shows only the windows of one workdir, so you can stay on a single task without the rest in the way.

```bash
optmux [DIR | YAML] warp [WORKDIR] [NAME]
```

It creates (or updates) a secondary session, named `<main-session>//<workdir-name>` unless you pass `NAME`, that links in only the windows from the main session whose panes are running in `WORKDIR` (defaults to the current directory). Run `optmux warp` from inside a worktree to get a session showing just that worktree's windows.

- Windows are linked, not copied, so the warp session stays in sync with the main session: the agent keeps running, and what you do in either place shows in both.
- Running it again attaches to the existing warp session, linking any windows that have appeared in that workdir since.
- The status line labels warp sessions `⚡warp`, so you can tell them apart from the main session.
- The main session must be running: start it first with `optmux`, and `optmux warp` tells you if it isn't.
