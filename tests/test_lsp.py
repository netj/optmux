"""optmux-lsp: language detection and choice, the LSP hub against a fake server, and the config that feeds it."""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
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
    "go": {"extensions": ["go"], "servers": [{"command": "no-such-gopls-xyz", "install": "echo install-gopls"}]},
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
    assert rows == ["src/a.py\t5\trun\x1ffunction\x1fApp\x1f",
                    "/usr/lib/lib.py\t1\tLib\x1fclass\x1f\x1f",
                    "b.py\t1\tNoRange\x1fvariable\x1f\x1f"]


def test_only_go_names_lose_a_qualifier_other_names_with_slash_and_dot_are_left_alone(tmp_path):
    sym = lambda name: {"name": name, "kind": 13, "location": {"uri": (tmp_path / "a.go").as_uri()}}
    names = lambda source: [r.split("\t")[2].split("\x1f")[0] for r in lsp.rows_of([sym("github.com/o/r/pkg/gui.Gui.Layout"), sym("Read docs/README.md")], str(tmp_path), source)]
    assert names("go: gopls")[0] == "Gui.Layout"  # (Go's qualified names are where the qualifier comes from)
    assert names("typescript: tsserver") == ["github.com/o/r/pkg/gui.Gui.Layout", "Read docs/README.md"]


def test_a_package_qualifier_is_dropped_from_a_symbols_name():
    assert lsp.short_name("github.com/org/repo/pkg/gui/controllers/helpers.MergeAndRebaseHelper.Run") == "MergeAndRebaseHelper.Run"
    assert lsp.short_name("github.com/org/repo/pkg/gui.Gui") == "Gui"
    assert lsp.short_name("Gui.Layout") == "Gui.Layout" and lsp.short_name("a/b") == "a/b" and lsp.short_name("") == ""


def test_hub_asks_the_fake_server_and_answers_with_rows(project):
    rows = wait_for(project, "hello", lambda r: r and r[0][0] == "a.py")
    assert [r[:2] for r in rows] == [["a.py", "1"], ["b.py", "4"]]
    assert rows[0][2].startswith("hello_world\x1ffunction\x1fmod\x1f") and rows[0][2].endswith("python")  # which server said so (LANG: command)
    # one more query: answered by the same hub, no new server
    assert [r[0] for r in query(project, "other")] == ["b.py"]


