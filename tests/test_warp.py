"""Tests for the warp subcommand."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from optmux.cli import cmd_warp, main


class _ExecvpCalled(Exception):
    pass


def _mock_execvp(*args, **kwargs):
    raise _ExecvpCalled(args)


@pytest.fixture
def warp_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TMUX", raising=False)
    sock = str(tmp_path / "tmux.sock")
    return {
        "resolved": {
            "name": "myproject",
            "session_name": "myproject",
            "yaml_path": tmp_path / "myproject.optmux.yaml",
            "yaml_file": str(tmp_path / "myproject.optmux.yaml"),
            "optmux_dir": tmp_path / ".myproject.optmux.d",
            "tmux_dir": tmp_path / ".myproject.optmux.d" / "tmux",
            "sock": sock,
            "tmux_cmd": ["tmux", "-S", sock],
        },
        "workdir": os.path.realpath(str(tmp_path)),
        "default_warp_name": f"myproject//{tmp_path.name}",
    }


def _make_run_mock(main_session="myproject", main_exists=True, panes="",
                   warp_session=None, warp_exists=False, warp_panes="",
                   new_session_window_id="@99"):
    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        result = MagicMock()

        if "has-session" in cmd:
            target = cmd[cmd.index("-t") + 1] if "-t" in cmd else None
            if target == main_session:
                result.returncode = 0 if main_exists else 1
            elif target == warp_session and warp_exists:
                result.returncode = 0
            else:
                result.returncode = 1
        elif "list-panes" in cmd:
            target = cmd[cmd.index("-t") + 1] if "-t" in cmd else None
            if target == main_session:
                result.stdout = panes
                result.returncode = 0
            elif target == warp_session:
                result.stdout = warp_panes
                result.returncode = 0
            else:
                result.returncode = 1
                result.stderr = "session not found"
        elif "new-session" in cmd:
            result.returncode = 0
            result.stdout = f"{new_session_window_id}\n"
        elif "link-window" in cmd:
            result.returncode = 0
        elif "kill-window" in cmd:
            result.returncode = 0
        else:
            result.returncode = 0

        return result

    return mock_run, calls


def test_warp_main_session_not_running(warp_env, capsys):
    mock_run, _ = _make_run_mock(main_exists=False)
    with patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(SystemExit, match="1"):
            cmd_warp(warp_env["resolved"], [])
    err = capsys.readouterr().err
    assert "not running" in err
    assert "myproject" in err


def test_warp_no_matching_windows(warp_env, capsys):
    panes = "@1\t1\t/other/dir\n@2\t2\t/another/dir\n"
    mock_run, _ = _make_run_mock(
        panes=panes,
        warp_session=warp_env["default_warp_name"],
    )
    with patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(SystemExit, match="1"):
            cmd_warp(warp_env["resolved"], [])
    assert "no windows" in capsys.readouterr().err


def test_warp_normal_creates_and_links(warp_env):
    workdir = warp_env["workdir"]
    warp_name = warp_env["default_warp_name"]
    panes = (
        f"@1\t1\t{workdir}\n"
        f"@2\t2\t/other/dir\n"
        f"@3\t3\t{workdir}\n"
    )
    mock_run, calls = _make_run_mock(
        panes=panes,
        warp_session=warp_name,
    )
    with patch("subprocess.run", side_effect=mock_run):
        with patch("os.execvp", side_effect=_mock_execvp):
            with pytest.raises(_ExecvpCalled):
                cmd_warp(warp_env["resolved"], [])

    link_calls = [c for c in calls if "link-window" in c]
    assert len(link_calls) == 2
    assert any("myproject:1" in str(c) for c in link_calls)
    assert any("myproject:3" in str(c) for c in link_calls)

    new_session_calls = [c for c in calls if "new-session" in c]
    assert len(new_session_calls) == 1
    assert warp_name in str(new_session_calls[0])

    kill_calls = [c for c in calls if "kill-window" in c]
    assert len(kill_calls) == 1
    assert "@99" in str(kill_calls[0])


def test_warp_existing_session_links_missing(warp_env):
    workdir = warp_env["workdir"]
    warp_name = warp_env["default_warp_name"]
    panes = (
        f"@1\t1\t{workdir}\n"
        f"@2\t2\t/other/dir\n"
        f"@3\t3\t{workdir}\n"
    )
    mock_run, calls = _make_run_mock(
        panes=panes,
        warp_session=warp_name,
        warp_exists=True,
        warp_panes="@1\n",  # @1 already linked
    )
    with patch("subprocess.run", side_effect=mock_run):
        with patch("os.execvp", side_effect=_mock_execvp):
            with pytest.raises(_ExecvpCalled):
                cmd_warp(warp_env["resolved"], [])

    link_calls = [c for c in calls if "link-window" in c]
    assert len(link_calls) == 1
    assert "myproject:3" in str(link_calls[0])

    new_session_calls = [c for c in calls if "new-session" in c]
    assert len(new_session_calls) == 0


def test_warp_existing_session_all_linked(warp_env):
    workdir = warp_env["workdir"]
    warp_name = warp_env["default_warp_name"]
    panes = f"@1\t1\t{workdir}\n@3\t3\t{workdir}\n"
    mock_run, calls = _make_run_mock(
        panes=panes,
        warp_session=warp_name,
        warp_exists=True,
        warp_panes="@1\n@3\n",
    )
    with patch("subprocess.run", side_effect=mock_run):
        with patch("os.execvp", side_effect=_mock_execvp):
            with pytest.raises(_ExecvpCalled) as exc_info:
                cmd_warp(warp_env["resolved"], [])

    assert "attach-session" in str(exc_info.value)
    link_calls = [c for c in calls if "link-window" in c]
    assert len(link_calls) == 0


def test_warp_default_name(warp_env):
    workdir = warp_env["workdir"]
    warp_name = warp_env["default_warp_name"]
    panes = f"@1\t1\t{workdir}\n"
    mock_run, calls = _make_run_mock(
        panes=panes,
        warp_session=warp_name,
    )
    with patch("subprocess.run", side_effect=mock_run):
        with patch("os.execvp", side_effect=_mock_execvp):
            with pytest.raises(_ExecvpCalled):
                cmd_warp(warp_env["resolved"], [])

    new_session_calls = [c for c in calls if "new-session" in c]
    assert warp_name in str(new_session_calls[0])
    assert warp_name == f"myproject//{Path(workdir).name}"


def test_warp_custom_name(warp_env):
    workdir = warp_env["workdir"]
    mock_run, calls = _make_run_mock(
        panes=f"@1\t1\t{workdir}\n",
        warp_session="my-custom-warp",
    )
    with patch("subprocess.run", side_effect=mock_run):
        with patch("os.execvp", side_effect=_mock_execvp):
            with pytest.raises(_ExecvpCalled):
                cmd_warp(warp_env["resolved"], ["my-custom-warp"])

    new_session_calls = [c for c in calls if "new-session" in c]
    assert "my-custom-warp" in str(new_session_calls[0])


def test_warp_custom_workdir(warp_env, tmp_path):
    custom_dir = tmp_path / "subdir"
    custom_dir.mkdir()
    custom_workdir = os.path.realpath(str(custom_dir))
    panes = f"@5\t5\t{custom_workdir}\n@6\t6\t/other\n"
    warp_name = f"myproject//{custom_dir.name}"
    mock_run, calls = _make_run_mock(
        panes=panes,
        warp_session=warp_name,
    )
    with patch("subprocess.run", side_effect=mock_run):
        with patch("os.execvp", side_effect=_mock_execvp):
            with pytest.raises(_ExecvpCalled):
                cmd_warp(warp_env["resolved"], [warp_name, str(custom_dir)])

    link_calls = [c for c in calls if "link-window" in c]
    assert len(link_calls) == 1
    assert "myproject:5" in str(link_calls[0])


def test_warp_same_socket_uses_switch_client(warp_env, monkeypatch):
    workdir = warp_env["workdir"]
    warp_name = warp_env["default_warp_name"]
    sock = warp_env["resolved"]["sock"]
    monkeypatch.setenv("TMUX", f"{sock},12345,0")

    panes = f"@1\t1\t{workdir}\n"
    mock_run, _ = _make_run_mock(
        panes=panes,
        warp_session=warp_name,
        warp_exists=True,
        warp_panes="@1\n",
    )
    with patch("subprocess.run", side_effect=mock_run):
        with patch("os.execvp", side_effect=_mock_execvp):
            with pytest.raises(_ExecvpCalled) as exc_info:
                cmd_warp(warp_env["resolved"], [])

    assert "switch-client" in str(exc_info.value)


def test_warp_different_socket_unsets_tmux(warp_env, monkeypatch, capsys):
    workdir = warp_env["workdir"]
    warp_name = warp_env["default_warp_name"]
    monkeypatch.setenv("TMUX", "/tmp/other-tmux.sock,12345,0")

    panes = f"@1\t1\t{workdir}\n"
    mock_run, _ = _make_run_mock(
        panes=panes,
        warp_session=warp_name,
    )
    with patch("subprocess.run", side_effect=mock_run):
        with patch("os.execvp", side_effect=_mock_execvp):
            with pytest.raises(_ExecvpCalled) as exc_info:
                cmd_warp(warp_env["resolved"], [])

    assert "TMUX" not in os.environ
    assert "attach-session" in str(exc_info.value)
    assert "nesting" in capsys.readouterr().err


def test_warp_too_many_args(warp_env, capsys):
    with pytest.raises(SystemExit, match="1"):
        cmd_warp(warp_env["resolved"], ["name", "/dir", "extra"])
    assert "too many arguments" in capsys.readouterr().err


# --- Subcommand dispatch tests (via main()) ---

@patch("os.execvp")
@patch("subprocess.run")
def test_main_explicit_start_same_as_default(mock_run, mock_execvp, project_yaml_file):
    """optmux foo.yaml start behaves the same as optmux foo.yaml."""
    mock_run.return_value = MagicMock(returncode=0)
    mock_execvp.side_effect = _mock_execvp

    with pytest.raises(_ExecvpCalled):
        main(argv=[str(project_yaml_file), "start"])

    mock_execvp.assert_called_once()
    assert "attach-session" in str(mock_execvp.call_args)


def test_main_unknown_arg_rejected(project_yaml_file, capsys):
    with pytest.raises(SystemExit, match="1"):
        main(argv=[str(project_yaml_file), "unknown"])
    err = capsys.readouterr().err
    assert "unknown argument" in err


def test_main_warp_dispatched(project_yaml_file, capsys):
    """optmux foo.yaml warp dispatches to cmd_warp, which errors because session not running."""
    def mock_run(cmd, **kwargs):
        result = MagicMock()
        if "has-session" in cmd:
            result.returncode = 1
        else:
            result.returncode = 0
        return result

    with patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(SystemExit, match="1"):
            main(argv=[str(project_yaml_file), "warp"])

    assert "not running" in capsys.readouterr().err
