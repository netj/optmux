import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import version as _pkg_version
from importlib.resources import files
from pathlib import Path

import yaml

from optmux import actions
from optmux import menu as menu_compiler

__version__ = _pkg_version("optmux")

# macOS sockaddr_un.sun_path is 104 bytes (including NUL terminator)
_SOCK_PATH_LIMIT = 104


def _short_sock_path(tmux_dir: Path) -> str:
    """Return a socket path under the Unix sun_path limit.

    When the natural path (.optmux.d/tmux/tmux.sock) is too long,
    place the socket under a deterministic temp directory and leave
    a symlink at the original location for discoverability.
    """
    natural = tmux_dir / "tmux.sock"
    natural_str = str(natural)
    if len(natural_str) < _SOCK_PATH_LIMIT:
        return natural_str
    h = hashlib.sha256(natural_str.encode()).hexdigest()[:12]
    short_dir = Path(tempfile.gettempdir()) / f"optmux-{h}"
    short_dir.mkdir(parents=True, exist_ok=True)
    short_sock = str(short_dir / "tmux.sock")
    if tmux_dir.exists():
        if natural.is_symlink():
            natural.unlink()
        if not natural.exists():
            natural.symlink_to(short_sock)
    return short_sock


KNOWN_SUBCOMMANDS = {"start", "stop", "warp", "tmux"}


