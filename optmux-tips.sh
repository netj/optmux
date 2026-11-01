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
    elif [[ "$name" == ctags ]] && ! ctags --version 2>/dev/null | grep -q Universal; then
        # macOS's own /usr/bin/ctags reads no file list and only knows C-like languages
        mark="✗"
        note="   (not universal-ctags: brew install universal-ctags)"
    elif [[ "$name" == less ]]; then
        # --mouse needs less 551+, clickable OSC 8 links 661+ (macOS ships 668; 702+ has the newer link protocol)
        local less_version
        less_version=$(less --version 2>/dev/null | sed -n '1s/^less \([0-9]*\).*/\1/p')
        if [[ "${less_version:-0}" -lt 661 ]]; then
            mark="✗"
            note="   (too old for --mouse and links: brew install less)"
        elif [[ "$less_version" -lt 702 ]]; then
            note="   (links via the old protocol; brew install less for the newer one)"
        fi
    fi
    printf '  %s %-8s %-40s %s%s\n' "$mark" "$name" "$description" "$url" "$note"
}

# the whole screen except the footer, as lines on stdout
render_tips() {
    printf '\noptmux tips\n===========\n\n'
    echo "Optimal, opinionated, batteries-included TMUX that's neat and easy for any project."
    echo "The optmux Way: https://github.com/netj/optmux/blob/main/OPTMUX-WAY.md"
    echo
    echo "TMUX runs many shells in one terminal, and keeps them alive when you detach."
    echo "New to TMUX? https://github.com/tmux/tmux/wiki/Getting-Started"

    heading "Keyboard Shortcuts"
    echo "  TMUX Prefix key: Ctrl+T (C-t). Press it, let go, then the key: C-t z zooms a pane."
    echo "  C-M-* (Ctrl+Alt, or Control+Option on a Mac) shortcuts need no prefix."
    echo
    if [[ -f "$tips_content" ]]; then
        cat "$tips_content"
    else
        echo "  (no shortcuts configured)"
    fi

    local custom_tips="$OPTMUX_DIR/tmux/tips-custom.txt"
    if [[ -s "$custom_tips" ]]; then
        heading "Your Shortcuts"
        cat "$custom_tips"
    fi

    heading "Mouse"
    cat <<'MOUSE'
  Click         a pane to focus it; a window name in the status bar to switch to it
  Drag          a pane border to resize; across text to select and copy it
  Double-click  selects a word
  Triple-click  selects a line
  Scroll        the wheel browses a pane's history (q, or scrolling to the end, leaves it)
  Right-click   a pane, window name, or the status bar for a menu of actions
MOUSE

    heading "Bundled Tools"
    bundled_tool wtcode 'for claude (or $WTCODE_CMD) (C-M-c)' https://github.com/netj/wtcode netj/tap/wtcode
    bundled_tool lazygit "review and stage changes (C-M-g)" https://github.com/jesseduffield/lazygit
    bundled_tool delta "syntax-highlighted, clickable diffs" https://github.com/dandavison/delta git-delta
    bundled_tool less "mouse and clickable links in pagers" https://greenwoodsoftware.com/less
    bundled_tool fzf "fuzzy finder (C-M-f)" https://github.com/junegunn/fzf
    bundled_tool ctags "tags for optmux Find (C-M-f)" https://ctags.io universal-ctags
    bundled_tool gh "GitHub CLI (C-M-w)" https://cli.github.com

    local plugins_tips="$OPTMUX_DIR/tmux/tips-plugins.txt"
    if [[ -s "$plugins_tips" ]]; then
        heading "TMUX Plugins"
        cat "$plugins_tips"
    fi

    heading "Good to Know"
    cat <<'EOF'
  (.) Each project is isolated: its own TMUX server, config, and saved sessions (in .NAME.optmux.d/)
  (.) One task = one worktree = one window. C-M-s/g/d/f open a shell/lazygit/diff/editor pane in its workdir
  (.) A window blinking red rang the bell (an agent wants you): C-t n / C-t p jump to the next / previous one
  (.) optmux pick  chooses among your projects (● running) and attaches; it returns when you detach
  (.) optmux env CMD...  runs CMD with optmux's delta/less/lazygit setup, e.g. optmux env git log -p
  (.) In a diff, click a line number twice to open that line in $EDITOR
  (.) copy-mode yank auto-copies to the system clipboard (OSC 52)
EOF
    # the OSC 52 warning goes right after the clipboard tip it belongs to; the Nerd Font note is last
    [[ -n "$terminal_tip" ]] && echo "$terminal_tip"
    [[ -n "$nerd_font_tip" ]] && echo "$nerd_font_tip"
}

footer="q/Enter: dismiss    d: dismiss for a week    D: dismiss forever    C-M-h: show again"

# a horizontal rule as wide as the terminal (at most 100 columns)
rule() {
    local cols
    cols=$(tput cols 2>/dev/null) || cols=80
    ((cols > 100)) && cols=100
    printf '%*s' "$cols" '' | sed 's/ /─/g'
}

# dismiss_key KEY: act on a dismissal key; succeeds when the screen should close
dismiss_key() {
    case "$1" in
        q|"") return 0 ;;
        d) touch "$dismissed"; return 0 ;;
        D) echo "forever" > "$dismissed"; return 0 ;;
    esac
    return 1
}

screen_rows() {
    local rows
    rows=$(stty size 2>/dev/null </dev/tty | cut -d' ' -f1) || true
    echo "${rows:-$(tput lines 2>/dev/null || echo 24)}"
}

# scroll_in_tmux: when the screen is taller than the pane, leave it in tmux's copy-mode at the top
# (instead of scrolled to the bottom), with key hints in this window's status bar entry.
# Mouse wheel, arrows, PgUp/PgDn and / search work as usual; q, or scrolling past the end, goes back
# to the footer prompt below.
scroll_in_tmux() {
    local pane=${TMUX_PANE:-}
    [[ -n "${TMUX:-}" && -n "$pane" ]] || return 0
    tmux set-window-option -t "$pane" window-status-current-format \
        ' #I:tips | wheel/↑/↓/PgUp/PgDn scroll · / search · q done reading ' 2>/dev/null || return 0
    # expand $pane now: it's a local, gone by the time the trap runs at exit
    trap "tmux set-window-option -u -t '$pane' window-status-current-format 2>/dev/null" EXIT
    tmux copy-mode -e -t "$pane" 2>/dev/null || return 0
    tmux send-keys -t "$pane" -X history-top 2>/dev/null || return 0
    while [[ "$(tmux display-message -p -t "$pane" '#{pane_in_mode}' 2>/dev/null)" == 1 ]]; do
        sleep 0.2
    done
    tmux set-window-option -u -t "$pane" window-status-current-format 2>/dev/null || true
}

lines=()
while IFS= read -r line; do lines+=("$line"); done < <(render_tips)

clear 2>/dev/null || true  # unknown TERM (common over SSH) must not abort the tips
printf '%s\n' "${lines[@]}"
printf '\n%s\n%s\n\n' "$(rule)" "$footer"
if [[ -t 0 && -t 1 ]] && ((${#lines[@]} + 5 > $(screen_rows))); then
    scroll_in_tmux
fi
while true; do
    read -rsn1 key
    dismiss_key "$key" && break
done
