# optmux — Claude Code Notes

## Project

- Python CLI tool wrapping tmuxp, packaged with `uv`
- Entry point: `optmux/cli.py` → `optmux.cli:main`
- Build system: `uv_build` (see `pyproject.toml`)

## Release Checklist

1. Bump `version` in `pyproject.toml`
2. `uv sync && uv build`
3. `git commit`, `git tag vX.Y.Z`, `git push origin main --tags`
4. `uv publish --token "$(python3 -c "import configparser; c=configparser.ConfigParser(); c.read('$HOME/.pypirc'); print(c['pypi']['password'])")"`
5. `gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes dist/*`
6. Update `netj/homebrew-tap/optmux.rb` — new version, sha256 (`curl -sL TARBALL_URL | shasum -a 256`), homepage stays `https://pypi.org/project/optmux/`

## Homebrew Tap

- Repo: `netj/homebrew-tap` (on GitHub)
- `optmux.rb` is a meta-formula: installs `netj/tap/wtcode` + `lazygit`
- Update via `gh api repos/netj/homebrew-tap/contents/optmux.rb --method PUT ...`

## Testing

```bash
uv run optmux ./example.optmux.yaml
```