def parse_project_name(yaml_path_str):
    """Extract project name from a YAML path by stripping known suffixes."""
    name = Path(yaml_path_str).stem
    for suffix in (".tmuxp", ".optmux", ".optmuxp"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


KNOWN_OPTMUX_KEYS = {"shortcuts", "tmux_config", "menu", "plugins", "env", "git_config", "lazygit"}
KNOWN_SHORTCUT_KEYS = {
    "tmux", "send_keys", "command", "new_window", "float_window",
    "zoom", "detached", "remain", "tip",
}
# menu items share the shortcuts action vocabulary (command/tmux/send_keys/...),
# plus their own default/title/key fields; only "tip" doesn't apply to a menu item.
KNOWN_MENU_ITEM_KEYS = {"default", "title", "key"} | (KNOWN_SHORTCUT_KEYS - {"tip"})


def _warn_unknown_keys(keys, allowed, context):
    """Print a warning for keys not in allowed (ignoring keys starting with '_')."""
    unknown = [k for k in keys if k not in allowed and not str(k).startswith("_")]
    if unknown:
        allowed_list = ", ".join(sorted(allowed))
        for key in unknown:
            print(
                f"optmux: {context}: unrecognized key {key!r} (allowed: {allowed_list})",
                file=sys.stderr,
            )


def _validate_optmux_section(optmux, source):
    """Warn about unrecognized keys in an optmux: section, its shortcuts, and its menu."""
    _warn_unknown_keys(optmux.keys(), KNOWN_OPTMUX_KEYS, source)
    for key, value in (optmux.get("shortcuts") or {}).items():
        if isinstance(value, dict):
            _warn_unknown_keys(value.keys(), KNOWN_SHORTCUT_KEYS, f"{source}: shortcut {key!r}")
    for context, entries in (optmux.get("menu") or {}).items():
        if context not in menu_compiler.CONTEXTS:
            print(
                f"optmux: {source}: menu: unrecognized context {context!r} "
                f"(allowed: {', '.join(menu_compiler.CONTEXTS)})",
                file=sys.stderr,
            )
            continue
        for entry in entries or []:
            if isinstance(entry, dict):
                _warn_unknown_keys(
                    entry.keys(), KNOWN_MENU_ITEM_KEYS, f"{source}: menu.{context} item {entry!r}"
                )


def load_bundled_defaults():
    """Load bundled optmux defaults from package data."""
    defaults_path = files("optmux").joinpath("data", "optmux-defaults.yaml")
    with open(str(defaults_path)) as f:
        data = yaml.safe_load(f) or {}
    return data.get("optmux") or {}


def load_optmux_conf(conf_path=None):
    """Load personal optmux config from ~/.optmux.yaml if it exists."""
    if conf_path is None:
        conf_path = Path.home() / ".optmux.yaml"
    if conf_path.exists():
        with open(conf_path) as f:
            data = yaml.safe_load(f) or {}
        optmux = data.get("optmux") or {}
        _validate_optmux_section(optmux, str(conf_path))
        return optmux
    return {}


def merge_optmux(*layers):
    """Merge optmux config layers (later layers win)."""
    merged = {}
    for key in ("shortcuts", "tmux_config", "env", "git_config"):
        combined = {}
        for layer in layers:
            combined.update(layer.get(key) or {})
        if combined:
            merged[key] = combined
    plugins_combined = {}
    for layer in layers:
        plugins_combined.update(layer.get("plugins") or {})
    if plugins_combined:
        merged["plugins"] = plugins_combined
    lazygit_combined = {}
    for layer in layers:
        lazygit_combined = _deep_merge(lazygit_combined, layer.get("lazygit") or {})
    if lazygit_combined:
        merged["lazygit"] = lazygit_combined
    menu_combined = {}
    for layer in layers:
        for context, entries in (layer.get("menu") or {}).items():
            menu_combined.setdefault(context, []).extend(entries or [])
    if menu_combined:
        merged["menu"] = menu_combined
    return merged


DISPLAY_ONLY_FIELDS = {"tip"}


def generate_shortcut_line(key, value):
    """Generate a single tmux bind line from a shortcut key and value.

    Returns the line string, or None if the value type is unsupported
    or the entry is display-only (tip field only).
    """
    bind = "bind -n" if key.startswith("C-M-") else "bind"
    # Escape backslashes in key for tmux (C-M-\ needs to be C-M-\\)
    tmux_key = key.replace("\\", "\\\\")
    # normalize str to dict
    if isinstance(value, str):
        opts = {"command": value} if value else {}
    elif isinstance(value, dict):
        opts = value
    else:
        return None
    # display-only entries (only tip, no action fields) generate no bind
    if opts and opts.keys() <= DISPLAY_ONLY_FIELDS:
        return None
    # raw tmux action
    if "tmux" in opts:
        return f"{bind} {tmux_key} {opts['tmux']}\n"
    parts = actions.build_action_parts(opts, f"shortcut {key!r}")
    if parts is None:
        return None
    return f"{bind} {tmux_key} {' \\; '.join(parts)}\n"


def generate_tips_content(shortcuts, bundled_keys=None):
    """Generate formatted tips text from shortcuts with tip fields.

    If bundled_keys is provided, separates user-defined shortcuts into a second section.
    """
    if bundled_keys is None:
        bundled_keys = set()

    def extract_entries(shortcut_dict, keys_filter=None):
        entries = []
        for key, value in shortcut_dict.items():
            if keys_filter is not None and (key in keys_filter) != (keys_filter == bundled_keys):
                continue
            if isinstance(value, str):
                tip = value if value else None
            elif isinstance(value, dict):
                tip = value.get("tip")
                if tip is None:
                    tip = value.get("command") or value.get("send_keys")
            else:
                continue
            if not tip:
                continue
            # display key: non-C-M- keys without spaces get C-t prefix
            if not key.startswith("C-M-") and " " not in key and "/" not in key:
                display_key = f"C-t {key}"
            else:
                display_key = key
            entries.append((display_key, tip))
        return entries

    builtin = extract_entries(shortcuts, bundled_keys if bundled_keys else None)
    user = extract_entries({k: v for k, v in shortcuts.items() if k not in bundled_keys}, set()) if bundled_keys else []

    all_entries = user + builtin
    if not all_entries:
        return ""

    key_width = max(len(k) for k, _ in all_entries) + 2
    lines = []

    if user:
        for display_key, tip in user:
            lines.append(f"  {display_key:<{key_width}}  {tip}")

    if builtin:
        if user:
            lines.append("")
        for display_key, tip in builtin:
            lines.append(f"  {display_key:<{key_width}}  {tip}")

    return "\n".join(lines) + "\n"


PLUGINS_CONF = "optmux-plugins.conf"


def _plugin_option_line(name, value):
    name = str(name)
    if isinstance(value, bool):
        value = "on" if value else "off"
    value = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'set -g {name if name.startswith("@") else "@" + name} "{value}"'


def generate_plugins_conf(plugins):
    """Generate tmux @plugin declarations from optmux.plugins (plugin -> config lines).

    A plugin's value may be empty, a string or list of raw tmux config lines, or a
    dict of option -> value (written as `set -g @option "value"`; the `@` is optional,
    `$VAR` still expands, and booleans become on/off; `_`-prefixed keys such as `_tip_url`
    are metadata, not options).
    `false` drops the plugin (to disable a bundled one).
    """
    lines = []
    enabled = [plugin for plugin, config in plugins.items() if config is not False]
    if enabled:
        # TPM can't expand $OPTMUX_DIR in the source-file path, so it would never see the
        # @plugin lines below; @tpm_plugins is the list it reads straight from tmux.
        lines.append(f"set -g @tpm_plugins '{' '.join(enabled)}'\n")
    for plugin, config in plugins.items():
        if config is False:
            continue
        lines.append(f"set -g @plugin '{plugin}'\n")
        if isinstance(config, dict):
            config = [
                _plugin_option_line(k, v)
                for k, v in config.items()
                if not str(k).startswith("_")
            ]
        elif isinstance(config, str):
            config = config.splitlines()
        for line in config or []:
            lines.append(f"{line}\n")
    return "".join(lines)


PLUGINS_TIPS = "tips-plugins.txt"


def plugin_url(plugin):
    """Homepage URL for a TPM plugin spec (user/repo on GitHub, or a full git URL)."""
    if "://" in plugin or plugin.startswith("git@"):
        return plugin
    return f"https://github.com/{plugin}"


def plugin_showcase_urls(config):
    """Extra links (a great page, a video) from a plugin's `_tip_url`: a string or a list."""
    urls = config.get("_tip_url") if isinstance(config, dict) else None
    if not urls:
        return []
    return [urls] if isinstance(urls, str) else [str(u) for u in urls]


def generate_plugins_tips(plugins):
    """Generate a `name  url` line per enabled plugin for the tips screen,
    followed by an indented line for each showcase link in its `_tip_url`."""
    enabled = {p: config for p, config in plugins.items() if config is not False}
    if not enabled:
        return ""
    width = max(len(n) for n in enabled) + 2
    lines = []
    for name, config in enabled.items():
        lines.append(f"  {name:<{width}}{plugin_url(name)}\n")
        lines.extend(f"  {'':<{width}}-> {u}\n" for u in plugin_showcase_urls(config))
    return "".join(lines)


def generate_tmux_conf_files(tmux_dir, optmux, bundled_shortcuts=None):
    """Generate tmux conf files from merged optmux config.

    Returns True if the set/content of the managed conf files changed.
    """
    managed = [*tmux_dir.glob("tmux.optmux-*.conf"), *tmux_dir.glob(PLUGINS_CONF)]
    old_files = {p.name: p.read_bytes() for p in managed}

    # clear all managed files first to avoid stale configs
    for conf_file in managed:
        conf_file.unlink()

    new_files = {}

    # optmux.plugins → optmux-plugins.conf (sourced by tmux.conf before TPM runs)
    plugins_content = generate_plugins_conf(optmux.get("plugins") or {})
    if plugins_content:
        new_files[PLUGINS_CONF] = plugins_content.encode()
        (tmux_dir / PLUGINS_CONF).write_text(plugins_content)
    plugins_tips = generate_plugins_tips(optmux.get("plugins") or {})
    if plugins_tips:
        (tmux_dir / PLUGINS_TIPS).write_text(plugins_tips)
    else:
        (tmux_dir / PLUGINS_TIPS).unlink(missing_ok=True)

    # optmux.shortcuts → tmux.optmux-shortcuts.conf + tips-content.txt
    shortcuts = optmux.get("shortcuts") or {}
    if shortcuts:
        lines = []
        for key, value in shortcuts.items():
            line = generate_shortcut_line(key, value)
            if line is not None:
                lines.append(line)
        shortcuts_content = "".join(lines)
        new_files["tmux.optmux-shortcuts.conf"] = shortcuts_content.encode()
        (tmux_dir / "tmux.optmux-shortcuts.conf").write_text(shortcuts_content)
        bundled_keys = set(bundled_shortcuts.keys()) if bundled_shortcuts else None
        tips_content = generate_tips_content(shortcuts, bundled_keys)
        if tips_content:
            (tmux_dir / "tips-content.txt").write_text(tips_content)

    # optmux.tmux_config → tmux.optmux-extras.{name}.conf for each entry
    tmux_config = optmux.get("tmux_config") or {}
    for conf_name, content in tmux_config.items():
        filename = f"tmux.optmux-extras.{conf_name}.conf"
        new_files[filename] = content.encode()
        (tmux_dir / filename).write_text(content)

    # optmux.menu → tmux.optmux-menu.conf (compiled display-menu bindings)
    menu_cfg = optmux.get("menu") or {}
    if menu_cfg:
        menu_content = menu_compiler.generate_menu_conf(menu_cfg, source="optmux: menu")
        if menu_content:
            new_files["tmux.optmux-menu.conf"] = menu_content.encode()
            (tmux_dir / "tmux.optmux-menu.conf").write_text(menu_content)

    return old_files != new_files


def resolve_paths(yaml_file):
    """Compute session name, optmux directory, and tmux paths from a YAML filename or CWD."""
    if yaml_file:
        yaml_path = Path(yaml_file).resolve()
        name = parse_project_name(yaml_file)
        optmux_dir = yaml_path.parent / f".{name}.optmux.d"
        # Read session_name from YAML for tmux session targeting
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            session_name = data.get("session_name", name)
        except OSError:
            session_name = name
    else:
        yaml_path = None
        name = Path.cwd().name
        # Strip leading dots from session name - tmux has issues parsing them in targets
        session_name = name.lstrip('.')
        optmux_dir = Path.cwd() / ".optmux.d"
    tmux_dir = optmux_dir / "tmux"
    sock = str(tmux_dir / "tmux.sock")
    return {
        "name": name,
        "session_name": session_name,
        "yaml_path": yaml_path,
        "yaml_file": yaml_file,
        "optmux_dir": optmux_dir,
        "tmux_dir": tmux_dir,
        "sock": sock,
        "tmux_cmd": ["tmux", "-S", sock],
    }


ENV_SH = "env.sh"
# git config keys whose value is a command to run; skipped when that command isn't installed
GIT_CONFIG_COMMAND_KEYS = {"core.pager", "interactive.difffilter"}


def _deep_merge(base, override):
    """Merge dicts recursively (override wins; lists and scalars replace)."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _env_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return os.path.expandvars(str(value))


def _command_installed(command):
    words = str(command).split()
    return bool(words) and shutil.which(words[0]) is not None


def _git_config_parameter(key, value):
    """Quote key=value the way git's GIT_CONFIG_PARAMETERS expects: 'key'='value'."""
    def quote(text):
        return "'" + text.replace("'", "'\\''") + "'"
    return f"{quote(key)}={quote(value)}"


def generate_git_config_env(git_config):
    """Turn optmux.git_config into a GIT_CONFIG_PARAMETERS env var (like `git -c key=value`).

    Not GIT_CONFIG_COUNT/KEY_n/VALUE_n: delta reads its settings (delta.*) itself and only
    understands GIT_CONFIG_PARAMETERS. Entries come after any the user already exported, so
    optmux's win.
    """
    # an outer optmux records the user's own value, so nesting doesn't stack our entries twice
    user = os.environ.get("OPTMUX_USER_GIT_CONFIG_PARAMETERS", os.environ.get("GIT_CONFIG_PARAMETERS", ""))
    params = [user] if user else []
    for key, value in git_config.items():
        if value is None:
            continue
        if (key.lower() in GIT_CONFIG_COMMAND_KEYS or key.lower().startswith("pager.")) \
                and not _command_installed(value):
            continue
        params.append(_git_config_parameter(key, _env_value(value)))
    return {
        "OPTMUX_USER_GIT_CONFIG_PARAMETERS": user,
        "GIT_CONFIG_PARAMETERS": " ".join(params),
    }


def _user_lazygit_config_files():
    """Return the user's own lazygit config file(s), to keep under optmux's in LG_CONFIG_FILE."""
    if "OPTMUX_USER_LG_CONFIG_FILE" in os.environ:  # recorded by an outer optmux
        return [f for f in os.environ["OPTMUX_USER_LG_CONFIG_FILE"].split(",") if f]
    if os.environ.get("LG_CONFIG_FILE"):
        return os.environ["LG_CONFIG_FILE"].split(",")
    try:
        env = {k: v for k, v in os.environ.items() if k != "LG_CONFIG_FILE"}
        config_dir = subprocess.run(
            ["lazygit", "--print-config-dir"], capture_output=True, text=True, env=env,
        ).stdout.strip()
    except OSError:
        return []
    config_file = Path(config_dir) / "config.yml" if config_dir else None
    return [str(config_file)] if config_file and config_file.exists() else []


def generate_lazygit_env(optmux_dir, lazygit):
    """Write optmux.lazygit as a config file layered on top of the user's via LG_CONFIG_FILE."""
    if not lazygit or not shutil.which("lazygit"):
        return {}
    git = lazygit.get("git") or {}
    if git.get("diffRenderers"):
        renderers = [r for r in git["diffRenderers"] if _command_installed(r.get("command", ""))]
        lazygit = {**lazygit, "git": {**git, "diffRenderers": renderers}}
    lazygit_dir = optmux_dir / "lazygit"
    lazygit_dir.mkdir(parents=True, exist_ok=True)
    config = lazygit_dir / "config.yml"
    config.write_text(
        "# DO NOT EDIT — regenerated by optmux on every launch from the optmux: lazygit: section.\n"
        + yaml.safe_dump(lazygit, sort_keys=False, allow_unicode=True)
    )
    user_files = _user_lazygit_config_files()
    return {
        "OPTMUX_USER_LG_CONFIG_FILE": ",".join(user_files),
        "LG_CONFIG_FILE": ",".join([*user_files, str(config)]),
    }


def generate_env_sh(bin_dir, env):
    """Render env.sh: put optmux's helper scripts on PATH, then set/unset env."""
    q = shlex.quote
    lines = [
        "# DO NOT EDIT — regenerated by optmux on every launch from the optmux: env, git_config, and lazygit sections.\n",
        "# Applied by optmux-env (which shortcuts use) to the command it runs. To use it in every shell,\n",
        "# add to your shell rc: [ -n \"$OPTMUX_DIR\" ] && . \"$OPTMUX_DIR/env.sh\"\n",
        f"export PATH={q(str(bin_dir))}\"${{PATH:+:$PATH}}\"\n",
    ]
    for name, value in env.items():
        lines.append(f"unset {name}\n" if value is None else f"export {name}={q(value)}\n")
    return "".join(lines)


def setup_tools_env(optmux_dir, data_dir, optmux):
    """Install optmux's helper scripts, and write env.sh from optmux's env, git_config, and lazygit.

    env.sh is applied only to commands run via optmux-env (as the bundled shortcuts do), and so to
    everything those start (lazygit → git → delta → less); shells inside optmux are left alone.
    """
    bin_dir = optmux_dir / "bin"
    if bin_dir.exists():  # managed: clear out stale scripts
        shutil.rmtree(bin_dir)
    bin_dir.mkdir(parents=True)
    for script in (data_dir / "bin").iterdir():
        dest = bin_dir / script.name
        dest.write_bytes(script.read_bytes())
        dest.chmod(0o555)  # read+execute for all (not writable), like tips.sh
    # only optmux-* helpers live here, so putting them on PATH shadows nothing
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")

    env = {
        name: None if value is None else _env_value(value)
        for name, value in (optmux.get("env") or {}).items()
    }
    env.update(generate_git_config_env(optmux.get("git_config") or {}))
    env.update(generate_lazygit_env(optmux_dir, optmux.get("lazygit") or {}))
    (optmux_dir / ENV_SH).write_text(generate_env_sh(bin_dir, env))


def setup_optmux_env(resolved):
    """Create optmux directories, seed config files, and set environment variables."""
    tmux_dir = resolved["tmux_dir"]
    optmux_dir = resolved["optmux_dir"]
    name = resolved["name"]
    yaml_path = resolved["yaml_path"]

    tmux_dir.mkdir(parents=True, exist_ok=True)

    gitignore = optmux_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n")

    data_dir = files("optmux").joinpath("data")
    tmux_conf = tmux_dir / "tmux.conf"
    new_tmux_conf_bytes = (data_dir / "tmux.conf").read_bytes()
    tmux_conf_changed = not tmux_conf.exists() or tmux_conf.read_bytes() != new_tmux_conf_bytes
    if tmux_conf.exists():
        tmux_conf.chmod(0o644)
    tmux_conf.write_bytes(new_tmux_conf_bytes)
    tmux_conf.chmod(0o444)

    setup_script = tmux_dir / "plugins-update.sh"
    if not setup_script.exists():
        shutil.copy2(data_dir / "plugins-update.sh", setup_script)
        setup_script.chmod(0o755)

    tips_script = tmux_dir / "tips.sh"
    if tips_script.exists():
        tips_script.chmod(0o644)
    shutil.copy2(data_dir / "tips.sh", tips_script)
    tips_script.chmod(0o555)  # read+execute for all (not writable)

    bundled = load_bundled_defaults()
    personal = load_optmux_conf()
    if yaml_path:
        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}
        project = data.get("optmux") or {}
        _validate_optmux_section(project, str(yaml_path))
        optmux = merge_optmux(bundled, project, personal)
    else:
        optmux = merge_optmux(bundled, personal)
    conf_files_changed = generate_tmux_conf_files(tmux_dir, optmux, bundled.get("shortcuts"))
    config_changed = tmux_conf_changed or conf_files_changed

    venv_bin = str(Path(sys.executable).parent)
    os.environ["PATH"] = venv_bin + os.pathsep + os.environ.get("PATH", "")
    os.environ["OPTMUX_DIR"] = str(optmux_dir)
    os.environ["OPTMUX_NAME"] = name
    os.environ["TMUX_PLUGIN_MANAGER_PATH"] = str(tmux_dir / "plugins")
    setup_tools_env(optmux_dir, data_dir, optmux)

    sock = _short_sock_path(tmux_dir)
    resolved["sock"] = sock
    resolved["tmux_cmd"] = ["tmux", "-S", sock]

    return {
        "conf": str(tmux_conf),
        "setup_script": setup_script,
        "tips_script": tips_script,
        "config_changed": config_changed,
    }


