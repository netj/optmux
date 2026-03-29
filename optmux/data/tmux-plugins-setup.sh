#!/usr/bin/env bash
# optmux tmux plugin setup/update script
# Bootstraps TPM and installs/updates all plugins defined in tmux.conf.
# Run manually to update: ./path/to/workflow.optmux.d/tmux-plugins-setup.sh
set -euo pipefail

: ${OPTMUX_DIR:="$(cd "$(dirname "$0")"; pwd)"}
: ${TMUX_PLUGIN_MANAGER_PATH:="$OPTMUX_DIR/tmux-plugins"}
export TMUX_PLUGIN_MANAGER_PATH

tpm=netj/tpm  # XXX using netj/tpm fork; TODO switch back to tmux-plugins/tpm

if [[ ! -x "$TMUX_PLUGIN_MANAGER_PATH"/$tpm/tpm ]]; then
    echo "optmux: installing TPM ($tpm)..."
    git clone https://github.com/$tpm "$TMUX_PLUGIN_MANAGER_PATH"/$tpm
fi

if [[ -n "${TMUX:-}" ]]; then
    # inside tmux: let tpm install plugins in background
    "$TMUX_PLUGIN_MANAGER_PATH"/$tpm/bin/install_plugins
else
    # outside tmux (first run from optmux cli): install plugins with visible output
    echo "optmux: installing tmux plugins..."
    "$TMUX_PLUGIN_MANAGER_PATH"/$tpm/bin/install_plugins
fi
