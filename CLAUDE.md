# optmux — Claude Code Notes

## Project

- Python CLI tool wrapping tmuxp, packaged with `uv`
- Entry point: `optmux/cli.py` → `optmux.cli:main`
- Build system: `uv_build` (see `pyproject.toml`)

## YAML Style

- README YAML examples use indentless lists (`yq --indentless` style): the `-` sits at the same indent as its parent key, not nested under it.
- **Prefer YAML block scalars over quoting** for anything with shell or tmux syntax (`command:`, `tmux:`, `tip:`, in `optmux-defaults.yaml`, README examples, tests). Use the **literal** style `|` (keeps newlines, so a script reads as written) and, for long prose, the **folded** style `>` (joins lines). Quoting (`'...'`, `"..."`) fights with the `$`, quotes, and `\` already in shell commands, and plain scalars choke on `: `, `#`, or a leading quote. Quote only what a block can't hold (e.g. a `"\x10..."` escape).

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
