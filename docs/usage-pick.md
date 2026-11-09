# Picking among many projects

Every project has its own TMUX server, so nothing shows what is running across projects, or on a host you ssh or mosh into. `optmux pick` is the one command to remember: it lists every project you have started OPTMUX in, running or not, and attaches to the one you choose.

```bash
optmux pick [--list] [--live] [-1] [--title TITLE] [--title-without-hostname] [QUERY]
```

OPTMUX remembers each project it was started in (`${XDG_STATE_HOME:-~/.local/state}/optmux/projects.tsv`), and `optmux pick` lists them with [fzf](https://github.com/junegunn/fzf) (a numbered menu if fzf is missing): ● has a running session, ○ doesn't; running ones come first, most recently active on top. The preview shows the session's windows and their directories, with a `[bell]` on those that rang. The prompt names the machine (`optmux pick@myhost>`), handy when you ssh or mosh into several (`--title-without-hostname` leaves it out).

- `Enter` attaches to the project's session, starting it if needed
- `C-x` stops the highlighted project's session, or forgets the project if it isn't running, after a `y/N` (projects whose directory or YAML is gone are dropped automatically)
- `Esc` or `C-d` quits
- `QUERY` pre-filters; `-1` picks without asking when exactly one project matches; `--live` hides projects that aren't running; `--list` prints TSV (`state kind target session socket`) for scripts

`optmux pick` is one action: it returns after you detach or exit (status 0), so a shell wrapper can offer to pick again. Exit status is 130 if you cancelled, and 1 if there was nothing to pick.

## Sessions that survive restarts

A project listed as ○ isn't lost: OPTMUX ships [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect), so a session can come back after a reboot or a crash.

- **`C-t C-s`** — save the current session (windows, panes, working directories)
- **`C-t C-r`** — restore the last saved session

Because each project has its own `resurrect/` folder (see [What OPTMUX generates](config.md#what-optmux-generates)), saves never mix between projects. Save project A, then project B — restoring either one brings back only its own layout.
