"""Tests for optmux's env/git_config/lazygit: config merging, env.sh, and optmux-env."""

import os
import shutil
import subprocess
from importlib.resources import files as pkg_files
from unittest.mock import patch

import pytest
import yaml

from optmux import cli
from optmux.cli import load_bundled_defaults, merge_optmux, setup_tools_env

DATA_DIR = pkg_files("optmux").joinpath("data")
OPEN_URL = str(DATA_DIR.joinpath("bin", "optmux-open-url"))


@pytest.fixture(autouse=True)
def clean_env():
    """Restore os.environ afterwards, starting each test without variables optmux manages."""
    saved = dict(os.environ)
    for name in list(os.environ):
        if name in ("PAGER", "LESS", "LESS_OSC8_OPEN_ANY", "LG_CONFIG_FILE") \
                or name.startswith(("GIT_CONFIG_", "OPTMUX_USER_")):
            del os.environ[name]
    yield
    os.environ.clear()
    os.environ.update(saved)


def which_only(*tools):
    return lambda name: f"/usr/bin/{name}" if name in tools else None


def env_sh(optmux_dir, base_env=None):
    """Source optmux_dir/env.sh in sh and return the resulting environment."""
    result = subprocess.run(
        ["sh", "-c", '. "$1/env.sh" && env -0', "sh", str(optmux_dir)],
        env={"PATH": "/usr/bin:/bin", **(base_env or {})}, capture_output=True, text=True, check=True,
    )
    return dict(kv.split("=", 1) for kv in result.stdout.split("\0") if kv)


def git_get(env, key, tmp_path):
    """Ask real git for a config value, as seen from `env` with an empty HOME."""
    if not shutil.which("git"):
        pytest.skip("git not found")
    home = tmp_path / "empty-home"
    home.mkdir(exist_ok=True)
    result = subprocess.run(
        ["git", "config", "--get-all", key],
        env={**env, "HOME": str(home), "XDG_CONFIG_HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1"},
        capture_output=True, text=True,
    )
    return result.stdout.split("\n")[:-1]


def run_setup(tmp_path, optmux=None, tools=("delta", "lazygit"), lazygit_config_dir=None):
    """Run setup_tools_env with fake installed tools (and no real subprocesses)."""
    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["lazygit", "--print-config-dir"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{lazygit_config_dir or ''}\n")
        raise AssertionError(f"unexpected command: {cmd}")

    if optmux is None:
        optmux = load_bundled_defaults()
    with patch.object(cli.shutil, "which", side_effect=which_only(*tools)), \
         patch.object(cli.subprocess, "run", side_effect=fake_run):
        setup_tools_env(tmp_path, DATA_DIR, optmux)
    return env_sh(tmp_path)


# --- config merging ---------------------------------------------------------

def test_merge_env_git_config_per_key():
    merged = merge_optmux(
        {"env": {"A": "1", "B": "2"}, "git_config": {"core.pager": "delta"}},
        {"env": {"B": "3", "C": None}, "git_config": {"core.pager": "less"}},
    )
    assert merged["env"] == {"A": "1", "B": "3", "C": None}
    assert merged["git_config"] == {"core.pager": "less"}


def test_merge_lazygit_deep():
    merged = merge_optmux(
        {"lazygit": {"git": {"diffRenderers": [1], "paging": {"a": 1}}, "x": 1}},
        {"lazygit": {"git": {"diffRenderers": [2]}}},
    )
    assert merged["lazygit"] == {"git": {"diffRenderers": [2], "paging": {"a": 1}}, "x": 1}


def test_new_keys_validated_without_warnings(capsys):
    cli._validate_optmux_section(load_bundled_defaults(), "bundled")
    assert capsys.readouterr().err == ""


# --- env ---------------------------------------------------------------------

def test_env_sh_overrides_user(tmp_path):
    run_setup(tmp_path)
    env = env_sh(tmp_path, {"LESS": "-R"})
    assert env["LESS"] == "-XRiMWSc --mouse"
    assert env["LESS_OSC8_OPEN_ANY"] == "\x10-optmux-open-url"
    assert env["PATH"] == f"{tmp_path / 'bin'}:/usr/bin:/bin"


def test_env_expands_vars_and_unsets_null(tmp_path):
    run_setup(tmp_path, {"env": {"WHERE": "$HOME/x", "DROP_ME": None, "Q": "it's"}})
    env = env_sh(tmp_path, {"DROP_ME": "x"})
    assert env["WHERE"] == os.path.expanduser("~/x")
    assert env["Q"] == "it's"
    assert "DROP_ME" not in env


def test_shells_and_server_env_left_alone(tmp_path):
    os.environ["LESS"] = "-R"
    run_setup(tmp_path)
    assert os.environ["LESS"] == "-R"
    assert "GIT_CONFIG_PARAMETERS" not in os.environ
    assert "LG_CONFIG_FILE" not in os.environ
    # only the optmux-* helpers go on PATH, shadowing nothing
    bin_dir = tmp_path / "bin"
    assert os.environ["PATH"].split(os.pathsep)[0] == str(bin_dir)
    assert all(p.name.startswith("optmux-") for p in bin_dir.iterdir())


# --- git_config --------------------------------------------------------------

def test_git_config_via_env(tmp_path):
    env = run_setup(tmp_path)
    assert git_get(env, "core.pager", tmp_path) == ["delta"]
    assert git_get(env, "interactive.diffFilter", tmp_path) == ["delta --color-only"]
    assert git_get(env, "delta.navigate", tmp_path) == ["true"]
    assert git_get(env, "delta.hyperlinks-file-link-format", tmp_path) == ["file://{path}#L{line}"]


def test_git_config_skips_missing_pager(tmp_path):
    env = run_setup(tmp_path, tools=())
    assert git_get(env, "core.pager", tmp_path) == []
    assert git_get(env, "interactive.diffFilter", tmp_path) == []
    assert git_get(env, "delta.navigate", tmp_path) == ["true"]  # harmless without delta


def test_git_config_quotes_values(tmp_path):
    env = run_setup(tmp_path, {"git_config": {"alias.q": "log --format='%h %s'"}})
    assert git_get(env, "alias.q", tmp_path) == ["log --format='%h %s'"]


def test_git_config_keeps_and_follows_user_parameters(tmp_path):
    os.environ["GIT_CONFIG_PARAMETERS"] = "'core.pager'='cat' 'user.name'='me'"
    env = run_setup(tmp_path, {"git_config": {"core.pager": "delta"}})
    assert git_get(env, "user.name", tmp_path) == ["me"]
    assert git_get(env, "core.pager", tmp_path) == ["cat", "delta"]  # last one wins


def test_git_config_not_stacked_when_nested(tmp_path):
    env = run_setup(tmp_path / "outer")
    os.environ.update({k: v for k, v in env.items() if k.startswith(("GIT_CONFIG_", "OPTMUX_USER_"))})
    inner = run_setup(tmp_path / "inner")
    assert inner["GIT_CONFIG_PARAMETERS"] == env["GIT_CONFIG_PARAMETERS"]


def test_git_config_wins_in_real_git(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git not found")
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("[core]\n\tpager = cat\n")
    env = run_setup(tmp_path / "optmux.d", {"git_config": {"core.pager": "less"}}, tools=("less",))
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home))
    result = subprocess.run(["git", "var", "GIT_PAGER"], env=env, capture_output=True, text=True)
    assert result.stdout.strip() == "less"


