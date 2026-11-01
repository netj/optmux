import importlib.util
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

from tests.conftest import skip_no_fzf

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


@skip_no_fzf
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


@skip_no_fzf
def test_omni_ranks_tags_and_files_together_by_match_strength(repo):
    (repo / "tags").write_text(
        'hel_per_function_with_a_long_name\tapp.py\t/^x/;"\tf\tline:1\n'
        'Hello\tapp.py\t/^def Hello():$/;"\tf\tline:3\n')
    (repo / "hello.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    top = [r.split("\t")[2].split()[:2] for r in fd.list_omni("hello")]
    # equal matches: the shorter first (the tag name, 5 letters, over hello.txt), the weak fuzzy tag hit last
    assert top == [["tag", "Hello"], ["file", "hello.txt"], ["tag", "hel_per_function_with_a_long_name"]]
    assert not any(r.split("\t")[2].startswith("grep") for r in fd.list_omni("hello"))  # grep is its own source


@skip_no_fzf
def test_omni_without_tags_still_lists_files(repo):
    assert [r.split("\t")[2] for r in fd.list_omni("notes")] == ["file sub/notes.md"]


def test_boost_pulls_recent_ahead_but_only_so_far():
    keys = [f"k{i}" for i in range(50)]
    assert fd.boost(keys, []) == list(range(50))  # nothing recent: match order
    order = fd.boost(keys, ["k10"])  # most recent: up to 20 places
    assert order.index(10) == 0 and order[1:11] == list(range(10))
    assert fd.boost(keys, ["k40"]).index(40) == 21  # a weak match gets 20 places up, no further (it ties 20, behind it)
    assert fd.boost(keys, ["k5", "k3"])[:3] == [3, 5, 0]  # both recent; the better match stays ahead of the newer


def test_recent_roundtrip_and_ordering(tmp_path, monkeypatch):
    monkeypatch.setenv("OPTMUX_DIR", str(tmp_path))
    assert fd.load_recent() == []
    fd.record_opened("files", "a.py\t1\ta.py")
    fd.record_opened("tags", "b.py\t7\tfoo  f  b.py:7")
    fd.record_opened("omni", "a.py\t1\tfile a.py")
    assert fd.load_recent() == ["a.py", "foo\tb.py", "b.py"]
    fd.record_opened("omni", "c.py\t2\ttag  bar  f  c.py:2")
    assert fd.load_recent()[:2] == ["bar\tc.py", "c.py"]
    es = ["x\t1\tx", "b.py\t1\tb.py", "a.py\t1\ta.py"]
    assert fd.by_recency(es, lambda e: e.split("\t")[0], ["a.py", "b.py"]) == [es[2], es[1], es[0]]


@skip_no_fzf
def test_omni_puts_recent_first_with_no_query_and_pulls_it_up_with_one(repo):
    (repo / "tags").write_text("")
    import os
    os.environ["OPTMUX_DIR"] = str(repo / ".od")
    try:
        assert next(fd.list_omni("")).split("\t")[0] == "app.py"  # nothing opened yet: list order
        fd.record_opened("files", "sub/notes.md\t1\tsub/notes.md")
        assert next(fd.list_omni("")).split("\t")[0] == "sub/notes.md"
        assert [r.split("\t")[0] for r in fd.list_omni("s")][0] == "sub/notes.md"
    finally:
        del os.environ["OPTMUX_DIR"]


@pytest.fixture
def fake_ctags(tmp_path_factory, monkeypatch):
    """A stand-in universal-ctags: says what it is, and writes one tag per file it is told to index."""
    outside = tmp_path_factory.mktemp("outside")  # not in the test repo, or ctags would index it
    bin_dir = outside / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "universal-ctags"
    exe.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = --version ]; then echo "Universal Ctags 6.1.0"; exit 0; fi\n'
        'while [ $# -gt 0 ]; do [ "$1" = -f ] && out=$2; shift; done\n'
        'echo run >> "$FAKE_CTAGS_LOG"\n'
        'while read f; do printf "sym_%s\\t%s\\t1;\\"\\tf\\tline:1\\n" "$(basename $f .py)" "$f"; done > "$out"\n')
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{__import__('os').environ['PATH']}")
    monkeypatch.setenv("FAKE_CTAGS_LOG", str(outside / "ctags.log"))
    monkeypatch.setenv("OPTMUX_DIR", str(outside / "od"))
    return outside / "ctags.log"


def test_tags_are_built_on_first_use_and_reused_while_the_project_is_unchanged(repo, fake_ctags):
    assert [l.split("\t")[2].split("  ")[0] for l in fd.list_tags("")] == ["sym_app", "sym_notes.md"]  # the files git lists
    assert fake_ctags.read_text().count("run") == 1
    list(fd.list_tags(""))
    assert fake_ctags.read_text().count("run") == 1  # unchanged: no rebuild, no refresh


def test_user_tags_file_wins_and_is_left_alone(repo, fake_ctags):
    (repo / "tags").write_text('mine\tapp.py\t1;"\tf\tline:1\n')
    assert [l.split("\t")[2].split("  ")[0] for l in fd.list_tags("")] == ["mine"]
    assert not fake_ctags.exists()


def test_stale_tags_are_served_while_a_refresh_is_started(repo, fake_ctags, monkeypatch):
    list(fd.list_tags(""))
    stamp = fd.tags_stamp(str(repo))
    (repo / "new.py").write_text("x")  # an untracked file is a change
    assert fd.tags_stamp(str(repo)) != stamp
    started = []
    monkeypatch.setattr(fd, "refresh_tags", lambda root: started.append(root))
    names = [l.split("\t")[2].split("  ")[0] for l in fd.list_tags("")]
    assert names == ["sym_app", "sym_notes.md"] and started == [str(repo)]
    fd.list_tags("")  # a refresh is under way (lock): do not start another
    list(fd.list_tags(""))
    assert len(started) == 1


def test_no_universal_ctags_means_no_tags(repo, monkeypatch, tmp_path_factory):
    monkeypatch.setenv("OPTMUX_DIR", str(tmp_path_factory.mktemp("od")))
    monkeypatch.setattr(fd, "universal_ctags", lambda: None)
    assert fd.tags_file() is None
