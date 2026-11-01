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
    top = [(fd.split_icon(r.split("\t")[2])[0], fd.split_icon(r.split("\t")[2])[1].split()[0]) for r in fd.list_omni("hello")]
    # equal matches: the shorter first (the tag name, 5 letters, over hello.txt), the weak fuzzy tag hit last
    assert top == [("tag", "Hello"), ("file", "hello.txt"), ("tag", "hel_per_function_with_a_long_name")]


@skip_no_fzf
def test_omni_without_tags_still_lists_files(repo):
    assert [fd.split_icon(r.split("\t")[2]) for r in fd.list_omni("notes")] == [("file", "sub/notes.md")]


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
    (repo / "new.py").write_text("x")
    subprocess.run(["git", "add", "new.py"], cwd=repo, check=True)  # a tracked change; untracked files are not indexed
    assert fd.tags_stamp(str(repo)) != stamp
    started = []
    monkeypatch.setattr(fd, "refresh_tags", lambda root: started.append(root))
    names = [l.split("\t")[2].split("  ")[0] for l in fd.list_tags("")]
    assert names == ["sym_app", "sym_notes.md"] and started == [str(repo)]
    list(fd.list_tags(""))  # a refresh is under way (lock): do not start another
    assert len(started) == 1


FAKE_CTAGS = (
    "#!/bin/sh\n"
    '%s'
    'while [ $# -gt 0 ]; do [ "$1" = -f ] && out=$2; shift; done\n'
    'while read f; do printf "sym_%%s\\t%%s\\t1;\\"\\tf\\n" "$(basename $f .py)" "$f"; done > "$out"\n')


def test_ctags_falls_back_to_plainer_invocations_and_gives_up_cleanly(repo, fake_ctags, monkeypatch, tmp_path_factory):
    exe = fake_ctags.parent / "bin" / "universal-ctags"
    # exuberant-like: refuses --fields, so the line numbers come from the patterns
    exe.write_text(FAKE_CTAGS % 'for a in "$@"; do case $a in --fields*) exit 2;; esac; done\n')
    assert [l.split("\t")[:2] for l in fd.list_tags("")] == [["app.py", "1"], ["sub/notes.md", "1"]]
    # BSD-like: reads no file list at all
    exe.write_text("#!/bin/sh\nexit 1\n")
    monkeypatch.setenv("OPTMUX_DIR", str(tmp_path_factory.mktemp("od2")))
    assert fd.tags_file(check=True) is None


def test_refresh_launch_failure_releases_the_lock(repo, fake_ctags, monkeypatch):
    list(fd.list_tags(""))
    (repo / "x.py").write_text("x")
    subprocess.run(["git", "add", "x.py"], cwd=repo, check=True)

    def boom(root):
        raise OSError("cannot run")
    monkeypatch.setattr(fd, "refresh_tags", boom)
    assert list(fd.list_tags(""))  # still serves the old tags
    assert not list(fd.tags_cache(str(repo)).parent.glob("*.lock"))


def test_per_keystroke_reloads_never_build_or_check(repo, fake_ctags, monkeypatch):
    monkeypatch.setattr(fd, "CHECK_TAGS", False)
    assert list(fd.list_tags("")) == [] and not fake_ctags.exists()  # nothing cached, nothing built
    monkeypatch.setattr(fd, "CHECK_TAGS", True)
    assert list(fd.list_tags(""))
    monkeypatch.setattr(fd, "CHECK_TAGS", False)
    (repo / "x.py").write_text("x")
    subprocess.run(["git", "add", "x.py"], cwd=repo, check=True)
    monkeypatch.setattr(fd, "refresh_tags", lambda root: pytest.fail("a reload must not start a refresh"))
    assert list(fd.list_tags(""))


def test_a_failing_ctags_is_not_retried_for_a_while(repo, fake_ctags):
    (fake_ctags.parent / "bin" / "universal-ctags").write_text('#!/bin/sh\necho run >> "$FAKE_CTAGS_LOG"\nexit 1\n')
    assert list(fd.list_tags("", warn=False)) == []
    assert list(fd.list_tags("", warn=False)) == []
    assert fake_ctags.read_text().count("run") == 3  # the three invocations of one attempt; none on the second open