@pytest.mark.skipif(not shutil.which("delta"), reason="delta not found")
def test_delta_sees_git_config(tmp_path):
    """delta reads delta.* itself and ignores GIT_CONFIG_COUNT, so optmux must use GIT_CONFIG_PARAMETERS."""
    env = run_setup(tmp_path)
    home = tmp_path / "empty-home"
    home.mkdir()
    result = subprocess.run(
        ["delta", "--show-config"],
        env={**env, "PATH": os.environ["PATH"], "HOME": str(home), "XDG_CONFIG_HOME": str(home)},
        capture_output=True, text=True,
    )
    assert "line-numbers" in result.stdout
    assert any("hyperlinks" in line and "true" in line for line in result.stdout.splitlines())


# --- lazygit -----------------------------------------------------------------

def test_lazygit_layers_over_user_config(tmp_path):
    user_dir = tmp_path / "user-lazygit"
    user_dir.mkdir()
    (user_dir / "config.yml").write_text("gui: {}\n")
    env = run_setup(tmp_path / "optmux.d", lazygit_config_dir=user_dir)
    ours = tmp_path / "optmux.d" / "lazygit" / "config.yml"
    assert env["LG_CONFIG_FILE"].split(",") == [str(user_dir / "config.yml"), str(ours)]
    config = yaml.safe_load(ours.read_text())
    assert config["git"]["diffRenderers"][0]["command"].startswith("delta ")
    assert config["customCommands"][0]["key"] == "<c-g>"


def test_lazygit_drops_missing_diff_renderer(tmp_path):
    env = run_setup(tmp_path, tools=("lazygit",))
    config = yaml.safe_load((tmp_path / "lazygit" / "config.yml").read_text())
    assert config["git"]["diffRenderers"] == []
    assert env["LG_CONFIG_FILE"] == str(tmp_path / "lazygit" / "config.yml")


