#!/usr/bin/env python3
"""A tiny language server for tests: workspace/symbol finds `def NAME` lines of .py files under its cwd.

With FAKE_LSP_LOG set, it appends what it receives (method names) to that file. With FAKE_LSP_SLOW set, it
waits that many seconds before answering `initialize`."""
import json
import os
import re
import sys
import time
from pathlib import Path

log = os.environ.get("FAKE_LSP_LOG")


def read():
    length = None
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        if line.lower().startswith(b"content-length:"):
            length = int(line.split(b":")[1])
    return json.loads(sys.stdin.buffer.read(length))


def send(msg):
    body = json.dumps(msg).encode()
    sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    sys.stdout.buffer.flush()


while (msg := read()) is not None:
    method = msg.get("method")
    if log and method:
        with open(log, "a") as f:
            f.write(method + "\n")
    if method == "initialize":
        time.sleep(float(os.environ.get("FAKE_LSP_SLOW", "0")))
        send({"jsonrpc": "2.0", "id": msg["id"], "result": {"capabilities": {"workspaceSymbolProvider": True}}})
        send({"jsonrpc": "2.0", "id": 900, "method": "window/workDoneProgress/create", "params": {"token": 1}})
    elif method == "workspace/symbol":
        query = msg["params"]["query"].lower()
        out = []
        for path in sorted(Path.cwd().rglob("*.py")):
            for n, line in enumerate(path.read_text().splitlines()):
                m = re.match(r"\s*def (\w+)", line)
                if m and query in m[1].lower():
                    out.append({"name": m[1], "kind": 12, "containerName": "mod",
                                "location": {"uri": path.as_uri(), "range": {"start": {"line": n, "character": 0},
                                                                           "end": {"line": n, "character": 1}}}})
        send({"jsonrpc": "2.0", "id": msg["id"], "result": out})
    elif method == "shutdown":
        send({"jsonrpc": "2.0", "id": msg["id"], "result": None})
    elif method == "exit":
        break
    elif "id" in msg and method:
        send({"jsonrpc": "2.0", "id": msg["id"], "result": None})
