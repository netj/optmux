import subprocess
from unittest.mock import patch

import pytest

from optmux import cli, pick
from tests.conftest import skip_no_tmux


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path / "state"


def make_dir(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return d


def test_record_upserts_by_target(tmp_path):
    a = make_dir(tmp_path, "a")
    pick.record_project("dir", a, "a", "/s/1", now=100)
    pick.record_project("dir", a, "a", "/s/2", now=200)
    [p] = pick.load_registry()
    assert (p.last_used, p.sock) == (200, "/s/2")


def test_record_prunes_vanished_targets(tmp_path):
    a, b = make_dir(tmp_path, "a"), make_dir(tmp_path, "b")
    pick.record_project("dir", a, "a", "/s/a", now=1)
    a.rmdir()
    pick.record_project("dir", b, "b", "/s/b", now=2)
    assert [p.target for p in pick.load_registry()] == [str(b)]


def test_forget(tmp_path):
    a = make_dir(tmp_path, "a")
    pick.record_project("dir", a, "a", "/s/a")
    pick.forget_project(a)
    assert pick.load_registry() == []


@pytest.mark.parametrize("answer, kept", [(False, 1), (True, 0)])
def test_ctrl_x_forgets_a_stopped_project_only_on_yes(tmp_path, answer, kept):
    a = make_dir(tmp_path, "a")
    pick.record_project("dir", a, "a", str(tmp_path / "no.sock"))
    with patch.object(pick, "confirm", return_value=answer) as asked:
        assert pick.run(["--stop-or-forget", str(a)]) == 0
    assert "Forget" in asked.call_args[0][0]
    assert len(pick.load_registry()) == kept


@pytest.mark.parametrize("answer, stops", [(False, 0), (True, 1)])
def test_ctrl_x_stops_a_live_project_only_on_yes(tmp_path, answer, stops):
    a = make_dir(tmp_path, "a")
    pick.record_project("dir", a, "a", "/s/a")
    live = lambda p: setattr(p, "live", True) or p
    with patch.object(pick, "probe", side_effect=live), \
         patch.object(pick, "confirm", return_value=answer) as asked, \
         patch.object(pick.subprocess, "run") as run:
        pick.run(["--stop-or-forget", str(a)])
    assert "Stop" in asked.call_args[0][0]
    assert run.call_count == stops and (not stops or run.call_args[0][0][-2:] == [str(a), "stop"])
    assert len(pick.load_registry()) == 1  # (stopping never forgets)


def test_confirm_without_a_terminal_is_no():
    with patch.object(pick.os, "open", side_effect=OSError):
        assert pick.confirm("Forget?") is False


def test_garbage_lines_ignored(state):
    (state / "optmux").mkdir(parents=True)
    (state / "optmux" / "projects.tsv").write_text("junk\nx\tdir\t/a\ts\t/k\n")
    assert pick.load_registry() == []


def test_idle_projects_ordered_by_last_use(tmp_path, capsys):
    for i, n in enumerate(["old", "new", "mid"]):
        pick.record_project("dir", make_dir(tmp_path, n), n, str(tmp_path / f"{n}.sock"), now=[1, 3, 2][i])
    assert pick.run(["--list"]) == 0
    sessions = [l.split("\t")[3] for l in capsys.readouterr().out.splitlines()]
    assert sessions == ["new", "mid", "old"]


def test_query_filters_and_empty_exits_1(tmp_path, capsys):
    pick.record_project("dir", make_dir(tmp_path, "alpha"), "alpha", "/nope")
    assert pick.run(["--list", "alp"]) == 0
    assert "alpha" in capsys.readouterr().out
    assert pick.run(["--list", "zzz"]) == pick.EXIT_NOTHING


def test_nothing_registered_exits_1(capsys):
    assert pick.run([]) == pick.EXIT_NOTHING
    assert "no projects" in capsys.readouterr().err


def test_select_launches_start_as_child(tmp_path):
    a = make_dir(tmp_path, "a")
    pick.record_project("dir", a, "a", "/nope")
    with patch("subprocess.run") as run:
        assert pick.run(["--select", "1"]) == 0
    argv = run.call_args.args[0]
    assert argv[-2:] == [str(a), "start"]


def test_main_dispatches_pick_without_resolving(tmp_path, capsys):
    with patch.object(cli, "resolve_paths") as resolve, pytest.raises(SystemExit) as e:
        cli.main(["pick", "--list"])
    assert e.value.code == pick.EXIT_NOTHING
    resolve.assert_not_called()


@skip_no_tmux
def test_live_session_detected_and_listed_first(tmp_path, capsys):
    short = tmp_path.parent / f"pk{abs(hash(str(tmp_path))) % 10**6}"
    short.mkdir(exist_ok=True)
    sock = str(short / "t.sock")
    try:
        subprocess.run(["tmux", "-S", sock, "-f", "/dev/null", "new-session", "-d", "-s", "live"], check=True)
        pick.record_project("dir", make_dir(tmp_path, "live"), "live", sock, now=1)
        pick.record_project("dir", make_dir(tmp_path, "idle"), "idle", str(short / "none.sock"), now=9)
        assert pick.run(["--list"]) == 0
        lines = [l.split("\t") for l in capsys.readouterr().out.splitlines()]
        assert [(l[0], l[3]) for l in lines] == [("live", "live"), ("idle", "idle")]
        assert pick.run(["--list", "--live"]) == 0
        assert capsys.readouterr().out.count("\n") == 1
    finally:
        subprocess.run(["tmux", "-S", sock, "kill-server"], capture_output=True)