def test_a_held_lock_means_someone_else_is_building(repo, fake_ctags):
    lock = fd.tags_cache(str(repo)).with_suffix(".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch()
    assert list(fd.list_tags("", warn=False)) == [] and not fake_ctags.exists()
    old = fd.time.time() - fd.LOCK_TTL - 1
    __import__("os").utime(lock, (old, old))  # presumed dead: take over
    assert list(fd.list_tags("", warn=False))


def test_managed_tags_only_in_git_projects(tmp_path_factory, monkeypatch, fake_ctags):
    monkeypatch.chdir(tmp_path_factory.mktemp("plain"))
    assert fd.tags_file() is None and not fake_ctags.exists()


def test_files_to_index_include_oddly_named_ones(repo, monkeypatch):
    (repo / "dir with space").mkdir()
    (repo / "dir with space" / "é.py").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    monkeypatch.setenv("OPTMUX_DIR", str(repo.parent / "elsewhere"))
    monkeypatch.chdir(repo)
    assert "dir with space/é.py" in fd.project_files(str(repo))


def test_no_ctags_means_no_tags(repo, monkeypatch, tmp_path_factory):
    monkeypatch.setenv("OPTMUX_DIR", str(tmp_path_factory.mktemp("od")))
    monkeypatch.setattr(fd, "find_ctags", lambda: None)
    assert fd.tags_file() is None


def test_files_to_index_are_the_tracked_ones_without_optmuxs_own_state(repo, monkeypatch):
    (repo / "untracked.py").write_text("x")
    (repo / ".optmux.d/find").mkdir(parents=True)
    (repo / ".optmux.d/find/x.tags").write_text("x")
    subprocess.run(["git", "add", "-f", ".optmux.d"], cwd=repo, check=True)  # even if the project tracks it
    monkeypatch.setenv("OPTMUX_DIR", str(repo / ".optmux.d"))
    monkeypatch.chdir(repo)
    assert fd.project_files(str(repo)) == ["app.py", "sub/notes.md"]


def test_the_picker_works_from_the_project_root(repo, monkeypatch, tmp_path_factory):
    import os
    (repo / "sub").mkdir(exist_ok=True)
    monkeypatch.chdir(repo / "sub")
    assert fd.enter_project_root()
    assert os.path.samefile(os.getcwd(), repo)
    monkeypatch.chdir(tmp_path_factory.mktemp("plain"))  # not a project: stays where it is
    here = os.getcwd()
    assert fd.enter_project_root() is None and os.getcwd() == here


# ---- icons, language-server symbols in omni, install rows ---------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_icon_style(monkeypatch):
    monkeypatch.delenv("OPTMUX_FIND_ICONS", raising=False)
    fd.icon_style.cache_clear()
    yield
    fd.icon_style.cache_clear()


def test_icons_by_style_and_back(monkeypatch):
    assert fd.with_icon("tag", "x  f  a.py:1").startswith("🔖 ")  # emoji is the default
    for style in fd.ICON_STYLES:
        monkeypatch.setenv("OPTMUX_FIND_ICONS", style)
        fd.icon_style.cache_clear()
        for kind in fd.ICON_STYLES[style]:
            assert fd.split_icon(fd.with_icon(kind, "rest of  the row")) == (kind, "rest of  the row"), (style, kind)
    assert fd.split_icon("plain row") == (None, "plain row")
    monkeypatch.setenv("OPTMUX_FIND_ICONS", "bogus")
    fd.icon_style.cache_clear()
    assert fd.icon_style() == "emoji"  # an unknown style is the default


def test_icon_style_comes_from_the_find_config(monkeypatch, tmp_path):
    (tmp_path / "find.json").write_text('{"icons": "nerd"}')
    monkeypatch.setenv("OPTMUX_DIR", str(tmp_path))
    assert fd.icon_style() == "nerd" and fd.with_icon("file", "a.py") == "\uf016 a.py"


@skip_no_fzf
def test_omni_blends_language_server_symbols_replacing_the_tag_of_the_same_name_and_file(repo, monkeypatch):
    # ctags says line 2 (the decorator), the server line 3: still one definition
    (repo / "tags").write_text('Hello\tapp.py\t/^def Hello():$/;"\tf\tline:2\n')
    symbols = ["app.py\t3\tHello  function  mod  app.py:3", "sub/notes.md\t1\tHelloNotes  class  sub/notes.md:1",
               "!note\t0\tno language server configuration"]
    asked = []
    monkeypatch.setattr(fd, "lsp_start", lambda args: asked.append(args) or "proc")
    monkeypatch.setattr(fd, "lsp_finish", lambda proc, timeout: symbols)
    rows = [(fd.split_icon(r.split("\t")[2]), r.split("\t")[:2]) for r in fd.list_omni("hello")]
    kinds = [k for (k, _), _ in rows]
    assert kinds.count("tag") == 0 and kinds.count("sym") == 2  # the symbol took the tag's place; the marker row is no symbol
    assert rows[0][0][0] == "sym" and rows[0][1] == ["app.py", "3"]  # best match, and the server's richer row
    assert all(not f.startswith("!") for _, (f, _) in rows)
    assert asked == [["--fast", "hello"]]


@skip_no_fzf
def test_omni_asks_no_servers_without_a_query(repo, monkeypatch):
    monkeypatch.setattr(fd, "lsp_start", lambda *a: pytest.fail("no query, nothing to ask"))
    assert list(fd.list_omni(""))


def test_lsp_source_rows_get_icons_and_hint_rows_their_own(monkeypatch):
    rows = ["a.py\t3\trun  function  a.py:3", "!install:go\t0\tgo: no language server installed.  Enter runs: brew install gopls",
            "!wait\t0\tpython: language server starting, try again in a moment", "!note\t0\tpython: language server exited"]
    monkeypatch.setattr(fd, "lsp_query", lambda args, timeout: rows)
    got = [(r.split("\t")[0], fd.split_icon(r.split("\t")[2])[0]) for r in fd.list_lsp("x")]
    assert got == [("a.py", "sym"), ("!install:go", "install"), ("!wait", "wait"), ("!note", "note")]
    assert list(fd.list_lsp("  ")) == []


def test_opening_a_symbol_remembers_it_like_a_tag(monkeypatch, tmp_path):
    monkeypatch.setenv("OPTMUX_DIR", str(tmp_path))
    fd.record_opened("omni", "a.py\t3\t" + fd.with_icon("sym", "run  function  a.py:3"))
    fd.record_opened("lsp", "b.py\t9\t" + fd.with_icon("sym", "walk  function  b.py:9"))
    assert fd.load_recent()[:4] == ["walk\tb.py", "b.py", "run\ta.py", "a.py"]


def test_enter_on_an_install_row_runs_the_installer_in_a_pane(monkeypatch):
    ran = []
    monkeypatch.setattr(fd, "split_pane", lambda pane, command: ran.append((pane, command)))
    monkeypatch.setenv("OPTMUX_DIR", "/p/.optmux.d")
    fd.install_in_split("%3", "go")
    assert "OPTMUX_DIR=/p/.optmux.d " in ran[0][1] and ran[0][0] == "%3" and "optmux-lsp" in ran[0][1] and "install --yes go" in ran[0][1] and "read _" in ran[0][1]


def test_marker_rows_exist_only_in_the_language_server_source():
    assert fd.marker_kind("lsp", "!install:go") == "install" and fd.marker_kind("lsp", "!wait") == "wait"
    assert fd.marker_kind("lsp", "!note") == "note" and fd.marker_kind("lsp", "src/a.py") is None
    for mode in ("files", "grep", "tags", "omni"):
        assert fd.marker_kind(mode, "!important.md") is None  # a file that happens to be named like a marker
    assert fd.marker_kind("lsp", "!important.md") is None  # not an exact marker either


def test_a_tag_named_like_an_icon_word_is_still_recorded_as_its_tag(monkeypatch, tmp_path):
    monkeypatch.setenv("OPTMUX_DIR", str(tmp_path))
    monkeypatch.setenv("OPTMUX_FIND_ICONS", "text")
    fd.icon_style.cache_clear()
    fd.record_opened("tags", "x.py\t1\tfile  f  x.py:1")  # a tag called `file`: tags rows are not drawn with icons
    assert fd.load_recent()[:2] == ["file\tx.py", "x.py"]


def test_the_install_pane_runs_under_sh_whatever_tmuxs_shell_is(monkeypatch):
    ran = []
    monkeypatch.setattr(fd, "split_pane", lambda pane, command: ran.append(command))
    monkeypatch.setenv("OPTMUX_DIR", "/p/.optmux.d")
    fd.install_in_split("%1", "go")
    assert ran[0].startswith("exec sh -c ") and "install --yes go" in ran[0]
