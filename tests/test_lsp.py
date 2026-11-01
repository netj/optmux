"""optmux-lsp: language detection and choice, the LSP hub against a fake server, and the config that feeds it."""

import importlib.util
import json
import os
import subprocess
import sys
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest
import yaml

from optmux.cli import _validate_optmux_section, load_bundled_defaults, merge_optmux, setup_tools_env

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).parent.parent / "optmux/data/bin/optmux-lsp"
FAKE_SERVER = Path(__file__).parent / "fixtures/fake_lsp_server.py"
loader = SourceFileLoader("optmux_lsp", str(SCRIPT))
lsp = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(lsp)

CONFIG = {
    "python": {"extensions": ["py"], "servers": [{"command": "nonexistent-lsp-xyz --stdio", "install": "brew install xyz"},
                                                  {"command": f"{sys.executable} {FAKE_SERVER}", "install": "n/a"}]},
    "go": {"extensions": ["go"], "servers": [{"command": "no-such-gopls-xyz", "install": "brew install gopls"}]},
}


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A git repo of python files (and a lone go file), a find.json beside it, and cleanup of its hub."""
    root = tmp_path / "proj"
    root.mkdir()
    for name, body in {"a.py": "def hello_world():\n    pass\n", "b.py": "def other():\n    pass\n\ndef hello_again():\n    pass\n",
                       "c.py": "x = 1\n", "main.go": "package main\n"}.items():
        (root / name).write_text(body)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    state = tmp_path / "state"
    state.mkdir()
    (state / "find.json").write_text(json.dumps({"lsp": CONFIG}))
    monkeypatch.setenv("OPTMUX_DIR", str(state))
    monkeypatch.setenv("OPTMUX_LSP_IDLE", "60")
    yield root
    subprocess.run([sys.executable, str(SCRIPT), "stop"], cwd=root, env=os.environ, capture_output=True, timeout=20)


def query(root, text):
    out = subprocess.run([sys.executable, str(SCRIPT), "query", text], cwd=root, env=os.environ,
                         capture_output=True, text=True, timeout=30).stdout
    return [line.split("\t") for line in out.splitlines()]


def wait_for(root, text, want, seconds=15):
    deadline = time.time() + seconds
    while True:
        rows = query(root, text)
        if want(rows) or time.time() > deadline:
            return rows
        time.sleep(0.3)


def test_languages_need_enough_of_the_project():
    cfg = {"python": {"extensions": ["py"]}, "go": {"extensions": [".go"]}, "bash": {"extensions": ["sh"]}}
    files = [f"a{i}.py" for i in range(20)] + ["x.go"] * 5 + ["run.sh"] * 3 + ["README.md"]
    # every language here has at least 3 files and 5% of the 28 that have a known language
    assert list(lsp.detect_languages(files, cfg)) == ["python", "go", "bash"]  # most files first
    assert lsp.detect_languages(["a.py", "b.py", "x.go"], cfg) == {}  # fewer than 3 each
    many = [f"a{i}.py" for i in range(100)]
    assert lsp.detect_languages(many + ["a.go"] * 3, cfg) == {"python": many}  # 3 of 103 files is under 5%


def test_first_installed_server_wins_and_shorthand_comes_first(tmp_path, monkeypatch):
    (tmp_path / "second").write_text("#!/bin/sh\n")
    (tmp_path / "second").chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    cfg = {"servers": [{"command": "first-missing --x"}, {"command": "second --stdio"}]}
    argv, server = lsp.installed_server(cfg)
    assert argv == [str(tmp_path / "second"), "--stdio"] and server["command"] == "second --stdio"
    cfg["command"] = "second --short"
    assert lsp.installed_server(cfg)[0][1] == "--short"  # the shorthand goes first
    assert lsp.installed_server({"servers": [{"command": "nope-xyz"}]}) is None


def test_rows_use_relative_paths_one_based_lines_and_kind_names(tmp_path):
    root = str(tmp_path)
    sym = lambda name, kind, uri, line, **kw: {"name": name, "kind": kind, "location": {"uri": uri, "range": {"start": {"line": line}}}, **kw}
    rows = list(lsp.rows_of([
        sym("run", 12, (tmp_path / "src/a.py").as_uri(), 4, containerName="App"),
        sym("Lib", 5, "file:///usr/lib/lib.py", 0),
        {"name": "NoRange", "kind": 13, "location": {"uri": (tmp_path / "b.py").as_uri()}},
        {"name": "NoLocation"},
    ], root))
    assert rows == ["src/a.py\t5\trun  function  App  src/a.py:5",
                    "/usr/lib/lib.py\t1\tLib  class  /usr/lib/lib.py:1",
                    "b.py\t1\tNoRange  variable  b.py:1"]


def test_hub_asks_the_fake_server_and_answers_with_rows(project):
    rows = wait_for(project, "hello", lambda r: r and r[0][0] == "a.py")
    assert [r[:2] for r in rows] == [["a.py", "1"], ["b.py", "4"]]
    assert rows[0][2] == "hello_world  function  mod  a.py:1"
    # one more query: answered by the same hub, no new server
    assert [r[0] for r in query(project, "other")] == ["b.py"]


def test_no_rows_explains_why_with_unopenable_hint_rows(project):
    (project / "d.go").write_text("package d\n")
    (project / "e.go").write_text("package e\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    rows = wait_for(project, "zzzz", lambda r: any("gopls" in x[2] for x in r))
    hints = [r[2] for r in rows]
    assert "go: no language server installed.  brew install gopls" in hints
    assert all(r[0] == "" for r in rows)  # no file: the picker will not try to open them


def test_status_lists_each_language_and_its_state(project):
    (project / "d.go").write_text("package d\n")
    (project / "e.go").write_text("package e\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    wait_for(project, "x", lambda r: True)
    status = {}
    for _ in range(50):
        status = json.loads(subprocess.run([sys.executable, str(SCRIPT), "status"], cwd=project, env=os.environ,
                                           capture_output=True, text=True, timeout=30).stdout)
        if status.get("python", {}).get("state") == "ready":
            break
        time.sleep(0.3)
    assert status["python"]["state"] == "ready"
    assert status["go"] == {"state": "missing", "install": "brew install gopls", "why": "no server installed"}


def test_a_slow_server_answers_starting_then_rows(project, monkeypatch):
    monkeypatch.setenv("FAKE_LSP_SLOW", "2")
    first = query(project, "hello")
    assert first and first[0][0] == "" and "starting" in first[0][2]
    assert wait_for(project, "hello", lambda r: r and r[0][0] == "a.py", seconds=20)[0][0] == "a.py"


def test_empty_query_asks_nothing(project):
    assert query(project, "   ") == []


# ---- configuration ----------------------------------------------------------------------------------------

def test_bundled_defaults_cover_the_main_languages_with_install_hints():
    lang = load_bundled_defaults()["find"]["lsp"]
    assert {"python", "typescript", "go", "rust", "c"} <= set(lang)
    for name, cfg in lang.items():
        assert cfg["extensions"] and cfg["servers"], name
        assert all(s["command"] and s["install"] for s in cfg["servers"]), name


def test_find_config_merges_per_language_and_replaces_server_lists():
    bundled = {"find": {"lsp": {"python": {"extensions": ["py"], "servers": [{"command": "a"}]}, "go": {"extensions": ["go"]}}}}
    mine = {"find": {"lsp": {"python": {"servers": [{"command": "mine", "install": "x"}]}, "go": {"enabled": False}}}}
    merged = merge_optmux(bundled, mine)["find"]["lsp"]
    assert merged["python"] == {"extensions": ["py"], "servers": [{"command": "mine", "install": "x"}]}
    assert merged["go"] == {"extensions": ["go"], "enabled": False}


def test_find_config_typos_are_warned_about(capsys):
    _validate_optmux_section({"find": {"lsp": {"python": {"serverz": [], "servers": [{"comand": "x"}]}}, "lspp": {}}}, "src")
    err = capsys.readouterr().err
    assert "lspp" in err and "serverz" in err and "comand" in err


def test_setup_tools_env_writes_the_merged_find_section(tmp_path):
    optmux = merge_optmux(load_bundled_defaults(), {"find": {"lsp": {"python": {"enabled": False}}}})
    data_dir = Path(__file__).parent.parent / "optmux/data"
    setup_tools_env(tmp_path, data_dir, optmux)
    written = json.loads((tmp_path / "find.json").read_text())
    assert written["lsp"]["python"]["enabled"] is False and written["lsp"]["go"]["servers"]
    assert (tmp_path / "bin/optmux-lsp").stat().st_mode & 0o111  # installed, executable


def test_disabled_languages_are_dropped_by_the_loader(tmp_path, monkeypatch):
    (tmp_path / "find.json").write_text(json.dumps({"lsp": {"python": {"enabled": False}, "go": {"extensions": ["go"]}}}))
    monkeypatch.setenv("OPTMUX_DIR", str(tmp_path))
    assert list(lsp.load_config()) == ["go"]


def test_a_server_installed_while_the_hub_runs_is_picked_up(project, monkeypatch, tmp_path):
    monkeypatch.setenv("OPTMUX_LSP_RESCAN", "0.2")
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    cfg = {"python": {"extensions": ["py"], "servers": [{"command": "late-lsp-xyz", "install": "brew install late"}]}}
    (Path(os.environ["OPTMUX_DIR"]) / "find.json").write_text(json.dumps({"lsp": cfg}))
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ['PATH']}")
    assert "no language server installed" in query(project, "hello")[0][2]
    shim = shim_dir / "late-lsp-xyz"  # `brew install` finishes
    shim.write_text(f"#!/bin/sh\nexec {sys.executable} {FAKE_SERVER}\n")
    shim.chmod(0o755)
    rows = wait_for(project, "hello", lambda r: r and r[0][0] == "a.py")
    assert [r[:2] for r in rows] == [["a.py", "1"], ["b.py", "4"]]


def test_a_missing_configuration_is_explained_not_silent(project):
    (Path(os.environ["OPTMUX_DIR"]) / "find.json").unlink()
    rows = query(project, "hello")
    assert len(rows) == 1 and rows[0][0] == "" and "restart optmux" in rows[0][2]
