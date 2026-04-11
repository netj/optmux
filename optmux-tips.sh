#!/usr/bin/env bash
# optmux tips — shows key binding cheatsheet and hints
set -euo pipefail

: ${OPTMUX_DIR:="$(cd "$(dirname "$0")/.."; pwd)"}
dismissed="$OPTMUX_DIR/tmux/.tips-dismissed"

# check suppression
if [[ -e "$dismissed" ]]; then
    if grep -q '^forever$' "$dismissed" 2>/dev/null; then
        exit 0
    fi
    # skip if dismissed less than 7 days ago
    if find "$dismissed" -mtime -7 -print -quit 2>/dev/null | grep -q .; then
        exit 0
    fi
fi

# nerd font hint
nerd_font_tip=""
if ! fc-list : family 2>/dev/null | grep -qi 'Nerd Font'; then
    nerd_font_tip="
  [!] Install a Nerd Font for best experience
      https://www.nerdfonts.com"
fi

clear
cat <<EOF


                            optmux tips

  Prefix: Ctrl+T  (C-t)

  Workflow:  C-M-c  wtcode   or   C-M-f  find file to open editor
          -> C-M-g  lazygit  to check diff/commits
          -> C-M-o  cycle between panes   or   q  to return
          -> C-M-s  shell in same dir (run tests, one-off commands)

  Install:  brew install netj/tap/wtcode   https://github.com/netj/wtcode
            brew install lazygit          https://github.com/jesseduffield/lazygit

  C-t C-t   last window        C-M-z         quick toggle zoom
  C-t C-c   new window         C-M-\\         last pane
  C-t C-n/p next/prev window   C-M-o         prev pane + zoom
  C-t n/p   next/prev w/ bell
  C-t z     toggle zoom        C-t F         fingers (copy URLs/paths/hashes)
  C-t o     cycle panes        C-t h/j/k/l   navigate panes
  C-t R     reload config

  C-t t     send prefix to nested tmux
  C-t T     swap prefix (for nested tmux)
  copy-mode yank auto-copies to system clipboard (OSC 52)
${nerd_font_tip}

  q/Enter: dismiss    d: dismiss for a week    D: dismiss forever

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
