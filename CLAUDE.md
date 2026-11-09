# optmux — Claude Code Notes

## Project

- Python CLI tool wrapping tmuxp, packaged with `uv`
- Entry point: `optmux/cli.py` → `optmux.cli:main`
- Build system: `uv_build` (see `pyproject.toml`)

## Docs Layout

- `README.md` is the front door (pitch, key → outcome table, get started, then short paragraphs pointing on); keep it short and put details in `docs/`: `usage.md` (feature overview + CLI reference), `usage-review.md`, `usage-extract.md` (with clipboard/OSC 52), `usage-find.md`, `usage-pick.md` (with tmux-resurrect), `usage-warp.md`, `config.md` (`+optmux:` reference, what optmux generates, environment variables), `development.md`, `troubleshooting/`. `OPTMUX-WAY.md` stays at the top level.
- README is also the PyPI description, so its links use absolute `https://github.com/netj/optmux/blob/main/...` URLs; links within `docs/` stay relative. Its tagline line is read by `tests/test_tips_script.py`.

## Wording

- **Don't call AI coding tools "agents"** (README, `docs/`, tips, messages, comments). The maintainer avoids personifying AI, following Jaron Lanier's framing of AI as a new way for people to collaborate at massive scale rather than as a being of its own. Say "AI coding tool" or "coding tool" for the software, "task" when the sentence is really about a window or worktree, and "Claude Code" for a concrete example. The one deliberate exception is the sentence in `OPTMUX-WAY.md` about leading "your brilliant AI agents like an insightful mentor"; keep any other use to a minimum in marketing copy (README, The OPTMUX Way). "ssh-agent" and the like are fine.
- **Write OPTMUX in capitals in prose**, like TMUX ("The OPTMUX Way", "OPTMUX Find", "OPTMUX's settings"). Commands (`optmux`), file names, paths, URLs, package names, and `optmux-*` scripts stay lowercase.
- **Say the `C-t` prefix early**: it is not tmux's default `C-b`, and readers should not have to hunt for it.

## YAML Style

- **`+` marks optmux's own words** (`+optmux:`, `+shortcuts:`, `+command:`, `+find:`, `+tip_url:`); names the user picks (shortcut keys, plugins, env vars, languages, `ignore_files` groups) stay bare, and so does everything under `+lazygit:` (lazygit's schema). Use it in every example, test fixture, and message. The bare `optmux:` form still loads, with a deprecation warning (`read_optmux_section` in `cli.py`); new reserved words go in the `KNOWN_*` sets there.
- README and `docs/` YAML examples use indentless lists (`yq --indentless` style): the `-` sits at the same indent as its parent key, not nested under it.
- **Prefer YAML block scalars over quoting** for anything with shell or tmux syntax (`command:`, `tmux:`, `tip:`, in `optmux-defaults.yaml`, README examples, tests). Use the **literal** style `|` (keeps newlines, so a script reads as written) and, for long prose, the **folded** style `>` (joins lines). Quoting (`'...'`, `"..."`) fights with the `$`, quotes, and `\` already in shell commands, and plain scalars choke on `: `, `#`, or a leading quote. Quote only what a block can't hold (e.g. a `"\x10..."` escape).

- `transform.optmux.yaml` is a hand-written showcase ("more than meets the eye") of plugin options, shortcut ideas, and tool settings for users to take to their own config (not exhaustive, no generator; plugin options come from the plugins' READMEs); a test checks that it loads without warnings.

## Release Checklist

1. Bump `version` in `pyproject.toml`
2. `uv sync && uv build`
3. `git commit` (include `uv.lock`), `git tag vX.Y.Z`, `git push origin main --tags`
4. Clean old builds: `rm dist/optmux-0.1.* ...` (keep only current version to avoid re-uploading old ones)
5. `uv publish --token "$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$HOME/.pypirc'); print(c['pypi']['password'])")"`
6. `gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes dist/*`
7. Update `homebrew/optmux.rb`: new `url`/`version`, tarball sha256 (`curl -sL TARBALL_URL | shasum -a 256`). Homepage stays `https://pypi.org/project/optmux/`. Commit it, then `homebrew/upload.sh` to push it to the tap

## Homebrew Tap

- Repo: `netj/homebrew-tap` (on GitHub); `homebrew/optmux.rb` in this repo is the source of truth for its `optmux.rb`
- `optmux.rb` runs `uv sync --frozen --no-dev --no-editable` at install time into `libexec` (deps pinned by `uv.lock`, nothing fetched at runtime), and depends on `tmux`, `netj/tap/wtcode`, `lazygit`, `git-delta`, `less`, `fzf`, `universal-ctags`, `gh`
- Shebangs recommended as `#!/usr/bin/env optmux` (not `uvx`, which hits PyPI on every run)
- Update via `homebrew/upload.sh` (uploads `homebrew/optmux.rb` with `gh api ... --method PUT`; no-op when unchanged)

## tmux-fingers Plugin

- Plugin: `Morantron/tmux-fingers` (TPM-managed)
- The install wizard downloads pre-built binaries from GitHub releases
- **Critical:** Pre-built binaries require `bdw-gc` (Boehm GC) and other runtime dependencies
- `optmux/data/plugins-update.sh` now auto-installs missing dependencies via Homebrew
- Dependencies: `bdw-gc`, `pcre2`, `libevent`, `libyaml`
- Config: `set -g @fingers-skip-wizard '1'` in `optmux-tmux.conf` to skip the install wizard after initial setup

## Testing

```bash
uv run optmux ./example.optmux.yaml
```
