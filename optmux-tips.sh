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
terminal_tip=""
if [[ "$__CFBundleIdentifier" == "com.apple.Terminal" ]]; then
    terminal_tip="
  [!] For clipboard integration (OSC 52), use a modern terminal:
      Ghostty: https://ghostty.org
      iTerm2:  https://iterm2.com
      Warp:    https://warp.dev"
fi

tips_content="$OPTMUX_DIR/tmux/tips-content.txt"

clear
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
