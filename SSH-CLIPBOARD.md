# SSH Clipboard Relay

optmux normally leaves clipboard selection to tmux and `tmux-yank`, including
their native support for macOS, Linux, Wayland, X11, WSL, and Cygwin. No relay
is enabled by default.

Use this optional setup when a tmux session runs on a remote host but copied
text needs to reach the clipboard of the local Mac that opened the SSH session.
The example uses `pbcopy` on the local Mac without relying on OSC 52 support in
the terminal.

## Data flow

```text
remote tmux selection
  -> optmux copy helper
  -> owner-only socket created by SSH on the remote host
  -> encrypted SSH RemoteForward
  -> private local socket
  -> local pbcopy
  -> local Mac clipboard
```

Clipboard contents remain inside the local and remote user accounts plus the
existing SSH connection. The relay does not require an additional TCP listener,
API key, password, or SSH identity configuration.

## 1. Install the listener on the local Mac

Create `~/.local/bin/optmux-pbcopy-listener`:

```sh
mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/optmux-pbcopy-listener" <<'EOF'
#!/bin/zsh
set -eu

SOCKET_DIR="$HOME/Library/Caches/optmux"
SOCKET="$SOCKET_DIR/pbcopy.sock"

umask 077
mkdir -p "$SOCKET_DIR"
chmod 700 "$SOCKET_DIR"

while true; do
  rm -f "$SOCKET"
  /usr/bin/nc -lU "$SOCKET" | /usr/bin/pbcopy
done
EOF

chmod 755 "$HOME/.local/bin/optmux-pbcopy-listener"
```

The socket lives inside a directory accessible only to the local user. The
listener accepts clipboard bytes only from processes that can access that
directory.

## 2. Run the listener with launchd

Create `~/Library/LaunchAgents/com.optmux.pbcopy-listener.plist`. Replace every
`YOUR_LOCAL_USER` placeholder with the local macOS account name.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.optmux.pbcopy-listener</string>

    <key>ProgramArguments</key>
    <array>
      <string>/Users/YOUR_LOCAL_USER/.local/bin/optmux-pbcopy-listener</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/YOUR_LOCAL_USER/Library/Logs/optmux/pbcopy-listener.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/YOUR_LOCAL_USER/Library/Logs/optmux/pbcopy-listener.err</string>
  </dict>
</plist>
```

Load it:

```sh
mkdir -p "$HOME/Library/Logs/optmux"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.optmux.pbcopy-listener.plist"
```

If the service was already loaded, restart it with:

```sh
launchctl kickstart -k "gui/$(id -u)/com.optmux.pbcopy-listener"
```

Verify the private socket exists:

```sh
ls -l "$HOME/Library/Caches/optmux/pbcopy.sock"
```

## 3. Configure SSH on the local Mac

First, create a private parent directory on the remote host and print the
absolute remote home path:

```sh
install -d -m 700 "$HOME/.cache/optmux"
printf '%s\n' "$HOME"
```

Then add the forwarding rule to the relevant host entry in `~/.ssh/config` on
the local Mac. Replace `YOUR_REMOTE_USER`, `YOUR_REMOTE_HOME`, and the host
values. `YOUR_REMOTE_HOME` must be the absolute path printed above. OpenSSH
expands `%d` to the local home directory.

```sshconfig
Host your-remote
  HostName your.remote.host
  User YOUR_REMOTE_USER
  RemoteForward YOUR_REMOTE_HOME/.cache/optmux/pbcopy.sock %d/Library/Caches/optmux/pbcopy.sock
  StreamLocalBindMask 0177
  StreamLocalBindUnlink yes
  ExitOnForwardFailure yes
```

The mode-0700 remote parent directory prevents other remote users from reaching
the forwarding socket even on systems that do not enforce Unix-socket mode
bits. `StreamLocalBindMask 0177` provides an additional owner-only restriction
where supported. No private key path, password, token, or credential belongs in
this setup guide or in the optmux repository.

Reconnect after changing the SSH configuration:

```sh
ssh your-remote
```

## 4. Enable the relay in the remote tmux server

Inside the remote SSH session:

```sh
export OPTMUX_PBCOPY_SOCKET="$HOME/.cache/optmux/pbcopy.sock"
tmux set-environment -g OPTMUX_PBCOPY_SOCKET "$OPTMUX_PBCOPY_SOCKET"
tmux source-file "$OPTMUX_DIR/tmux/tmux.conf"
```

The tmux server needs its own environment entry because copy commands run in
the server, not in the current shell. Reloading the config activates the optmux
relay override. Removing the variable and reloading restores `tmux-yank`'s
native clipboard detection:

```sh
tmux set-environment -gu OPTMUX_PBCOPY_SOCKET
unset OPTMUX_PBCOPY_SOCKET
tmux source-file "$OPTMUX_DIR/tmux/tmux.conf"
```

To enable the relay automatically for future SSH shells, add the export to the
remote shell configuration only when an SSH connection is present:

```sh
if [[ -n "${SSH_CONNECTION:-}" ]]; then
  export OPTMUX_PBCOPY_SOCKET="$HOME/.cache/optmux/pbcopy.sock"
fi
```

## 5. Test end to end

On the remote host:

```sh
printf 'hello from remote optmux' | "$OPTMUX_DIR/tmux/copy.sh"
```

Paste on the local Mac. The clipboard should contain:

```text
hello from remote optmux
```

## Custom relay command

Advanced users may provide a trusted POSIX shell command instead of a Unix
socket. The command receives clipboard content on standard input:

```sh
export OPTMUX_COPY_COMMAND='your-copy-command --flag'
tmux set-environment -g OPTMUX_COPY_COMMAND "$OPTMUX_COPY_COMMAND"
tmux source-file "$OPTMUX_DIR/tmux/tmux.conf"
```

`OPTMUX_COPY_COMMAND` takes precedence when both relay variables are set. Its
failure is terminal; optmux does not replay clipboard contents into another
backend. Treat this variable as trusted local configuration because it is
executed by `/bin/sh -c`.

## Troubleshooting

Check the local service and socket:

```sh
launchctl print "gui/$(id -u)/com.optmux.pbcopy-listener"
ls -ld "$HOME/Library/Caches/optmux"
ls -l "$HOME/Library/Caches/optmux/pbcopy.sock"
tail -50 "$HOME/Library/Logs/optmux/pbcopy-listener.err"
```

Check the remote forwarding socket and tmux environment:

```sh
relay_socket="$HOME/.cache/optmux/pbcopy.sock"
ls -ld "$HOME/.cache/optmux"
ls -l "$relay_socket"
tmux show-environment -g OPTMUX_PBCOPY_SOCKET
```

Confirm the effective SSH forwarding configuration without printing private
key material:

```sh
ssh -G your-remote | grep -E '^(remoteforward|streamlocalbind)'
```

To unload the local listener:

```sh
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.optmux.pbcopy-listener.plist"
```
