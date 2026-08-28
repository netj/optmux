import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from optmux.cli import _SOCK_PATH_LIMIT, _short_sock_path, main


class _ExecvpCalled(Exception):
    """Raised by mock execvp to simulate process replacement."""
    pass


def _mock_execvp(*args, **kwargs):
    """Mock execvp that raises to stop execution (simulates process replacement)."""
    raise _ExecvpCalled(args)


def _mock_run_side_effect(*args, **kwargs):
    """Default mock for subprocess.run: has-session fails, others succeed."""
    cmd = args[0]
    result = MagicMock()
    if "has-session" in cmd:
        result.returncode = 1  # no existing session
    else:
        result.returncode = 0
    return result


@patch("os.execvp")
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_main_with_yaml_new_session(mock_run, mock_execvp, project_yaml_file):
    """With YAML arg and no existing session: runs tmuxp, creates window, attaches."""
    main(argv=[str(project_yaml_file)])

    # Find the tmuxp load call
    tmuxp_calls = [c for c in mock_run.call_args_list if "tmuxp" in str(c)]
    assert len(tmuxp_calls) == 1
    tmuxp_cmd = tmuxp_calls[0][0][0]
    assert tmuxp_cmd[0] == "tmuxp"
    assert "load" in tmuxp_cmd

    # execvp called with tmux attach
    mock_execvp.assert_called_once()
    assert "attach-session" in mock_execvp.call_args[0][1]


@patch("os.execvp", side_effect=_mock_execvp)
@patch("subprocess.run")
def test_main_with_yaml_existing_session(mock_run, mock_execvp, project_yaml_file):
    """With YAML arg and existing session: just attaches."""
    mock_run.return_value = MagicMock(returncode=0)  # has-session succeeds
    with pytest.raises(_ExecvpCalled):
        main(argv=[str(project_yaml_file)])

    # execvp called with attach
    mock_execvp.assert_called_once()
    assert "attach-session" in mock_execvp.call_args[0][1]

    # tmuxp should NOT have been called
    tmuxp_calls = [c for c in mock_run.call_args_list if "tmuxp" in str(c)]
    assert len(tmuxp_calls) == 0


