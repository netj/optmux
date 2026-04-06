# optmux — Claude Code Notes

## Project

- Python CLI tool wrapping tmuxp, packaged with `uv`
- Entry point: `optmux/cli.py` → `optmux.cli:main`
- Build system: `uv_build` (see `pyproject.toml`)

## Release Checklist

1. Bump `version` in `pyproject.toml`
2. `uv sync && uv build`
3. `git commit` (include `uv.lock`), `git tag vX.Y.Z`, `git push origin main --tags`
4. Clean old builds: `rm dist/optmux-0.1.* ...` (keep only current version to avoid re-uploading old ones)
5. `uv publish --token "$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$HOME/.pypirc'); print(c['pypi']['password'])")"`
6. `gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes dist/*`
7. Update `netj/homebrew-tap/optmux.rb` — new version, sha256 (`curl -sL TARBALL_URL | shasum -a 256`), homepage stays `https://pypi.org/project/optmux/`

## Homebrew Tap

- Repo: `netj/homebrew-tap` (on GitHub)
- `optmux.rb` is a meta-formula: installs `netj/tap/wtcode` + `lazygit`
- Update via `gh api repos/netj/homebrew-tap/contents/optmux.rb --method PUT ...`

## Testing

```bash
uv run optmux ./example.optmux.yaml
```