def test_no_rows_explains_why_with_unopenable_hint_rows(project):
    (project / "d.go").write_text("package d\n")
    (project / "e.go").write_text("package e\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    rows = wait_for(project, "zzzz", lambda r: any("gopls" in x[2] for x in r))
    assert [r[:3] for r in rows if r[0] == "!install:go"] == [["!install:go", "0", "go: no language server installed.  Enter runs: echo install-gopls"]]
    assert all(r[0].startswith("!") for r in rows)  # markers, not files: the picker will not try to open them


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
    assert status["go"] == {"state": "missing", "install": "echo install-gopls", "hint": "echo install-gopls",
                            "why": "no server installed"}


def test_a_slow_server_answers_starting_then_rows(project, monkeypatch):
    monkeypatch.setenv("FAKE_LSP_SLOW", "2")
    first = query(project, "hello")
    assert first and first[0][0] == "!wait" and "starting" in first[0][2]
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
    assert len(rows) == 1 and rows[0][0] == "!note" and "restart optmux" in rows[0][2]


# ---- what an independent review found ---------------------------------------------------------------------

def write_config(servers_by_lang):
    (Path(os.environ["OPTMUX_DIR"]) / "find.json").write_text(json.dumps({"lsp": servers_by_lang}))


@pytest.fixture
def hubs():
    made = []
    yield made
    for hub in made:
        hub.shutdown()


def test_concurrent_queries_start_one_server_per_language(project, monkeypatch, tmp_path, hubs):
    log = tmp_path / "init.log"
    monkeypatch.setenv("FAKE_LSP_LOG", str(log))
    monkeypatch.setattr(lsp, "RESCAN_MISSING", 0)
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    write_config({"python": {"extensions": ["py"], "servers": [{"command": "late-lsp-xyz", "install": "x"}]}})
    monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ['PATH']}")
    hub = lsp.Hub(str(project.resolve()))
    hubs.append(hub)
    assert "python" in hub.missing
    shim = shim_dir / "late-lsp-xyz"
    shim.write_text(f"#!/bin/sh\nexec {sys.executable} {FAKE_SERVER}\n")
    shim.chmod(0o755)
    threads = [threading.Thread(target=hub.rescan) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    time.sleep(1)
    assert log.read_text().count("initialize\n") == 1 and list(hub.servers) == ["python"]


def test_a_language_that_left_the_project_does_not_break_the_rescan(project, monkeypatch, hubs):
    monkeypatch.setattr(lsp, "RESCAN_MISSING", 0)
    hub = lsp.Hub(str(project.resolve()))
    hubs.append(hub)
    hub.missing["ruby"] = {"install": "gem install x", "why": "no server installed"}  # not in lang_files
    hub.config["ruby"] = {"extensions": ["rb"], "servers": [{"command": "ruby-lsp"}]}
    hub.scanned_files = 0  # a file rescan: the stale entry is pruned ...
    hub.rescan()
    assert "ruby" not in hub.missing
    hub.missing["ruby"] = {"install": "", "why": ""}
    hub.scanned_missing = 0
    hub.rescan()  # ... and a stale one met by the missing-server pass is no KeyError either
    assert hub.query("hello") is not None


def test_a_dead_server_is_started_again_after_a_while(project, monkeypatch, tmp_path, hubs):
    attempts = tmp_path / "attempts"
    write_config({"python": {"extensions": ["py"], "servers": [{"command": f"sh -c 'echo x >> {attempts}; exit 3'"}]}})
    monkeypatch.setattr(lsp, "RESTART_AFTER", 0.3)
    hub = lsp.Hub(str(project.resolve()))
    hubs.append(hub)
    count = lambda: len(attempts.read_text().split()) if attempts.exists() else 0
    deadline = time.time() + 10
    while count() < 2 and time.time() < deadline:
        time.sleep(0.2)
        hub.rescan()
    assert count() >= 2  # it died, and was tried again


def test_servers_run_with_the_path_they_were_found_on(project, monkeypatch, tmp_path, hubs):
    seen = tmp_path / "seen-path"
    write_config({"python": {"extensions": ["py"], "servers": [
        {"command": f"sh -c 'echo \"$PATH\" > {seen}; exec {sys.executable} {FAKE_SERVER}'"}]}})
    monkeypatch.setattr(lsp, "search_path", lambda: "/marker/bin:" + os.environ["PATH"])
    hubs.append(lsp.Hub(str(project.resolve())))
    for _ in range(50):
        if seen.exists() and seen.read_text().strip():
            break
        time.sleep(0.1)
    assert seen.read_text().startswith("/marker/bin:")


def test_a_tracked_file_that_is_gone_does_not_fail_the_server(project, monkeypatch, tmp_path, hubs):
    log = tmp_path / "methods.log"
    monkeypatch.setenv("FAKE_LSP_LOG", str(log))
    (project / "0gone.py").write_text("x")
    subprocess.run(["git", "add", "0gone.py"], cwd=project, check=True)
    (project / "0gone.py").unlink()  # tracked, but not in the working tree
    write_config({"python": {"extensions": ["py"], "open_first_file": True,
                             "servers": [{"command": f"{sys.executable} {FAKE_SERVER}"}]}})
    hub = lsp.Hub(str(project.resolve()))
    hubs.append(hub)
    for _ in range(50):
        if hub.status().get("python", {}).get("state") == "ready":
            break
        time.sleep(0.1)
    assert hub.status()["python"]["state"] == "ready"
    time.sleep(0.3)
    assert "textDocument/didOpen python" in log.read_text()  # the next file, with its own languageId


def test_language_ids_follow_the_file_not_the_language_name():
    assert lsp.LANGUAGE_IDS["hpp"] == "cpp" and lsp.LANGUAGE_IDS["c"] == "c" and lsp.LANGUAGE_IDS["tsx"] == "typescriptreact"


def test_two_hubs_starting_at_once_leave_one(project):
    root = os.path.realpath(project)
    first = subprocess.Popen([sys.executable, str(SCRIPT), "serve", root], env=os.environ)
    path = lsp.socket_path(root)
    for _ in range(100):
        try:
            lsp.exchange(path, {"op": "status"}, 2)
            break
        except OSError:
            time.sleep(0.1)
    second = subprocess.Popen([sys.executable, str(SCRIPT), "serve", root], env=os.environ)
    assert second.wait(10) == 0  # found the lock taken: no second hub, and the first one's socket is intact
    assert "status" in lsp.exchange(path, {"op": "status"}, 2)
    subprocess.run([sys.executable, str(SCRIPT), "stop"], cwd=project, env=os.environ, timeout=20)
    assert first.wait(10) == 0


def test_a_dead_hubs_leftover_socket_is_no_obstacle(project):
    path = lsp.socket_path(os.path.realpath(project))
    leftover = socket.socket(socket.AF_UNIX)
    leftover.bind(path)
    leftover.close()  # the file stays, nobody listens
    rows = wait_for(project, "hello", lambda r: r and r[0][0] == "a.py")
    assert rows[0][0] == "a.py"


def test_stop_takes_the_hub_down_at_once(project):
    query(project, "hello")
    path = lsp.socket_path(os.path.realpath(project))
    assert os.path.exists(path)
    subprocess.run([sys.executable, str(SCRIPT), "stop"], cwd=project, env=os.environ, timeout=20)
    for _ in range(20):
        if not os.path.exists(path):
            break
        time.sleep(0.05)
    assert not os.path.exists(path)  # not 5 seconds later, when the next accept would have noticed
    assert wait_for(project, "hello", lambda r: r and r[0][0] == "a.py")[0][0] == "a.py"  # and a fresh one starts


# ---- install on Enter, and the quick query omni uses ------------------------------------------------------

def test_the_install_offered_is_the_first_whose_installer_is_present(tmp_path, monkeypatch):
    (tmp_path / "uv").write_text("#!/bin/sh\n")
    (tmp_path / "uv").chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    monkeypatch.setattr(lsp, "search_path", lambda: os.environ["PATH"])
    server = lambda *cmds: {"command": "x", "install": list(cmds) if len(cmds) > 1 else cmds[0]}
    assert lsp.best_install({"servers": [server("brew install a", "uv tool install a", "pip install a")]}) == "uv tool install a"
    # none of the installers here: nothing to run, but the preferred command is still worth telling the user
    assert lsp.best_install({"servers": [server("no-such-brew-xyz install a")]}) == ""
    assert lsp.first_install({"servers": [server("no-such-brew-xyz install a", "no-such-uv-xyz tool install a")]}) == "no-such-brew-xyz install a"
    # a later server whose installer exists beats an earlier one whose does not
    assert lsp.best_install({"servers": [server("no-such-brew-xyz install a"), server("uv tool install b")]}) == "uv tool install b"
    assert lsp.best_install({"servers": [{"command": "x"}]}) == "" and lsp.first_install({"servers": [{"command": "x"}]}) == ""


def test_install_yes_runs_the_command_for_a_language_without_a_server(project, tmp_path):
    marker = tmp_path / "installed"
    write_config({"go": {"extensions": ["go"], "servers": [{"command": "no-such-gopls-xyz", "install": [f"touch {marker}"]}]}})
    for name in ("x.go", "y.go", "z.go"):
        (project / name).write_text("package x\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    out = subprocess.run([sys.executable, str(SCRIPT), "install", "--yes", "go"], cwd=project, env=os.environ,
                         capture_output=True, text=True, timeout=30).stdout
    assert marker.exists() and f"$ touch {marker}" in out and "installed" in out


def test_a_failing_install_says_so(project, tmp_path):
    write_config({"go": {"extensions": ["go"], "servers": [{"command": "no-such-gopls-xyz", "install": ["sh -c 'exit 7'"]}]}})
    for name in ("x.go", "y.go", "z.go"):
        (project / name).write_text("package x\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    out = subprocess.run([sys.executable, str(SCRIPT), "install", "--yes", "go"], cwd=project, env=os.environ,
                         capture_output=True, text=True, timeout=30).stdout
    assert "failed (exit 7)" in out


def test_fast_query_never_starts_a_hub_and_answers_from_a_running_one(project):
    def fast():
        out = subprocess.run([sys.executable, str(SCRIPT), "query", "--fast", "hello"], cwd=project, env=os.environ,
                             capture_output=True, text=True, timeout=30).stdout
        return [line.split("\t") for line in out.splitlines()]
    assert fast() == []
    assert not os.path.exists(lsp.socket_path(os.path.realpath(project)))  # and it started nothing
    wait_for(project, "hello", lambda r: r and r[0][0] == "a.py")  # a normal query starts the hub
    rows = fast()
    assert rows and rows[0][0] == "a.py" and all(r[0] != "" and not r[0].startswith("!") for r in rows)


def test_icons_setting_is_known_and_defaulted():
    assert load_bundled_defaults()["find"]["icons"] == "emoji"
    import io
    from contextlib import redirect_stderr
    err = io.StringIO()
    with redirect_stderr(err):
        _validate_optmux_section({"find": {"icons": "nerd"}}, "src")
    assert err.getvalue() == ""
    with redirect_stderr(err):
        _validate_optmux_section({"find": {"icons": "sparkles", "preview": "off"}}, "src")
    assert "sparkles" in err.getvalue() and "emoji" in err.getvalue() and "find.preview: 'off'" in err.getvalue()


def test_without_a_usable_installer_the_row_is_a_note_not_an_install(project, tmp_path):
    write_config({"go": {"extensions": ["go"], "servers": [{"command": "no-such-gopls-xyz", "install": ["no-such-brew-xyz install gopls"]}]}})
    for name in ("x.go", "y.go", "z.go"):
        (project / name).write_text("package x\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    rows = wait_for(project, "zzzz", lambda r: any("gopls" in x[2] for x in r))
    assert [r[0] for r in rows if "gopls" in r[2]] == ["!note"]
    assert "By hand: no-such-brew-xyz install gopls" in [r[2] for r in rows if "gopls" in r[2]][0]


def test_an_install_that_leaves_no_server_on_the_path_says_so(project):
    write_config({"go": {"extensions": ["go"], "servers": [{"command": "no-such-gopls-xyz", "install": ["true"]}]}})
    for name in ("x.go", "y.go", "z.go"):
        (project / name).write_text("package x\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    out = subprocess.run([sys.executable, str(SCRIPT), "install", "--yes", "go"], cwd=project, env=os.environ,
                         capture_output=True, text=True, timeout=30).stdout
    assert "succeeded, but none of no-such-gopls-xyz is on the PATH" in out and "installed; optmux" not in out


def test_fast_query_without_configuration_prints_nothing(project):
    (Path(os.environ["OPTMUX_DIR"]) / "find.json").unlink()
    out = subprocess.run([sys.executable, str(SCRIPT), "query", "--fast", "hello"], cwd=project, env=os.environ,
                         capture_output=True, text=True, timeout=30).stdout
    assert out == ""


def test_the_places_installers_put_binaries_are_searched(monkeypatch):
    monkeypatch.setenv("GOBIN", "/somewhere/gobin")
    path = lsp.search_path().split(os.pathsep)
    assert path[0] == "/opt/homebrew/bin" and "/somewhere/gobin" in path
    assert str(Path.home() / ".local/bin") in path and str(Path.home() / ".cargo/bin") in path


def test_a_hub_left_running_by_an_older_optmux_is_replaced_not_read(monkeypatch):
    calls = []
    def fake_exchange(path, request, timeout):
        calls.append(request["op"])
        if "stopped" in calls:
            raise OSError("gone")
        if request["op"] == "stop":
            calls.append("stopped")
        return {"rows": ["old\t1\told  function  x  old:1"], "status": {}}  # no protocol: an old hub's answer
    monkeypatch.setattr(lsp, "exchange", fake_exchange)
    started = []
    monkeypatch.setattr(lsp.subprocess, "Popen", lambda *a, **k: started.append(a))
    assert lsp.ask_hub("/p", {"op": "query", "q": "x"}, start=False) is None  # the fast path leaves it be
    assert calls == ["query"] and not started
    lsp.ask_hub("/p", {"op": "query", "q": "x"}, start=True)
    assert "stop" in calls and started  # asked to stop, then started its own


def test_stop_reaches_a_hub_from_an_older_optmux(monkeypatch):
    monkeypatch.setattr(lsp, "exchange", lambda path, request, timeout: {"status": {}})  # no protocol: an old hub
    assert lsp.ask_hub("/p", {"op": "stop"}, start=False) == {"status": {}}  # (asked: it stopped)
    assert lsp.ask_hub("/p", {"op": "query", "q": "x"}, start=False) is None


def test_a_script_is_of_the_language_its_shebang_says(tmp_path):
    def script(name, first):
        (tmp_path / name).write_text(first + "\nx = 1\n")
        return lsp.script_language(str(tmp_path), name)
    assert script("a", "#!/usr/bin/env python3") == ("python", "python")
    assert script("b", "#!/usr/bin/python") == ("python", "python")
    assert script("c", "#!/usr/bin/env -S python3 -u") == ("python", "python")
    assert script("d", "#!/bin/bash") == ("bash", "shellscript")
    assert script("e", "#!/usr/bin/env node") == ("typescript", "javascript")
    assert script("f", "#!/usr/bin/env optmux") is None  # not a language we know
    assert script("g", "no shebang") is None and lsp.script_language(str(tmp_path), "missing") is None
    assert script("h", "#!/usr/bin/env python3.12") == ("python", "python")  # a versioned interpreter


def test_scripts_of_the_projects_languages_are_found_with_a_cap(tmp_path, monkeypatch):
    for n in range(5):
        (tmp_path / f"tool{n}").write_text("#!/usr/bin/env python3\n")
    (tmp_path / "README").write_text("hello\n")
    (tmp_path / "mod.py").write_text("x\n")
    (tmp_path / "run.sh").write_text("#!/bin/bash\n")  # has an extension: the server knows it
    files = [f"tool{n}" for n in range(5)] + ["README", "mod.py", "run.sh", "sub/tool9"]
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub/tool9").write_text("#!/usr/bin/env python\n")
    config = {"python": {"extensions": ["py"]}}
    found = lsp.find_scripts(str(tmp_path), files, config)
    assert sorted(f for f, _ in found["python"]) == sorted([f"tool{n}" for n in range(5)] + ["sub/tool9"])
    assert list(found) == ["python"]  # (bash is not a language of this config)
    monkeypatch.setattr(lsp, "MAX_SCRIPTS", 2)
    assert len(lsp.find_scripts(str(tmp_path), files, config)["python"]) == 2


def test_a_file_that_was_no_script_is_not_opened_again_for_a_day_unless_it_changed(tmp_path, monkeypatch):
    (tmp_path / "LICENSE").write_text("MIT\n")
    config, known = {"python": {"extensions": ["py"]}}, {}
    opened = []
    real = lsp.script_language
    monkeypatch.setattr(lsp, "script_language", lambda root, name: opened.append(name) or real(root, name))
    lsp.find_scripts(str(tmp_path), ["LICENSE"], config, known)
    lsp.find_scripts(str(tmp_path), ["LICENSE"], config, known)
    assert opened == ["LICENSE"]  # the second scan only stat'ed it
    (tmp_path / "LICENSE").write_text("#!/usr/bin/env python3\n")  # it became a script
    assert lsp.find_scripts(str(tmp_path), ["LICENSE"], config, known) == {"python": [("LICENSE", "python")]}
    assert "LICENSE" not in known
    (tmp_path / "NOTES").write_text("n\n")
    lsp.find_scripts(str(tmp_path), ["NOTES"], config, known)
    known["NOTES"] = (known["NOTES"][0], known["NOTES"][1] - lsp.RECHECK_NOT_SCRIPT - 1)  # a day later
    lsp.find_scripts(str(tmp_path), ["NOTES"], config, known)
    assert opened.count("NOTES") == 2


def test_open_scripts_tells_the_server_about_each_one(tmp_path):
    (tmp_path / "tool").write_text("#!/usr/bin/env python3\nclass Style: pass\n")
    sent = []
    server = lsp.LanguageServer.__new__(lsp.LanguageServer)
    server.root, server.scripts, server.send = str(tmp_path), [("tool", "python"), ("gone", "python")], sent.append
    server.open_scripts()
    assert len(sent) == 1  # (the missing one is skipped)
    doc = sent[0]["params"]["textDocument"]
    assert sent[0]["method"] == "textDocument/didOpen" and doc["languageId"] == "python" and "class Style" in doc["text"]
    assert doc["uri"] == (tmp_path / "tool").as_uri()