def test_lazygit_keeps_user_lg_config_file(tmp_path):
    os.environ["LG_CONFIG_FILE"] = "/a.yml,/b.yml"
    env = run_setup(tmp_path / "outer")
    assert env["LG_CONFIG_FILE"].split(",")[:2] == ["/a.yml", "/b.yml"]
    os.environ.update(LG_CONFIG_FILE=env["LG_CONFIG_FILE"],
                      OPTMUX_USER_LG_CONFIG_FILE=env["OPTMUX_USER_LG_CONFIG_FILE"])
    env = run_setup(tmp_path / "inner")  # nested optmux doesn't stack layers
    assert len(env["LG_CONFIG_FILE"].split(",")) == 3


def test_no_lazygit_config_when_not_installed(tmp_path):
    assert "LG_CONFIG_FILE" not in run_setup(tmp_path, tools=("delta",))


# --- optmux-env --------------------------------------------------------------

def test_optmux_env_runs_command_with_env(tmp_path):
    run_setup(tmp_path, {"env": {"LESS": "-OPTMUX"}})
    result = subprocess.run(
        [str(tmp_path / "bin" / "optmux-env"), "sh", "-c", 'echo "$LESS $1"', "sh", "arg"],
        env={"PATH": "/usr/bin:/bin", "LESS": "-USER"}, capture_output=True, text=True, timeout=10,
    )
    assert result.stdout.strip() == "-OPTMUX arg"


def test_optmux_env_usage(tmp_path):
    run_setup(tmp_path)
    result = subprocess.run([str(tmp_path / "bin" / "optmux-env")], capture_output=True, text=True)
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_rerun_replaces_read_only_scripts(tmp_path):
    run_setup(tmp_path)
    run_setup(tmp_path)
    assert os.access(tmp_path / "bin" / "optmux-env", os.X_OK)


# --- optmux-open-url ----------------------------------------------------------

@pytest.mark.parametrize("editor, uri, expected", [
    ("vim", "file:///tmp/a%20b.py#L12", "vim +12 /tmp/a b.py"),
    ("vim", "file://host/tmp/x.py", "vim /tmp/x.py"),
    ("vim", "file:///tmp/x.py#section", "vim /tmp/x.py"),
    ("code --wait", "file:///tmp/x.py#L3", "code --wait --goto /tmp/x.py:3"),
    ("hx", "file:///tmp/x.py#L3", "hx /tmp/x.py:3"),
])
def test_open_url_file_links(tmp_path, editor, uri, expected):
    # stub editors that just print how they were invoked
    for name in ("vim", "code", "hx"):
        stub = tmp_path / name
        stub.write_text(f'#!/bin/sh\necho {name} "$@"\n')
        stub.chmod(0o755)
    result = subprocess.run(
        ["bash", OPEN_URL, uri],
        env={"PATH": f"{tmp_path}:/usr/bin:/bin", "EDITOR": editor},
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


# --- optmux-diff-base ---------------------------------------------------------

DIFF_BASE = str(DATA_DIR.joinpath("bin", "optmux-diff-base"))


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
    )


@pytest.fixture
def repo_with_remote(tmp_path):
    """A clone whose default branch has diverged from the feature branch (no origin/HEAD yet)."""
    if not shutil.which("git"):
        pytest.skip("git not found")
    origin, clone = tmp_path / "origin", tmp_path / "clone"
    git(tmp_path, "init", "-q", "-b", "main", str(origin))
    (origin / "a.txt").write_text("base\n")
    git(origin, "add", "a.txt")
    git(origin, "commit", "-qm", "base")
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    git(clone, "checkout", "-qb", "feature")
    (clone / "a.txt").write_text("base\nfeature\n")
    git(clone, "commit", "-qam", "feature")
    # main moves on after the branch point: must not show up as a (reverse) change
    (origin / "b.txt").write_text("later\n")
    git(origin, "add", "b.txt")
    git(origin, "commit", "-qm", "later")
    git(clone, "fetch", "-q")
    return clone


def diff_base(cwd, *args):
    result = subprocess.run(
        ["bash", DIFF_BASE, *args], cwd=cwd, capture_output=True, text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
             "GIT_PAGER": "cat"},
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_diff_base_falls_back_to_origin_main(repo_with_remote):
    out = diff_base(repo_with_remote)
    assert "+feature" in out
    assert "b.txt" not in out  # since the merge-base, not a diff against main's tip


def test_diff_base_uses_origin_head(repo_with_remote):
    git(repo_with_remote, "remote", "set-head", "origin", "main")
    assert "+feature" in diff_base(repo_with_remote)


def test_diff_base_passes_args_to_git_diff(repo_with_remote):
    assert diff_base(repo_with_remote, "--stat").strip().startswith("a.txt")


def test_lazygit_ctrl_g_and_shortcut_share_the_script():
    defaults = load_bundled_defaults()
    command = next(c for c in defaults["lazygit"]["customCommands"] if c["key"] == "<c-g>")["command"]
    assert command == "optmux-diff-base"
    assert defaults["shortcuts"]["C-M-d"]["command"] == "optmux-env optmux-diff-base"
