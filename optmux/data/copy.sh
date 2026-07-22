#!/bin/sh

# Relay one tmux selection through exactly one explicitly configured backend.
# When neither variable is set, optmux leaves tmux-yank's native clipboard
# detection untouched and this helper is not invoked.

if [ -n "${OPTMUX_COPY_COMMAND:-}" ]; then
    exec /bin/sh -c "$OPTMUX_COPY_COMMAND"
fi

if [ -n "${OPTMUX_PBCOPY_SOCKET:-}" ]; then
    if ! command -v nc >/dev/null 2>&1; then
        echo "optmux: OPTMUX_PBCOPY_SOCKET requires nc" >&2
        exit 1
    fi
    if [ ! -S "$OPTMUX_PBCOPY_SOCKET" ]; then
        echo "optmux: clipboard relay socket is unavailable: $OPTMUX_PBCOPY_SOCKET" >&2
        exit 1
    fi
    exec nc -U "$OPTMUX_PBCOPY_SOCKET"
fi

echo "optmux: clipboard relay is not configured" >&2
exit 1