def create_optmux_window(tmux_cmd, tips_script, setup_script, session_name):
    """Create window 0 with tips + plugins-update panes."""
    # Create window 0 (base-index is 1, so window 0 doesn't auto-exist)
    target = f"{session_name}:0"
    subprocess.run([*tmux_cmd, "new-window", "-t", target, "-n", "optmux", str(tips_script)], check=True)
    subprocess.run([*tmux_cmd, "split-window", "-t", target, "-v", str(setup_script)], check=True)


def cmd_stop(resolved):
    """Stop (kill) an optmux session."""
    # Setup environment to get correct socket path
    setup_optmux_env(resolved)
    tmux = resolved["tmux_cmd"]
    session_name = resolved["session_name"]

    has_session = subprocess.run(
        [*tmux, "has-session", "-t", session_name],
        capture_output=True,
    ).returncode == 0

    if not has_session:
        print(f"optmux: session '{session_name}' is not running", file=sys.stderr)
        sys.exit(1)

    subprocess.run([*tmux, "kill-session", "-t", session_name], check=True)
    print(f"optmux: killed session '{session_name}'")


def cmd_tmux(resolved, args):
    """Low-level passthrough to the tmux server backing this project.

    Bypasses tmuxp/session bootstrapping entirely, for when you need direct
    access (e.g. `optmux . tmux ls`) instead of hand-rolling `-S <sock>`.
    """
    setup_optmux_env(resolved)
    tmux = resolved["tmux_cmd"]
    os.execvp(tmux[0], [*tmux, *args])


