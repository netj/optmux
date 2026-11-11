# OPTMUX eXtract: repeat and copy what you see

`C-t X` (or `C-M-x`, without the prefix) opens OPTMUX eXtract, a picker over the pane's screen and scrollback. `Tab` selects several, `Enter` types them into the pane, `C-y` copies them. Lines keep their screen order and duplicates, so a multiline script survives (extrakto, which this replaces, dedups and reorders).

- **`C-M-x`** again (the key that opened the picker) switches between **lines** and **spans**. Spans are the runs of text the program colored or styled (the command, path or name worth copying; one the program wrapped onto the next line in the same style is joined back when it clearly filled the line), mixed in screen order with the patterns it did not style (URLs, paths, file names with an optional `:line:col`, commit hashes, PR or issue numbers like `#234`, quoted text (`'x'`, `"x"`, `` `x` ``, GNU `` `x' ``), semver versions). The last one used is remembered.
- **`C-y`** copies by the method **`C-t`** cycles: `osc52` (eXtract writes an OSC 52 escape to its own terminal and tmux relays it, so it reaches your local clipboard over SSH too), `native` (`pbcopy`, `wl-copy`, `xclip` or `xsel`) or `buffer` (the tmux buffer only). Also remembered. Either way the tmux buffer holds the text afterwards.
- **`C-e`** edits the picks in `$EDITOR` (`vi` if unset) in a new, zoomed pane above the one you came from (as OPTMUX's other shortcuts open theirs; quitting the editor brings back the layout, or the zoom you had), in its current directory. File names and paths that exist open as files, at their `:line:col` when they have one (vim and nvim jump there, `-o` giving each of several files its own window; nano and emacs take `+LINE` per file, Helix `file:line:col`, VS Code `-g`), several picks in one editor; relative ones are taken from that directory, and URLs are left to `C-o`. Anything else (a command, quoted text, lines, a hash) is written to a temporary file that opens instead, and is deleted when you quit the editor.
- **`C-o`** opens each pick by its kind: on macOS a file is revealed in Finder, a directory opened and a URL sent to the browser (`xdg-open` elsewhere); a commit hash or `#234` opens on GitHub with `gh browse`, when `gh` is installed and the pane is in a git repository. What can't be opened (or a path that doesn't exist) is left alone, with a short message saying why.
- **`M-r`** cycles how paths (that exist) are typed and copied: **shown** as on the screen, **relative** to the project root (the pane's git repository, else its directory) or **absolute**; a `:line:col` stays. Remembered like the copy method (`@optmux-extract-paths`).
- **Where you were is remembered**, per filter: eXtract opens on the query you left (leaving with `Esc` counts, and an emptied query stays empty), with the cursor on the item you last picked, and `M-p` steps back through that filter's earlier queries before it, each with the cursor on the item you picked then, so the `bash`, `.tmp/` or pattern you use often is a few keystrokes away (`M-n` goes forward again to a fresh, empty start). A query that `M-p` recalls and that matches nothing on the screen now is skipped; the one eXtract opens on stays even then (`C-u` clears it). Spans in plain grey (a coding tool's status lines and hints) are left out, so they don't crowd the list; bold or highlighted ones stay. To find spans starting with a bang, type `^!` or `'!`: a lone `!` is fzf's negation, which matches everything. `C-u` clears the query. The **spans** filter draws each pattern kind with an icon (🔗 URL, 📁 path, 📄 file name, 💬 quoted text, #️⃣ commit hash, 🔀 PR or issue number, 🏷️ version) and the program's own styled runs with 🎨, in the style of `+icons` (`nerd` by default; shown here as emoji) like Find.
- **`C-f`, `C-g`, `C-M-f`** look the selection up in the project instead of typing it: the picks (or, with nothing matching, the text you typed in the filter) become the query of [OPTMUX Find](usage-find.md), which continues in this same popup: **`C-f`** in the files, **`C-g`** by grep, **`C-M-f`** in omni (tags, symbols and files). Pick an error's path, a function name or a phrase from the screen, then jump to where it lives (a `:line:col` after a path is left off, since a file name has none).
- Several picks go on one line separated by spaces, except lines mode (always one pick per line) and picks that themselves contain whitespace, such as commands in spans mode, which each get their own line.
- Picks are pasted as a bracketed paste, so a shell (or Claude Code) takes several lines as one paste. A program that doesn't ask for bracketed paste (plain `cat`, some REPLs) receives each newline as `Enter`.
- These are kept as tmux options on the project's server (`@optmux-extract-filter`, `@optmux-extract-copy`, `@optmux-extract-paths`), so they last until it stops.

## Clipboard and OSC 52

OPTMUX ships [tmux-yank](https://github.com/netj/tmux-yank) and sets `set-clipboard on` + `allow-passthrough on`, so yanking in copy-mode lands on your system clipboard. Locally that goes through `pbcopy`/`xclip`. **Over SSH, [OSC 52](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands) is the only mechanism** — the remote tmux emits an escape sequence and your local terminal writes it to the clipboard, with no relay, agent, or daemon in between.

### macOS Terminal.app has no OSC 52 support

Local copying still works, but **copying from a remote OPTMUX session over SSH will not reach your pasteboard** — Terminal.app discards the escape sequence, and no tmux configuration can change that. OPTMUX deliberately doesn't ship a clipboard relay to work around it; that means a socket on your laptop accepting arbitrary bytes into your pasteboard, to replace what modern terminals already do natively.

**Workaround:** turn off **View → Allow Mouse Reporting** (`⌘R`), or hold `Fn`, to hand the mouse back to Terminal and drag-select with its own selection, then `⌘C`. `⌘R` again returns the mouse to tmux. You get only what's on screen, and the selection cuts across split panes — zoom first with `prefix + z`.

**Better:** use a terminal that supports OSC 52 — [Ghostty](https://ghostty.org), [iTerm2](https://iterm2.com), [Warp](https://warp.dev), [kitty](https://sw.kovidgoyal.net/kitty/), [WezTerm](https://wezterm.org), or [Alacritty](https://alacritty.org). The tips screen (shown on first attach, or `C-M-h`) nags about this unless it can confirm your terminal, using the attached client's `TERM_PROGRAM` and terminal type — over SSH only the latter survives, so `xterm-ghostty` and friends are still recognized on remote hosts.

## Leaving out the chrome

The spans filter skips plain grey text, and what a coding tool draws on every screen in color (Claude Code's mode line, its always-listed `/` commands, "Jump to bottom" and "N new messages"). `+ignore_spans` under `+find:` is that list: groups of regular expressions, each matched against a whole span or pattern match (case-insensitive). The defaults live in `optmux-defaults.yaml`; as with `+ignore_files`, setting a group replaces its list, `[]` drops it, and a new group adds to the rest:

```yaml
+optmux:
  +find:
    +ignore_spans:
      my_tool:
      - '>>> ready'
      - \d+ files changed
      claude_code_commands: []
```

A pattern ending in `:` is written `[:]`, or YAML reads it as a key.
