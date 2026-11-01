import importlib.util
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

sys.dont_write_bytecode = True
loader = SourceFileLoader("optmux_find", str(Path(__file__).parent.parent / "optmux/data/bin/optmux-find"))
fd = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(fd)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    (tmp_path / "app.py").write_text("import os\n\ndef Hello():\n    return 'hi'\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub/notes.md").write_text("say hello there\n")
    git("add", ".")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_files_lists_tracked_and_untracked_not_ignored(repo):
    (repo / "new.txt").write_text("x")
    (repo / ".gitignore").write_text("ignored.txt\n")
    (repo / "ignored.txt").write_text("x")
    assert [l.split("\t")[0] for l in fd.list_files("")] == [".gitignore", "app.py", "new.txt", "sub/notes.md"]


def test_grep_is_smart_case_and_carries_line_numbers(repo):
    lines = list(fd.list_grep("hello"))  # lowercase: case-insensitive
    assert [l.split("\t")[:2] for l in lines] == [["app.py", "3"], ["sub/notes.md", "1"]]
    assert [l.split("\t")[:2] for l in fd.list_grep("Hello")] == [["app.py", "3"]]  # capital: exact case
    assert list(fd.list_grep("")) == [] and list(fd.list_grep("h")) == []  # too short to be worth listing


def test_tags_parse_line_field_and_search_patterns(repo):
    (repo / "tags").write_text(
        '!_TAG_FILE_FORMAT\t2\t/extended format/\n'
        'Hello\tapp.py\t/^def Hello():$/;"\tf\tline:3\n'
        'os\tapp.py\t/^import os$/;"\tkind:module\n'
    )
    assert list(fd.list_tags("")) == [
        "app.py\t3\tHello  f  app.py:3",
        "app.py\t1\tos  module  app.py:1",
    ]


def test_editor_command_line_syntax(monkeypatch):
    monkeypatch.setenv("VISUAL", "")
    monkeypatch.setenv("EDITOR", "nvim")
    assert fd.editor_command("a b.py", "7") == "nvim +7 'a b.py'"
    monkeypatch.setenv("EDITOR", "code --wait")
    assert fd.editor_command("a.py", "7") == "code --wait -g a.py:7"


def test_parse_output_and_target():
    assert fd.parse_output("q\nctrl-g\nf.py\t4\tshown\n") == ("q", "ctrl-g", "f.py\t4\tshown")
    assert fd.parse_output("") == ("", "esc", None)
    assert fd.parse_output("q\n\n")[2] is None
    assert fd.target("f.py\t4\tshown") == ("f.py", "4")


def test_state_roundtrip_is_per_project_and_source(tmp_path, monkeypatch):
    monkeypatch.setenv("OPTMUX_DIR", str(tmp_path))
    assert fd.load_state("grep") == ("", None)
    fd.save_state("grep", "def pick", "a.py\t3\tx")
    assert fd.load_state("grep") == ("def pick", "a.py\t3\tx")
    assert fd.load_state("files") == ("", None)
    (tmp_path / "find/grep.last").write_text("garbage")
    assert fd.load_state("grep") == ("", None)


def test_cursor_position_follows_fzf_ranking():
    es = ["src/a.py\t1\tsrc/a.py", "b.py\t1\tb.py", "src/b.py\t1\tsrc/b.py"]
    assert fd.cursor_position(es, "", es[2]) == 3
    assert fd.cursor_position(es, "src", es[2]) == 2  # b.py is filtered out
    assert fd.cursor_position(es, "zzz", es[0]) is None and fd.cursor_position(es, "", None) is None


def test_dedupe_history_keeps_latest_occurrence_in_order(tmp_path):
    h = tmp_path / "h"
    h.write_text("foo\nbar\nfoo\n\nfoo\nbaz\n")
    fd.dedupe_history(h)
    assert h.read_text() == "bar\nfoo\nbaz\n"
    fd.dedupe_history(tmp_path / "missing")  # no history yet is fine


def test_remember_query_appends_dedupes_and_skips_blank(tmp_path):
    h = tmp_path / "h"
    for q in ["foo", "bar", "  ", "foo"]:
        fd.remember_query(h, q)
    assert h.read_text() == "bar\nfoo\n"


def test_state_dir_falls_back_to_xdg_outside_optmux(tmp_path, monkeypatch):
    monkeypatch.delenv("OPTMUX_DIR", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert fd.state_dir() == tmp_path / "optmux"


def test_grep_half_typed_regex_falls_back_to_plain_text(repo):
    (repo / "c.txt").write_text("call(x) and [a-z\n")
    (repo / "c.txt").write_text("call(x) and [a-z\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    assert [l.split("\t")[:2] for l in fd.list_grep("[a-z")] == [["c.txt", "1"]]  # not a valid regex yet
    assert [l.split("\t")[:2] for l in fd.list_grep("call(")] == [["c.txt", "1"]]
    assert list(fd.list_grep("no such thing (")) == []


def test_grep_is_sorted_by_file_then_numeric_line(repo):
    (repo / "z.txt").write_text("hello\n" * 12)
    (repo / "a.txt").write_text("x\nhello\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    got = [tuple(l.split("\t")[:2]) for l in fd.list_grep("hello")]
    assert got == sorted(got, key=lambda t: (t[0], int(t[1])))
    assert got[0] == ("a.txt", "2") and got[-1] == ("z.txt", "12")


def test_cursor_position_in_grep_is_plain_list_index():
    es = ["a.py\t1\ta.py:1: foo", "b.py\t2\tb.py:2: bar"]
    assert fd.cursor_position(es, "zzz", es[1], filtered=False) == 2  # fzf would filter both out
