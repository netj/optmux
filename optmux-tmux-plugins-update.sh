#!/usr/bin/env bash
# optmux tmux plugin setup/update script
# Bootstraps TPM, installs missing plugins, and updates all plugins.
# Run manually to update: ./path/to/workflow.optmux.d/tmux/plugins-update.sh
set -euo pipefail

: ${OPTMUX_DIR:="$(cd "$(dirname "$0")/.."; pwd)"}
: ${TMUX_PLUGIN_MANAGER_PATH:="$OPTMUX_DIR/tmux/plugins"}
export TMUX_PLUGIN_MANAGER_PATH
export XDG_CONFIG_HOME="$OPTMUX_DIR"

# Shared git object cache for faster plugin clones across optmux projects.
# When the cache exists, GIT_TEMPLATE_DIR injects alternates so git clone
# borrows objects locally instead of re-downloading them.
_optmux_git_cache="${XDG_CACHE_HOME:-$HOME/.cache}/optmux/git-reference.git"
if [[ -d "$_optmux_git_cache/objects" ]]; then
    _git_tpl="${_optmux_git_cache%/*}/git-template"
    mkdir -p "$_git_tpl/objects/info"
    printf '%s\n' "$_optmux_git_cache/objects" >"$_git_tpl/objects/info/alternates"
    export GIT_TEMPLATE_DIR="$_git_tpl"
fi

tpm=netj/tpm  # XXX using netj/tpm fork; TODO switch back to tmux-plugins/tpm

if [[ ! -x "$TMUX_PLUGIN_MANAGER_PATH"/$tpm/tpm ]]; then
    echo "optmux: installing TPM ($tpm)..."
    git clone --reference-if-able "$_optmux_git_cache" \
        https://github.com/$tpm "$TMUX_PLUGIN_MANAGER_PATH"/$tpm
fi

# Pre-clone plugins in parallel so TPM's install_plugins finds them already present
# (parses @plugin entries from tmux.conf using TPM's own awk pattern)
# TODO migrate plugin list to optmux YAML config instead of parsing tmux.conf
_optmux_preclone() {
    local plugin="$1"
    local dest="$TMUX_PLUGIN_MANAGER_PATH/$plugin"
    [[ -d "$dest/.git" ]] && return
    git clone --reference-if-able "$_optmux_git_cache" --single-branch --recursive \
        "https://git::@github.com/$plugin" "$dest" >/dev/null 2>&1 &&
        echo "optmux:   cloned $plugin" ||
        echo "optmux:   failed to clone $plugin" >&2
}
if [[ -f "$OPTMUX_DIR/tmux/tmux.conf" ]]; then
    while IFS= read -r _plugin; do
        _optmux_preclone "$_plugin" &
    done < <(awk '/^[ \t]*set(-option)? +-g +@plugin/ {
        gsub(/'"'"'/,""); gsub(/"/,""); print $4
    }' "$OPTMUX_DIR/tmux/tmux.conf")
    wait
fi

if [[ -n "${TMUX:-}" ]]; then
    echo "optmux: installing/updating tmux plugins..."
    "$TMUX_PLUGIN_MANAGER_PATH"/$tpm/bin/install_plugins
    "$TMUX_PLUGIN_MANAGER_PATH"/$tpm/bin/update_plugins all
    # reload config to activate newly installed/updated plugins
    tmux source-file "$OPTMUX_DIR/tmux/tmux.conf"
fi

# Ensure tmux-fingers runtime dependencies are installed
# The plugin may use either a statically-linked binary (from GitHub releases) or
# a dynamically-linked one (from Homebrew). The Homebrew version needs bdw-gc, etc.
if [[ -d "$TMUX_PLUGIN_MANAGER_PATH/Morantron/tmux-fingers" ]]; then
    _fingers_bin="$TMUX_PLUGIN_MANAGER_PATH/Morantron/tmux-fingers/bin/tmux-fingers"
    if [[ -x "$_fingers_bin" ]]; then
        # Check if the binary can run (has all dependencies)
        if ! "$_fingers_bin" version &>/dev/null 2>&1; then
            # Binary exists but can't run - likely missing dependencies
            if command -v brew &>/dev/null && command -v otool &>/dev/null; then
                # Check if it needs bdw-gc (dynamically linked Homebrew binary)
                if otool -L "$_fingers_bin" 2>/dev/null | grep -q "bdw-gc"; then
                    echo "optmux: tmux-fingers requires runtime dependencies, installing..."
                    brew install bdw-gc pcre2 libevent libyaml 2>/dev/null || true
                fi
            fi
        fi
    fi
fi

# Populate shared cache from installed plugins for future projects
if [[ -d "$TMUX_PLUGIN_MANAGER_PATH" ]]; then
    [[ -d "$_optmux_git_cache" ]] || git init --bare "$_optmux_git_cache" 2>/dev/null
    for _d in "$TMUX_PLUGIN_MANAGER_PATH"/*/*; do
        [[ -d "$_d/.git" ]] || continue
        git -C "$_optmux_git_cache" fetch --quiet "$_d" \
            '+refs/*:refs/cache/'"${_d##*/}"'/*' 2>/dev/null || true
    done
fi