def _notify_config_changed(tmux):
    """Remind the next client to attach to this session to reload the config.

    display-message can't be shown directly here: in the common workflow
    (detach, edit config, rerun) no client is attached yet at this point —
    we're about to become the client via the attach-session that follows.
    A one-shot client-attached hook fires once that attach happens.
    """
    subprocess.run(
        [*tmux, "set-hook", "-g", "client-attached",
         'display-message -d 0 "optmux: config changed — press C-t R to reload" ; '
         "set-hook -gu client-attached"],
        capture_output=True,
    )


def cmd_start(resolved, remaining_args):
    """Start or attach to an optmux session."""
    tmux = resolved["tmux_cmd"]
    sock = resolved["sock"]
    name = resolved["name"]
    session_name = resolved["session_name"]
    yaml_path = resolved["yaml_path"]
    yaml_file = resolved["yaml_file"]

    outer_tmux = os.environ.get("TMUX")
    if outer_tmux:
        outer_sock = outer_tmux.split(",")[0]
        if os.path.realpath(outer_sock) == os.path.realpath(sock):
            # Same server: switch to the main session (e.g., from a warp session)
            os.execvp(tmux[0], [*tmux, "switch-client", "-t", session_name])
            return
        print("optmux: nesting inside outer tmux session", file=sys.stderr)
        del os.environ["TMUX"]

    env = setup_optmux_env(resolved)
    conf = env["conf"]
    tmux = resolved["tmux_cmd"]
    sock = resolved["sock"]

    subprocess.run([str(env["setup_script"])], check=True)

    if yaml_path:
        has_session = subprocess.run(
            [*tmux, "has-session", "-t", session_name],
            capture_output=True,
        ).returncode == 0
        if has_session:
            if env["config_changed"]:
                _notify_config_changed(tmux)
            os.execvp(tmux[0], [*tmux, "attach-session", "-t", session_name])
        subprocess.run(
            ["tmuxp", "load", "--yes", "-d", "-S", sock, "-f", conf,
             yaml_file, *remaining_args],
            check=True,
        )
        create_optmux_window(tmux, env["tips_script"], env["setup_script"], session_name)
        os.execvp(tmux[0], [*tmux, "attach-session", "-t", session_name])
    else:
        has_session = subprocess.run(
            [*tmux, "has-session", "-t", session_name],
            capture_output=True,
        ).returncode == 0
        if has_session:
            if env["config_changed"]:
                _notify_config_changed(tmux)
            os.execvp(tmux[0], [*tmux, "attach-session", "-t", session_name])
        else:
            subprocess.run([*tmux, "-f", conf, "new-session", "-d", "-s", session_name], check=True)
            create_optmux_window(tmux, env["tips_script"], env["setup_script"], session_name)
            os.execvp(tmux[0], [*tmux, "attach-session", "-t", session_name])