def test_main_no_args_prints_help(capsys):
    """No args: prints usage and exits 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(argv=[])
    assert exc_info.value.code == 0
    assert "usage:" in capsys.readouterr().err


@patch("os.execvp")
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_main_dot_dir_new_session(mock_run, mock_execvp, tmp_path, monkeypatch):
    """Passing '.' as dir: creates session in cwd, attaches."""
    monkeypatch.chdir(tmp_path)
    main(argv=["."])

    # new-session called
    new_session_calls = [c for c in mock_run.call_args_list if "new-session" in str(c)]
    assert len(new_session_calls) == 1

    mock_execvp.assert_called_once()
    assert "attach-session" in mock_execvp.call_args[0][1]


@patch("os.execvp", side_effect=_mock_execvp)
@patch("subprocess.run")
def test_main_dot_dir_existing_session(mock_run, mock_execvp, tmp_path, monkeypatch):
    """Passing '.' with existing session: just attaches."""
    monkeypatch.chdir(tmp_path)
    mock_run.return_value = MagicMock(returncode=0)
    with pytest.raises(_ExecvpCalled):
        main(argv=["."])

    mock_execvp.assert_called_once()
    assert "attach-session" in mock_execvp.call_args[0][1]


@patch("os.execvp")
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_main_env_vars_set(mock_run, mock_execvp, project_yaml_file):
    """OPTMUX_DIR, OPTMUX_NAME, TMUX_PLUGIN_MANAGER_PATH are set."""
    main(argv=[str(project_yaml_file)])

    assert os.environ.get("OPTMUX_NAME") == "myproject"
    assert "OPTMUX_DIR" in os.environ
    assert os.environ["OPTMUX_DIR"].endswith(".myproject.optmux.d")
    assert "TMUX_PLUGIN_MANAGER_PATH" in os.environ


@patch("os.execvp")
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_main_creates_optmux_dir(mock_run, mock_execvp, project_yaml_file):
    """The .{name}.optmux.d/tmux/ directory is created."""
    main(argv=[str(project_yaml_file)])

    optmux_dir = project_yaml_file.parent / ".myproject.optmux.d"
    assert optmux_dir.is_dir()
    assert (optmux_dir / "tmux").is_dir()
    assert (optmux_dir / "tmux" / "tmux.conf").exists()
    menu_conf = optmux_dir / "tmux" / "tmux.optmux-menu.conf"
    assert menu_conf.exists()
    assert "New Window (C-t c)" in menu_conf.read_text()


@patch("os.execvp")
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_main_generates_shortcuts_conf(mock_run, mock_execvp, project_yaml_file):
    """Shortcut conf files are generated from merged config."""
    main(argv=[str(project_yaml_file)])

    tmux_dir = project_yaml_file.parent / ".myproject.optmux.d" / "tmux"
    shortcuts_conf = tmux_dir / "tmux.optmux-shortcuts.conf"
    assert shortcuts_conf.exists()
    content = shortcuts_conf.read_text()
    # project shortcut should be present
    assert "C-M-b" in content
    # bundled defaults should be merged in
    assert "C-M-s" in content


@patch("os.execvp")
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_main_remaining_args_passed(mock_run, mock_execvp, project_yaml_file):
    """Extra args after YAML are passed to tmuxp."""
    main(argv=[str(project_yaml_file), "--log-level", "debug"])

    tmuxp_calls = [c for c in mock_run.call_args_list if "tmuxp" in str(c)]
    assert len(tmuxp_calls) == 1
    tmuxp_cmd = tmuxp_calls[0][0][0]
    assert "--log-level" in tmuxp_cmd
    assert "debug" in tmuxp_cmd


@patch("os.execvp")
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_nested_different_socket_unsets_tmux(mock_run, mock_execvp, project_yaml_file, monkeypatch, capsys):
    """Running optmux inside a different tmux session unsets $TMUX and prints nesting message."""
    monkeypatch.setenv("TMUX", "/tmp/other-tmux.sock,12345,0")
    main(argv=[str(project_yaml_file)])

    # $TMUX should have been unset
    assert "TMUX" not in os.environ
    # informational message printed
    assert "nesting inside outer tmux session" in capsys.readouterr().err


@patch("os.execvp", side_effect=_mock_execvp)
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_nested_same_socket_switches_to_main(mock_run, mock_execvp, project_yaml_file, monkeypatch):
    """Running optmux inside the same server switches to the main session."""
    yaml_path = Path(str(project_yaml_file)).resolve()
    sock = str(yaml_path.parent / ".myproject.optmux.d" / "tmux" / "tmux.sock")
    monkeypatch.setenv("TMUX", f"{sock},12345,0")
    with pytest.raises(_ExecvpCalled):
        main(argv=[str(project_yaml_file)])

    mock_execvp.assert_called_once()
    assert "switch-client" in mock_execvp.call_args[0][1]
    assert "myproject" in str(mock_execvp.call_args)


@patch("os.execvp")
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_main_dir_arg_as_workdir(mock_run, mock_execvp, tmp_path, monkeypatch):
    """First arg that is a directory changes workdir, then opens session there."""
    # Start in a different directory
    monkeypatch.chdir("/")
    main(argv=[str(tmp_path)])

    # session should be named after tmp_path, not "/"
    new_session_calls = [c for c in mock_run.call_args_list if "new-session" in str(c)]
    assert len(new_session_calls) == 1
    assert tmp_path.name in str(new_session_calls[0])

    mock_execvp.assert_called_once()
    assert "attach-session" in mock_execvp.call_args[0][1]


@patch("os.execvp", side_effect=_mock_execvp)
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_main_tmux_passthrough(mock_run, mock_execvp, tmp_path, monkeypatch):
    """`optmux DIR tmux ARGS...` execs tmux directly with the resolved socket, bypassing tmuxp."""
    monkeypatch.chdir("/")
    with pytest.raises(_ExecvpCalled) as exc_info:
        main(argv=[str(tmp_path), "tmux", "list-sessions"])

    args = exc_info.value.args[0]
    assert args[0] == "tmux"
    argv_passed = args[1]
    assert argv_passed[0] == "tmux"
    assert "-S" in argv_passed
    assert argv_passed[-1] == "list-sessions"
    # no tmuxp load, no new-session, no attach — a pure passthrough
    assert not any("new-session" in str(c) for c in mock_run.call_args_list)


@patch("os.execvp")
@patch("subprocess.run", side_effect=_mock_run_side_effect)
def test_no_tmux_env_no_nesting_message(mock_run, mock_execvp, project_yaml_file, monkeypatch, capsys):
    """Without $TMUX set, no nesting messages are printed."""
    monkeypatch.delenv("TMUX", raising=False)
    main(argv=[str(project_yaml_file)])

    err = capsys.readouterr().err
    assert "nesting" not in err
    assert "already inside" not in err


def test_short_sock_path_short_path():
    """Short paths are returned as-is."""
    short_dir = Path(tempfile.mkdtemp(prefix="om-"))
    try:
        tmux_dir = short_dir / "t"
        tmux_dir.mkdir()
        assert len(str(tmux_dir / "tmux.sock")) < _SOCK_PATH_LIMIT
        result = _short_sock_path(tmux_dir)
        assert result == str(tmux_dir / "tmux.sock")
        assert not (tmux_dir / "tmux.sock").is_symlink()
    finally:
        import shutil
        shutil.rmtree(short_dir, ignore_errors=True)


def test_short_sock_path_long_path(tmp_path):
    """Paths exceeding sun_path limit get redirected to a temp directory."""
    padding = "x" * 200
    tmux_dir = tmp_path / padding / "tmux"
    tmux_dir.mkdir(parents=True)
    natural = str(tmux_dir / "tmux.sock")
    assert len(natural) >= _SOCK_PATH_LIMIT

    result = _short_sock_path(tmux_dir)
    assert len(result) < _SOCK_PATH_LIMIT
    assert result.startswith(tempfile.gettempdir())
    # symlink created at original location
    link = tmux_dir / "tmux.sock"
    assert link.is_symlink()
    assert os.readlink(str(link)) == result


def test_short_sock_path_deterministic(tmp_path):
    """Same input always produces the same short path."""
    padding = "x" * 200
    tmux_dir = tmp_path / padding / "tmux"
    tmux_dir.mkdir(parents=True)
    assert _short_sock_path(tmux_dir) == _short_sock_path(tmux_dir)
