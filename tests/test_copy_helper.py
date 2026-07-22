import os
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest


COPY_HELPER = Path(__file__).resolve().parents[1] / "optmux" / "data" / "copy.sh"


@pytest.fixture
def short_socket_path():
    """Keep Unix socket paths below macOS's sun_path limit."""
    with tempfile.TemporaryDirectory(prefix="optmux-copy-", dir="/tmp") as directory:
        yield Path(directory) / "relay.sock"


def relay_env():
    env = os.environ.copy()
    env.pop("OPTMUX_COPY_COMMAND", None)
    env.pop("OPTMUX_PBCOPY_SOCKET", None)
    return env


def run_copy(payload, env):
    return subprocess.run(
        [str(COPY_HELPER)],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
    )


def test_copy_helper_uses_explicit_copy_command(tmp_path):
    copied = tmp_path / "copied.txt"
    env = relay_env()
    env["COPY_OUTPUT"] = str(copied)
    env["OPTMUX_COPY_COMMAND"] = 'cat > "$COPY_OUTPUT"'

    result = run_copy("forwarded clipboard", env)

    assert result.returncode == 0
    assert copied.read_text() == "forwarded clipboard"


def test_copy_helper_propagates_explicit_command_failure():
    env = relay_env()
    env["OPTMUX_COPY_COMMAND"] = "cat >/dev/null; exit 23"

    result = run_copy("clipboard data", env)

    assert result.returncode == 23


def test_copy_helper_prefers_explicit_command_over_socket(tmp_path, short_socket_path):
    copied = tmp_path / "copied.txt"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(short_socket_path))
        env = relay_env()
        env["COPY_OUTPUT"] = str(copied)
        env["OPTMUX_COPY_COMMAND"] = 'cat > "$COPY_OUTPUT"'
        env["OPTMUX_PBCOPY_SOCKET"] = str(short_socket_path)

        result = run_copy("command wins", env)

    assert result.returncode == 0
    assert copied.read_text() == "command wins"


def test_copy_helper_sends_complete_payload_to_unix_socket(short_socket_path):
    received = []

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(short_socket_path))
        server.listen(1)

        def receive():
            connection, _ = server.accept()
            with connection:
                chunks = []
                while chunk := connection.recv(4096):
                    chunks.append(chunk)
                received.append(b"".join(chunks))

        receiver = threading.Thread(target=receive, daemon=True)
        receiver.start()
        env = relay_env()
        env["OPTMUX_PBCOPY_SOCKET"] = str(short_socket_path)

        result = run_copy("socket clipboard\nwith unicode: 안녕", env)
        receiver.join(timeout=2)

    assert result.returncode == 0
    assert not receiver.is_alive()
    assert received == ["socket clipboard\nwith unicode: 안녕".encode()]


def test_copy_helper_rejects_missing_socket(tmp_path):
    missing_socket = tmp_path / "missing.sock"
    env = relay_env()
    env["OPTMUX_PBCOPY_SOCKET"] = str(missing_socket)

    result = run_copy("clipboard data", env)

    assert result.returncode == 1
    assert str(missing_socket) in result.stderr


def test_copy_helper_reports_missing_netcat(short_socket_path):
    env = relay_env()
    env["PATH"] = ""
    env["OPTMUX_PBCOPY_SOCKET"] = str(short_socket_path)

    result = run_copy("clipboard data", env)

    assert result.returncode == 1
    assert "requires nc" in result.stderr


def test_copy_helper_requires_explicit_relay_configuration():
    result = run_copy("clipboard data", relay_env())

    assert result.returncode == 1
    assert "clipboard relay is not configured" in result.stderr
