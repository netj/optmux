#!/usr/bin/env bash
# optmux tips — shows key binding cheatsheet and hints
set -euo pipefail

: ${OPTMUX_DIR:="$(cd "$(dirname "$0")/.."; pwd)"}
dismissed="$OPTMUX_DIR/tmux/.tips-dismissed"

# parse flags
force=false
for arg in "$@"; do
    [[ "$arg" == "--force" || "$arg" == "-f" ]] && force=true
done

# check suppression (skipped when --force)
if [[ "$force" != true ]]; then
    if [[ -e "$dismissed" ]]; then
        if grep -q '^forever$' "$dismissed" 2>/dev/null; then
            exit 0
        fi
        # skip if dismissed less than 7 days ago
        if find "$dismissed" -mtime -7 -print -quit 2>/dev/null | grep -q .; then
            exit 0
        fi
    fi
fi

# nerd font hint
nerd_font_tip=""
if ! fc-list : family 2>/dev/null | grep -qi 'Nerd Font'; then
    nerd_font_tip="
  [!] Install a Nerd Font for best experience
      https://www.nerdfonts.com"
fi

# terminal recommendation for OSC 52 support
#
# Shown by default; hidden only when the outer terminal is positively
# recognized as supporting OSC 52.  Inside tmux the pane's TERM_PROGRAM is
# overwritten with "tmux", so ask the server for the attached client's
# environment (see `update-environment` in tmux.conf) and terminal type —
# the latter also survives SSH, where TERM_PROGRAM does not.
if [[ -n "${TMUX:-}" ]]; then
    term_program=$(tmux show-environment TERM_PROGRAM 2>/dev/null) || term_program=""
    term_program="${term_program#TERM_PROGRAM=}"
    [[ "$term_program" == -* ]] && term_program=""  # "-VAR" means unset in the client env
    term_name=$(tmux display-message -p '#{client_termname}' 2>/dev/null) || term_name=""
else
    term_program="${TERM_PROGRAM:-}"
    term_name="${TERM:-}"
fi

osc52_known=false
case "$term_program" in
    ghostty|iTerm.app|WezTerm|WarpTerminal|kitty|alacritty|rio) osc52_known=true ;;
esac
case "$term_name" in
    *ghostty*|*kitty*|alacritty*|foot*|wezterm*|contour*|rio*) osc52_known=true ;;
esac

terminal_tip=""
if [[ "$osc52_known" != true ]]; then
    if [[ "$term_program" == "Apple_Terminal" || "${__CFBundleIdentifier:-}" == "com.apple.Terminal" ]]; then
        terminal_tip_why="  [!] Terminal.app has no OSC 52 support — clipboard sync will not work"
    else
        terminal_tip_why="  [!] Could not confirm this terminal supports OSC 52 clipboard"
    fi
    terminal_tip="
${terminal_tip_why}
      For clipboard integration, use a modern terminal:
      Ghostty: https://ghostty.org
      iTerm2:  https://iterm2.com
      Warp:    https://warp.dev"
fi

tips_content="$OPTMUX_DIR/tmux/tips-content.txt"

clear 2>/dev/null || true  # unknown TERM (common over SSH) must not abort the tips
cat <<EOF


                            optmux tips

  Prefix: Ctrl+T  (C-t)

EOF

if [[ -f "$tips_content" ]]; then
    cat "$tips_content"
else
    echo "  (no shortcuts configured)"
fi

cat <<EOF

  Install:  brew install netj/tap/wtcode   https://github.com/netj/wtcode
            brew install lazygit          https://github.com/jesseduffield/lazygit

  copy-mode yank auto-copies to system clipboard (OSC 52)
${nerd_font_tip}${terminal_tip}

  q/Enter: dismiss    d: dismiss for a week    D: dismiss forever    C-M-h: show again

EOF

# wait for user input
while true; do
    read -rsn1 key
    case "$key" in
        q|"")
            break
            ;;
        d)
            touch "$dismissed"
            break
            ;;
        D)
            echo "forever" > "$dismissed"
            break
            ;;
    esac
done
