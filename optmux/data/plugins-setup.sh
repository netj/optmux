#!/usr/bin/env bash
# optmux tmux plugin setup/update script
# Bootstraps TPM, and installs/updates plugins when run inside tmux.
# Run manually to update: ./path/to/workflow.optmux.d/tmux/plugins-setup.sh
set -euo pipefail

: ${OPTMUX_DIR:="$(cd "$(dirname "$0")/.."; pwd)"}
: ${TMUX_PLUGIN_MANAGER_PATH:="$OPTMUX_DIR/tmux/plugins"}
export TMUX_PLUGIN_MANAGER_PATH
export XDG_CONFIG_HOME="$OPTMUX_DIR"

tpm=netj/tpm  # XXX using netj/tpm fork; TODO switch back to tmux-plugins/tpm

if [[ ! -x "$TMUX_PLUGIN_MANAGER_PATH"/$tpm/tpm ]]; then
    echo "optmux: installing TPM ($tpm)..."
    git clone https://github.com/$tpm "$TMUX_PLUGIN_MANAGER_PATH"/$tpm
fi

if [[ -n "${TMUX:-}" ]]; then
    # inside tmux: tpm can query the server, so install/update plugins
    echo "optmux: installing/updating tmux plugins..."
    "$TMUX_PLUGIN_MANAGER_PATH"/$tpm/bin/install_plugins
    # reload config to activate newly installed plugins
    tmux source-file "$OPTMUX_DIR/tmux/tmux.conf"
fi
