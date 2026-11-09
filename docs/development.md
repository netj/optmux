# Developing optmux

For people hacking on optmux itself; if you only use it, you can skip this.

```bash
# install the latest main branch
uvx git+https://github.com/netj/optmux.git

# local editable install for development
uv tool install -e .

# test any local changes directly (best for testing branches)
uv run optmux ./example.optmux.yaml

# run tests
uv run pytest                  # all tests
uv run pytest -m "not e2e"     # skip E2E tests (no tmux needed)
uv run pytest -m e2e           # E2E only (requires tmux)
```

The project's conventions, the docs layout, and the release checklist are in [`CLAUDE.md`](../CLAUDE.md).
