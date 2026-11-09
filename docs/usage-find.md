# OPTMUX Find: open a file, line or tag

`C-M-f` opens a picker over the project with five sources, and opens the pick in your editor (`$VISUAL`, `$EDITOR`, else `vim`) in a split beside your coding tool, at the matching line:

- **`C-o` omni** (the default): tags, language-server symbols and file paths in one list, ranked together, so the stronger match is higher whichever it is (a file named for your query outranks a tag that only loosely contains it; a tag or symbol is matched on its name, a file on its path). A symbol the servers know replaces the tag for the same line. Rows are drawn alike in every source (see below); the best 100 are shown. Grep stays on its own key, `C-g`.
- **`C-f` files**: `git ls-files` (tracked and untracked) first, then every other file `find` turns up, ignored ones included (scratch scripts, local notes), minus what `+find` → `+ignore_files` names (`node_modules`, `.venv`, caches, OPTMUX's own `.optmux.d`; see below). Just `find` outside a repo.
- **`C-g` grep**: live `git grep`, re-run on every keystroke, smart-case.
- **`C-t` tags**: OPTMUX's own index, built the way a `post-commit` hook would (`git ls-files | ctags -L -`, minus `+ignore_tags` under `+find`), the first time, and refreshes it in the background whenever the commit or the tracked files that changed differ, so opening the picker never waits for it. Until the very first build is done (minutes in a huge project) the list is a single ⏳ row and fills in by itself when ctags finishes; later refreshes keep using the old tags until the new ones are ready. It needs [universal-ctags](https://ctags.io) (`brew install universal-ctags`, a dependency of the Homebrew formula; exuberant ctags should do too, minus line numbers it can find from patterns). macOS's own `/usr/bin/ctags` does not: it takes no file list and only knows C-like languages. It is stored per project in `.optmux.d/find/`. A `tags` file in the project is never read, whatever it holds (a hook's options, JSON keys, patterns without line numbers: the picker depends on what the index holds); `ctags` runs in the project root, so its `.ctags.d` still applies, and `+ignore_tags` (under `+find`) is the setting for what to leave out. To use the same tags in your editor, `optmux-find --tags-path` prints the file (building it first if there is none yet, and exiting 1 when there is no project; it prints a copy with absolute paths, since an editor reads them relative to the tags file's directory): in vim, `:let &tags .= ',' . escape(trim(system('optmux-find --tags-path 2>/dev/null')), ' ,')`. It resolves the same way inside and outside OPTMUX only where `$OPTMUX_DIR` is the same, so run it from a pane of the project's OPTMUX session.
- **`C-l` lsp**: symbols from the project's language servers, searched as you type (see [Language servers](#language-servers-c-l) below).

## Switching, history and recency

`C-M-f` again (the key that opened it) cycles the sources, or jump straight to one with its key. Switching carries the text you typed along, so what you searched in omni can be tried as grep, then as tags (the same text means different things in each: fuzzy for omni, files and tags, a regex or plain text for grep). Each source keeps its own record, since a fuzzy file name, a regex and a tag name are different kinds of query. Opening the picker afresh resumes the last source with its own last query and the cursor on the entry it was on; `C-u` clears the query for a new search, and `M-p` recalls that source's earlier queries (`M-n` goes forward; `C-p` and `C-n` still move the cursor; `M-p`/`M-n` need your terminal to send Option as Meta, e.g. "Use Option as Meta key" in macOS Terminal.app), including ones you left with `Esc` or a switch. Grep results are sorted by file and line.

**Slow sources never hold the list up.** Whatever is still being worked on (the first ctags run, language servers answering) shows as an ⏳ row at the very bottom, below every result, so you can tell "still looking" from "nothing found"; the list reloads itself when the answer arrives, and what is already there (files, tags) can be used meanwhile.

**Recency.** What you open is remembered per project, and pulls those files and tags up: with an empty query the lists start with what you opened last (like ctrl-p's most-recently-used list). In omni the boost is bounded: the most recent file or tag may jump up to 20 places, the next one a place less, so a strong match still beats a weak recent one. Files and tags are matched by fzf itself, so there recency decides ties and the empty list, but cannot lift a weaker match over a stronger one. Grep order stays by file and line. State is per project and per source, in `.optmux.d/find/` (`SOURCE.last`, `SOURCE.history`, `recent.json`, `lsp.log`; `~/.local/state/optmux/` outside OPTMUX); the source is the tmux option `@optmux-find-mode`.

## Language servers (`C-l`)

`C-l` asks your language servers for `workspace/symbol`, so it sees what the compiler sees: methods and classes in the right scope, not just what a regex or ctags could pick out. Nothing to set up if the server is installed:

- OPTMUX looks at the files git tracks and picks the languages that have a few of them (python, typescript/javascript, go, rust, c/c++, lua, bash out of the box), then starts the first installed server of each. One hub process per project keeps them running between keystrokes (it exits after 30 idle minutes, `OPTMUX_LSP_IDLE` seconds to change), and logs to `.optmux.d/find/lsp.log`.
- Scripts without an extension count too: a tracked file whose first line is `#!/usr/bin/env python3` (or `node`, `bash`, `lua`, ...) is told to the server of that language, up to 50 per language. (Servers only look at files with the language's extension, so a script like `bin/tool` would otherwise never show its classes and functions.) Files found not to be scripts are not read again for a day (unless they changed).
- A language with files but no server installed shows a ⚠️ row with its install command, e.g. `go: no language server installed.  Enter runs: brew install gopls`. **Enter on that row runs the install** in the picker's own popup (so you can watch it, answer a prompt), then returns to the same picker, where the servers show up within seconds of it finishing. The command offered is the first one whose installer is on the machine: `+install` may be a list of alternatives (`brew`, `uv tool`, `npm`, ...). `optmux-lsp install` does the same from a shell (asking first); `optmux-lsp status` shows what runs; `optmux-lsp stop` stops the project's servers. ⏳ rows say a server is still starting, 💬 rows say what went wrong; Enter on those does nothing.
- The first search after a server starts may say it is starting (rust-analyzer and the like take a while to index). Some servers need a project description: clangd needs a `compile_commands.json`, and finds nothing without one.

Choose servers in your `optmux.yaml` (project or `~/.optmux.yaml`), per language. `+servers` replaces the preference list, the first installed one is used; `+command` alone is a one-server shorthand; `+enabled: false` turns a language off. `+open_first_file: true` opens one file after the server starts, for servers that find their project from it (typescript and c do that by default):

```yaml
+optmux:
  +find:
    +lsp:
      python:
        +servers:
        - +command: ty server
          +install: uv tool install ty
        - +command: basedpyright-langserver --stdio
          +install: brew install basedpyright
      ruby:
        +extensions:
        - rb
        +command: ruby-lsp
        +install: gem install ruby-lsp
      bash:
        +enabled: false
```

The bundled defaults are under `+find` → `+lsp` in [`optmux-defaults.yaml`](../optmux-defaults.yaml). Omni asks the servers too, but only those already running, within a second, so typing never waits for a server that is still starting.

## Leaving files out

`+ignore_files` (under `+find:`) lists what the file list leaves out, as glob patterns matched against each name in a path (`node_modules` skips that directory, `*.pyc` the files), in groups. Setting a group replaces its list, `[]` drops it, and a new group adds to the rest; `.git` is always skipped:

```yaml
+optmux:
  +find:
    +ignore_files:
      dependencies:  # replaces the bundled list
      - node_modules
      - .venv
      - vendor
      caches: []  # look inside caches too
      scratch:  # a group of your own
      - "*.log"
      - tmp
```

`+ignore_tags` is the same for the tags index (`C-t`, and the tags in `C-o`): ctags makes a symbol of every key in a JSON file, so a few big data files or generated bindings can mean hundreds of thousands of rows and a list that takes minutes to load. The defaults leave out `*.json`, `*.csv`, lockfiles, `generated` directories and minified files; set a group to `[]` to index them after all. Changing the patterns re-indexes on the next open.

## Preview and rows

A **preview** of the selected row sits beside the list: the file around the matching line, marked (with [bat](https://github.com/sharkdp/bat), or `batcat` on Debian and Ubuntu, if you have it: it highlights syntax), or what an install row will do. `C-/` (or `^_`, which is what macOS Terminal.app sends for `ctrl-/` and `ctrl--`) toggles it; while it is on, grep's list shows just `path:line` (the preview has the text); it is hidden when the terminal is under about 100 columns wide; `+preview: false` (under `+find:`) turns it off (`OPTMUX_FIND_PREVIEW=0` does so for one run). Long lines are cut, not wrapped, so the marked line stays in view.

**How a row reads.** The same for files, matches, tags and symbols: a dim letter for the source (`F` file, `G` grep match, `T` tag, `L` language-server symbol), an icon for what it is, the name, then where: `file:line`, and the directory in dim parens:

```
T⚡️ build_tags  optmux-find:172  (optmux/data/bin)
L⚡️ Gui.Layout  layout.go:12  (pkg/gui)
F📄 layout.go  (pkg/gui)
G🔍 layout.go:12  (pkg/gui)
```

The icon is the kind: ⚡️ function or method, 🧩 class, struct or interface, 📖 module or namespace, 📦 package, 🏷️ variable, constant or field, 🔖 anything else, 📄 file, 🔍 grep match. Tags and symbols share them (ctags is asked for full kind names, so a tag's kind is not a bare letter), and a language server's package qualifier is left off the name (gopls's `github.com/org/repo/pkg/gui.Gui.Layout` is shown `Gui.Layout`: the file is next to it). The first lines of the preview say it all again, in words: the name, its kind and source, and the full directory (and the container, if the server gave one).

Nerd Font glyphs are the default, so the terminal needs a [Nerd Font](https://www.nerdfonts.com) (without one the icons show as boxes: set `+icons: emoji`, `text` or `none`). `+icons` (at the top of the `+optmux:` section, for eXtract too) switches them: `emoji` renders in any terminal, also where OPTMUX runs on a machine that cannot tell what font your terminal has (mosh, SSH), `text` uses letters in Find (`f` function, `t` type, `m` module, `p` package, `v` value, `o` other, `d` directory, `-` file, `/` match) and words in eXtract (`url`, `path`, `quot`, `pr`, `line`, ...), and `none` draws no icon at all:

```yaml
+optmux:
  +icons: nerd
  +find:
    +preview: false
```