def _patch_warp_status(tmux, warp_name):
    """Patch global status formats to show short name for warp sessions (no-op for main)."""
    warp_fmt = "#{s|//.*|⚡warp|:session_name}"
    for option in ("status-left", "status-right", "set-titles-string"):
        result = subprocess.run(
            [*tmux, "show", "-gv", option],
            capture_output=True, text=True,
        )
        raw = result.stdout.strip()
        if result.returncode != 0 or warp_fmt in raw:
            continue
        if "#{session_name}" in raw:
            patched = raw.replace("#{session_name}", warp_fmt)
        elif "#S" in raw:
            patched = raw.replace("#S", warp_fmt)
        else:
            continue
        subprocess.run([*tmux, "set", "-g", option, patched], capture_output=True)


def _attach_or_switch(tmux_cmd, session_name, sock, outer_tmux, *, warp=False):
    """Attach to a session, or switch-client if already inside the same server."""
    if warp:
        _patch_warp_status(tmux_cmd, session_name)
    if outer_tmux:
        outer_sock = outer_tmux.split(",")[0]
        if os.path.realpath(outer_sock) == os.path.realpath(sock):
            os.execvp(tmux_cmd[0], [*tmux_cmd, "switch-client", "-t", session_name])
            return
    os.execvp(tmux_cmd[0], [*tmux_cmd, "attach-session", "-t", session_name])


