# optmux

A [tmuxp](https://github.com/tmux-python/tmuxp) wrapper that creates per-workflow tmux config directories with [TPM](https://github.com/tmux-plugins/tpm) and plugins pre-configured.

## Quick Start

```bash
# install optmux
uv tool install optmux

# try the included example
git clone https://github.com/netj/optmux
cd optmux
./example.optmux.yaml
```

That's it. On first run, optmux will:

1. Create `example.optmux.d/tmux/` next to the YAML file
2. Seed a default `tmux.conf` with TPM and plugins
3. Install TPM and all plugins (visible in window 0)
4. Launch tmuxp with an isolated tmux server

## Install

```bash
uv tool install optmux
```

Or run directly without installing:

```bash
uvx optmux workflow.optmuxp.yaml
```

## Usage

### With a tmuxp YAML file

```bash
optmux myproject.optmuxp.yaml
```

### Without arguments

```bash
optmux
```

Opens plain `tmux` using `.optmux.d/` in the current directory — useful for a quick, isolated tmux session with the bundled config.

### As a shebang

Add the shebang line to any `.optmux.yaml` file and make it executable:

```yaml
#!/usr/bin/env -S uvx optmux
session_name: myproject
windows:
  - window_name: editor
    panes:
      - vim .
  - window_name: shell
    panes:
      - ""
```

```bash
chmod +x myproject.optmux.yaml
./myproject.optmux.yaml
```

## Per-workflow config directory

Each workflow gets its own `$WORKFLOW.optmux.d/` directory:

| Path | Purpose |
|---|---|
| `tmux/tmux.conf` | Main tmux config (editable after creation) |
| `tmux/tmux.*.conf` | Additional config files you can add |
| `tmux/tmux.sock` | Tmux server socket (isolates this workflow) |
| `tmux/plugins/` | TPM plugin directory |
| `tmux/plugins-update.sh` | Run manually to update all plugins |

### Customization

- Edit `tmux/tmux.conf` to change tmux settings
- Drop `tmux/tmux.mysetup.conf` files for additional config (auto-sourced)
- Run `tmux/plugins-update.sh` from inside tmux to update plugins
- Press `prefix + R` to reload the config

### Environment variables

optmux sets these before launching tmux/tmuxp:

| Variable | Value |
|---|---|
| `OPTMUX_DIR` | Absolute path to the `.optmux.d/` directory |
| `OPTMUX_BASENAME` | Workflow name (e.g., `myproject`) |
| `TMUX_PLUGIN_MANAGER_PATH` | `$OPTMUX_DIR/tmux/plugins` |

## License

[MIT](LICENSE)
