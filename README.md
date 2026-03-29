# optmux

A [tmuxp](https://github.com/tmux-python/tmuxp) wrapper that creates per-workflow tmux config directories.

## Install

```bash
uv tool install optmux
```

Or use directly with `uvx`:

```bash
uvx optmux workflow.optmuxp.yaml
```

## Usage

### With a tmuxp YAML file

```bash
optmux myproject.optmuxp.yaml
```

This will:

1. Create `myproject.optmux.d/` next to the YAML file
2. Seed it with a default `tmux.conf` (with TPM and plugins pre-configured)
3. Set up `tmux.sock` (socket) and `tmux-plugins/` inside that directory
4. Launch `tmuxp load` with the per-workflow socket and config

### Without arguments

```bash
optmux
```

Opens plain `tmux` using `.optmux.d/` in the current directory — useful for a quick, isolated tmux session with the bundled config.

### As a shebang

Make your YAML file executable:

```yaml
#!/usr/bin/env -S uvx optmux
session_name: myproject
windows:
  - window_name: editor
    panes:
      - vim
  - window_name: shell
    panes:
      - ""
```

```bash
chmod +x myproject.optmuxp.yaml
./myproject.optmuxp.yaml
```

## Per-workflow config directory

The `$WORKFLOW.optmux.d/` directory contains:

| File/Dir | Purpose |
|---|---|
| `tmux.conf` | Main tmux config (seeded from bundled default, editable) |
| `tmux.*.conf` | Additional config files you can add |
| `tmux.sock` | Tmux server socket (isolates this workflow's tmux) |
| `tmux-plugins/` | TPM plugin directory (`TMUX_PLUGIN_MANAGER_PATH`) |

The default `tmux.conf` comes with [TPM](https://github.com/tmux-plugins/tpm) and several plugins pre-configured. You can edit it freely after creation.

## License

[MIT](LICENSE)