def cmd_warp(resolved, args, original_cwd=None):
    """Create or update a warp session linking windows whose panes match a workdir."""
    tmux = resolved["tmux_cmd"]
    sock = resolved["sock"]
    main_session = resolved["session_name"]

    if original_cwd is None:
        original_cwd = os.getcwd()

    warp_name = None
    workdir = None
    if len(args) >= 1:
        workdir = args[0]
    if len(args) >= 2:
        warp_name = args[1]
    if len(args) > 2:
        print("optmux warp: too many arguments", file=sys.stderr)
        print("usage: optmux [DIR | YAML] warp [WORKDIR] [NAME]", file=sys.stderr)
        sys.exit(1)

    # Resolve workdir relative to original cwd (before any chdir from DIR arg)
    workdir = os.path.realpath(os.path.join(original_cwd, workdir or "."))
    if warp_name is None:
        warp_name = f"{main_session}//{Path(workdir).name}"

    outer_tmux = os.environ.get("TMUX")
    if outer_tmux:
        outer_sock = outer_tmux.split(",")[0]
        if os.path.realpath(outer_sock) != os.path.realpath(sock):
            print("optmux: nesting inside outer tmux session", file=sys.stderr)
            del os.environ["TMUX"]

    if subprocess.run(
        [*tmux, "has-session", "-t", main_session], capture_output=True,
    ).returncode != 0:
        yaml_hint = f" {resolved['yaml_file']}" if resolved["yaml_file"] else ""
        print(f"optmux warp: session '{main_session}' is not running", file=sys.stderr)
        print(f"optmux warp: start it first with: optmux{yaml_hint}", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        [*tmux, "list-panes", "-s", "-t", main_session,
         "-F", "#{window_id}\t#{window_index}\t#{pane_current_path}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"optmux warp: failed to list panes: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    matching_windows = {}  # window_id -> window_index
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        win_id, win_idx, pane_path = line.split("\t", 2)
        if os.path.realpath(pane_path) == workdir:
            matching_windows[win_id] = win_idx

    if not matching_windows:
        print(f"optmux warp: no windows in '{main_session}' have panes in {workdir}", file=sys.stderr)
        sys.exit(1)

    warp_exists = subprocess.run(
        [*tmux, "has-session", "-t", warp_name], capture_output=True,
    ).returncode == 0

    already_linked = set()
    if warp_exists:
        result = subprocess.run(
            [*tmux, "list-panes", "-s", "-t", warp_name, "-F", "#{window_id}"],
            capture_output=True, text=True,
        )
        already_linked = set(result.stdout.strip().splitlines())

    windows_to_link = {wid: idx for wid, idx in matching_windows.items()
                       if wid not in already_linked}

    if not windows_to_link and warp_exists:
        _attach_or_switch(tmux, warp_name, sock, outer_tmux, warp=True)
        return

    initial_window_id = None
    if not warp_exists:
        result = subprocess.run(
            [*tmux, "new-session", "-d", "-s", warp_name, "-P", "-F", "#{window_id}"],
            capture_output=True, text=True, check=True,
        )
        initial_window_id = result.stdout.strip()

    for win_id, win_idx in windows_to_link.items():
        subprocess.run(
            [*tmux, "link-window", "-s", f"{main_session}:{win_idx}", "-t", warp_name],
            check=True,
        )

    if initial_window_id and initial_window_id not in matching_windows:
        subprocess.run(
            [*tmux, "kill-window", "-t", initial_window_id],
            capture_output=True,
        )

    _attach_or_switch(tmux, warp_name, sock, outer_tmux, warp=True)


USAGE = """\
usage: optmux [DIR | YAML] [start | stop | warp [WORKDIR] [NAME] | tmux ARGS...]

  optmux DIR                          open tmux in DIR (use . for cwd)
  optmux YAML                         load a tmuxp session from YAML
  optmux [DIR | YAML] start           same as above (explicit)
  optmux [DIR | YAML] stop            kill the tmux session
  optmux [DIR | YAML] warp [WORKDIR] [NAME]
                                      create a warp session linking windows
                                      whose panes match WORKDIR (default: cwd)
  optmux [DIR | YAML] tmux ARGS...    run a raw tmux command against this
                                      project's tmux server (e.g. `optmux . tmux ls`)
  optmux -v | --version | version     print the optmux version
  optmux -h | --help | help           print this help
"""


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print(f"optmux {__version__}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(0)

    if argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        sys.exit(0)

    if argv[0] in ("-v", "--version", "version"):
        print(f"optmux {__version__}")
        sys.exit(0)

    argv = list(argv)
    original_cwd = os.getcwd()

    # First positional is either a directory (plain tmux) or a YAML file (tmuxp session)
    yaml_file = None
    if argv and argv[0] not in KNOWN_SUBCOMMANDS:
        candidate = argv[0]
        if Path(candidate).is_dir():
            os.chdir(argv.pop(0))
        elif Path(candidate).suffix in ('.yaml', '.yml'):
            yaml_file = argv.pop(0)

    if argv and argv[0] in KNOWN_SUBCOMMANDS:
        subcommand = argv.pop(0)
    elif argv and not argv[0].startswith('-'):
        print(f"optmux: unknown argument: {argv[0]}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)
    else:
        subcommand = "start"

    resolved = resolve_paths(yaml_file)

    if subcommand == "start":
        cmd_start(resolved, argv)
    elif subcommand == "stop":
        cmd_stop(resolved)
    elif subcommand == "warp":
        cmd_warp(resolved, argv, original_cwd)
    elif subcommand == "tmux":
        cmd_tmux(resolved, argv)
