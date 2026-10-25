# Plan: stable `SSH_AUTH_SOCK` for panes that outlive an ssh/mosh connection

Parked idea; not started. Related: the maintainer's bpm plugin `tmux-env-sync` (undecided whether to port it to optmux; probably not for now), and `shared-ssh-agent` (a different mechanism that replaces the connection's agent, independent of this).

## Problem (tmux 3.8, verified)

Default `update-environment` contains `SSH_AUTH_SOCK SSH_CONNECTION DISPLAY ...`; tmux copies those from the attaching client into the **session environment**, so only **new** panes/windows see the new value. Shells already running keep the old, now-dead socket. (`optmux-tmux.conf` appends `TERM_PROGRAM` with `set -ga update-environment`, so the defaults still apply.)

## Proposal: a per-project symlink, no shell hooks

- On every launch/attach (client side, in `setup_optmux_env` or `cmd_start`), refresh `$OPTMUX_DIR/ssh-agent.sock` as a symlink to the client's `SSH_AUTH_SOCK` (when set and a socket); leave the old target if the client has no agent.
- At server start, `set-environment -g SSH_AUTH_SOCK "$OPTMUX_DIR/ssh-agent.sock"` (in `optmux/data/tmux.conf`), and **remove `SSH_AUTH_SOCK` from `update-environment`** so a reattach doesn't overwrite it with the raw path. Existing shells hold the symlink path, which then always points at the newest connection's agent.
- Caveat to document: with no forwarded agent (or after the forwarding ssh session ends) the symlink dangles until the next attach. Make this opt-out-able through the `env:` YAML if it surprises anyone.
- Verify with real ssh agent forwarding, and with mosh + Blink if possible.

## Open question

Whether this belongs in optmux at all, or whether a `tmux-env-sync`-style approach (syncing more than the agent socket, e.g. `DISPLAY`, `SSH_CONNECTION`) covers it better.
