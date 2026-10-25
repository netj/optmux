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
    nerd_font_tip="  [!] Install a Nerd Font for best experience
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
        terminal_tip_why="  [!] Terminal.app has no OSC 52 support — clipboard sync will not work over SSH
      Workaround: ⌘R (View > Allow Mouse Reporting) off, then drag-select and ⌘C"
    else
        terminal_tip_why="  [!] Could not confirm OSC 52 support — clipboard sync may not work over SSH"
    fi
    terminal_tip="${terminal_tip_why}
      For clipboard integration, use a modern terminal:
      Ghostty: https://ghostty.org
      iTerm2:  https://iterm2.com
      Warp:    https://warp.dev"
fi

tips_content="$OPTMUX_DIR/tmux/tips-content.txt"

# Setext-style (markdown-like) heading: the text, then a line of = under it
heading() {
    printf '\n%s\n%s\n\n' "$1" "$(printf '%*s' "${#1}" '' | tr ' ' '=')"
}

# bundled_tool NAME DESCRIPTION URL [BREW-FORMULA]: one row, marked by whether it's installed
bundled_tool() {
    local name=$1 description=$2 url=$3 formula=${4:-$1} mark="✓" note=""
    if ! command -v "$name" >/dev/null 2>&1; then
        mark="✗"
        note="   (missing: brew install $formula)"
    elif [[ "$name" == less ]]; then
        # --mouse and clickable OSC 8 links need less 668+ (macOS ships 487)
        local less_version
        less_version=$(less --version 2>/dev/null | sed -n '1s/^less \([0-9]*\).*/\1/p')
        if [[ "${less_version:-0}" -lt 668 ]]; then
            mark="✗"
            note="   (too old for --mouse and links: brew install less)"
        fi
    fi
    printf '  %s %-8s %-40s %s%s\n' "$mark" "$name" "$description" "$url" "$note"
}

clear 2>/dev/null || true  # unknown TERM (common over SSH) must not abort the tips
printf '\noptmux tips\n===========\n'

heading "Keyboard Shortcuts"
echo "  Prefix: Ctrl+T (C-t)"
echo
if [[ -f "$tips_content" ]]; then
    cat "$tips_content"
else
    echo "  (no shortcuts configured)"
fi

heading "Bundled Tools"
bundled_tool wtcode 'for claude (or $WTCODE_CMD) (C-M-c)' https://github.com/netj/wtcode netj/tap/wtcode
bundled_tool lazygit "review and stage changes (C-M-g)" https://github.com/jesseduffield/lazygit
bundled_tool delta "syntax-highlighted, clickable diffs" https://github.com/dandavison/delta git-delta
bundled_tool less "mouse and clickable links in pagers" https://greenwoodsoftware.com/less
bundled_tool fzf "fuzzy finder (C-M-f)" https://github.com/junegunn/fzf
bundled_tool gh "GitHub CLI (C-M-w)" https://cli.github.com

plugins_tips="$OPTMUX_DIR/tmux/tips-plugins.txt"
if [[ -s "$plugins_tips" ]]; then
    heading "Plugins"
    cat "$plugins_tips"
fi

heading "Tips"
cat <<'EOF'
  optmux env CMD...  run CMD with optmux's delta/less/lazygit setup, e.g. optmux env git log -p
  In a diff, click a line number twice to open that line in $EDITOR
  copy-mode yank auto-copies to system clipboard (OSC 52)
EOF

if [[ -n "${nerd_font_tip}${terminal_tip}" ]]; then
    heading "Heads Up"
    [[ -n "$nerd_font_tip" ]] && echo "$nerd_font_tip"
    [[ -n "$terminal_tip" ]] && echo "$terminal_tip"
fi

cat <<'EOF'

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
