import importlib.util
import shutil
import subprocess
import sys
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

sys.dont_write_bytecode = True  # a __pycache__ in data/bin would be installed as if it were a script
loader = SourceFileLoader("optmux_extract", str(Path(__file__).parent.parent / "optmux/data/bin/optmux-extract"))
pt = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(pt)

CAPTURE = "if x; then\n  \x1b[36mgit commit\x1b[0m -m \x1b[1;38;5;208m\"msg\"\x1b[0m\nfi\n\nfi\n\x1b[32mall green\x1b[0m\n\n"


def test_lines_keep_order_duplicates_and_blanks():
    texts = [t for t, _ in pt.choices(CAPTURE, "lines")]
    assert texts == ["if x; then", '  git commit -m "msg"', "fi", "", "fi", "all green"]


def test_spans_are_styled_runs_including_bold_headings_but_not_highlighted_lines():
    assert [t for t, _ in pt.choices(CAPTURE, "spans")] == ["git commit", '"msg"', "all green"]
    cap = "\x1b[1mWhat changed:\x1b[0m\n\x1b[48;5;237mhighlighted whole line\x1b[0m\n"
    assert [t for t, _ in pt.choices(cap, "spans")] == ["What changed:"]


def test_repeated_spans_appear_once_at_latest_position():
    cap = "\x1b[31mfoo\x1b[0m bar\n\x1b[34mbaz\x1b[0m x\n\x1b[31mfoo\x1b[0m y\n"
    assert [t for t, _ in pt.choices(cap, "spans")] == ["baz", "foo"]


def test_parse_line_strips_hyperlinks_and_tracks_256_and_rgb_colors():
    plain, runs = pt.parse_line("\x1b]8;;http://x\x1b\\\x1b[38;2;1;2;3mlink\x1b[0m\x1b]8;;\x1b\\ tail")
    assert plain == "link tail"
    assert [(s, e, st.fg) for s, e, st in runs] == [(0, 4, (38, 2, 1, 2, 3))]


def test_compose_dedents_lines_and_joins_spans_with_spaces():
    assert pt.compose(["    a", "      b", ""], "lines") == "a\n  b"
    assert pt.compose(["foo", "bar"], "spans") == "foo bar"
    assert pt.compose(["foo", "bar"], "spans") == "foo bar"


def test_compose_puts_picks_that_contain_whitespace_on_their_own_lines():
    assert pt.compose(["git commit -m x", "make test"], "spans") == "git commit -m x\nmake test"
    assert pt.compose(["make test", "foo"], "spans") == "make test\nfoo"


def test_patterns_find_urls_paths_files_hashes_and_versions_without_overlaps():
    line = "see https://github.com/netj/optmux/pull/38. ~/a/cli.py:12:3 foo.py eb0eb3f v0.13.2 1452 deadbeef (#234) a#5 &#38;"
    assert [(label, text) for _, label, text in pt.find_patterns(line)] == [
        ("url", "https://github.com/netj/optmux/pull/38"),
        ("path", "~/a/cli.py:12:3"),
        ("file", "foo.py"),
        ("hash", "eb0eb3f"),
        ("ver", "v0.13.2"),
        ("pr", "#234"),
    ]


def test_pattern_choices_are_labelled_and_deduplicated_at_latest_position():
    cap = "a.py b.py\nc.py a.py\n"
    assert [t for t, _ in pt.choices(cap, "spans")] == ["b.py", "c.py", "a.py"]


def test_cycle_wraps_around():
    assert pt.cycle(pt.FILTERS, pt.FILTERS[-1]) == pt.FILTERS[0]


def test_labels_shrink_in_narrow_terminals(monkeypatch):
    import os
    monkeypatch.setattr(pt.shutil, "get_terminal_size", lambda: os.terminal_size((120, 30)))
    wide = pt.labels("spans", "osc52")
    assert wide[1] == "--prompt=spans filtered (C-M-x to switch) > "
    assert "C-f files" in wide[0] and "C-g grep" in wide[0] and "C-M-f all" in wide[0] and "M-p/M-n" in wide[0]
    monkeypatch.setattr(pt.shutil, "get_terminal_size", lambda: os.terminal_size((60, 30)))
    narrow = pt.labels("spans", "osc52")
    assert narrow[1] == "--prompt=spans (C-M-x) > "
    assert all(len(line) < 80 for line in narrow[0].split("\n")) and "C-f: files" in narrow[0]


def test_control_characters_never_survive_into_the_text_to_type():
    # an unterminated-looking paste end would let the rest of the text run as typed input
    plain, _ = pt.parse_line("echo hi\x1b[201~; rm -rf ~\x07\r")
    assert "\x1b" not in plain and "\r" not in plain and "\x07" not in plain


def test_tabs_become_spaces_so_fzf_fields_stay_intact():
    [(text, _)] = pt.choices("a\tb\n", "lines")
    assert "\t" not in text


def test_colon_sub_parameters_do_not_leak_bogus_attributes():
    _, [(_, _, style)] = pt.parse_line("\x1b[38:2::1:2:4mrgb\x1b[0m")
    assert style.fg == (38, 2, 1, 2, 4) and not style.attrs
    _, [(_, _, style)] = pt.parse_line("\x1b[4:3mcurly\x1b[0m")
    assert style.attrs == {4}


def test_parse_fzf_output_returns_picks_in_screen_order_with_blank_lines():
    out = "query\nenter\n7\tlast\td7\n2\t\td2\n4\tmiddle\td4\n"
    assert pt.parse_fzf_output(out) == ("query", "enter", ["", "middle", "last"])
    assert pt.parse_fzf_output("q\n\n") == ("q", "", [])
    assert pt.parse_fzf_output("") == ("", "esc", [])


def test_ip_addresses_and_dotted_libraries_are_not_truncated():
    texts = [t for _, _, t in pt.find_patterns("ip 192.168.1.100 and lib.so.6 and v1.2.3.")]
    assert "192.168.1" not in texts and "lib.so" not in texts
    assert "lib.so.6" in texts and "v1.2.3" in texts


def test_url_keeps_a_balanced_closing_paren_but_not_sentence_punctuation():
    assert [t for _, _, t in pt.find_patterns("see http://x.com/Foo_(bar).")] == ["http://x.com/Foo_(bar)"]
    assert [t for _, _, t in pt.find_patterns("(see http://x.com/a)")] == ["http://x.com/a"]


def test_colon_rgb_with_a_4_keeps_following_attributes():
    _, [(_, _, style)] = pt.parse_line("\x1b[38:2::1:4:5;1mx\x1b[0m")
    assert style.fg == (38, 2, 1, 4, 5) and style.attrs == {1}


needs_tmux = pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux not installed")


@needs_tmux
def test_load_buffer_keeps_trailing_semicolons_and_large_text():
    sock = tempfile.mkdtemp(prefix="optmux-x-") + "/s"  # short: unix socket paths are limited to ~104 characters
    tmux = ["tmux", "-S", sock, "-f", "/dev/null"]
    subprocess.run([*tmux, "new-session", "-d", "-s", "t", "cat"], check=True)
    try:
        real = pt.tmux
        pt.tmux = lambda *a, **kw: subprocess.run([*tmux, *a], check=True, **kw)
        for text in ["echo hi;", ";", "a;b;", "x" * 50000]:
            pt.load_buffer(text)
            shown = subprocess.run([*tmux, "show-buffer", "-b", pt.BUFFER], capture_output=True, text=True).stdout
            assert shown == text
    finally:
        pt.tmux = real
        subprocess.run([*tmux, "kill-server"], capture_output=True)


def test_spans_wrapped_by_the_program_are_joined_when_they_fill_the_line():
    cap = "so \x1b[34mgit\x1b[0m\n  \x1b[34mcommit -m x\x1b[0m and \x1b[34mmake test\x1b[0m\n"
    # "so git" is 6 wide; "commit" would not fit in 8 columns, so it was wrapped
    assert [t for t, _ in pt.choices(cap, "spans", 8)] == ["git commit -m x", "make test"]
    # plenty of room left: two separate highlights, not a wrap
    assert [t for t, _ in pt.choices(cap, "spans", 80)] == ["git", "commit -m x", "make test"]
    # a different style never joins
    cap2 = "so \x1b[34mgit\x1b[0m\n  \x1b[31mcommit\x1b[0m\n"
    assert [t for t, _ in pt.choices(cap2, "spans", 8)] == ["git", "commit"]


def test_find_query_joins_the_picks_on_one_line_or_falls_back_to_what_was_typed():
    assert pt.find_query(["optmux/pick.py", "def  pickable"], "typed") == "optmux/pick.py def pickable"
    assert pt.find_query(["  multi\n  line  "], "") == "multi line"
    assert pt.find_query([], " typed ") == "typed" and pt.find_query([], "  ") == ""
    assert len(pt.find_query(["x" * 1000], "")) == pt.MAX_QUERY


def test_find_query_drops_the_line_and_column_after_a_path_but_not_other_colons():
    q = pt.find_query
    assert q(["optmux/pick.py:119"], "") == "optmux/pick.py" and q(["tests/a.py:12:5"], "") == "tests/a.py"
    assert q(["pick.py:119", "error"], "") == "pick.py error"
    assert q(["10:30"], "") == "10:30" and q(["key:value"], "") == "key:value"  # not paths
    assert q(["http://example.com:8080/x"], "") == "http://example.com:8080/x"
    assert q(["see foo/bar.py:3"], "") == "see foo/bar.py:3"  # only a pick that is just path:line


def test_find_query_defuses_control_bytes_and_fzf_search_syntax():
    assert pt.find_query(["a\x1b[31mred\rb"], "") == "a [31mred b"
    assert pt.find_query([], "'exact ^prefix !neg suffix$ plain") == "exact prefix neg suffix plain"
    assert pt.find_query(["'quoted' ^caret"], "") == "'quoted' ^caret"  # the picks are text, not a filter


def test_lookup_keys_start_find_in_the_right_source_and_leave_cycling_to_the_opener_key():
    assert pt.FIND_KEYS == {"ctrl-f": "files", "ctrl-g": "grep", "ctrl-alt-f": "omni"}
    assert "ctrl-alt-x" not in pt.FIND_KEYS and "ctrl-t" not in pt.FIND_KEYS and "ctrl-y" not in pt.FIND_KEYS


def test_open_find_closes_this_popup_and_opens_find_in_one_titled_for_it(monkeypatch, tmp_path):
    import shlex
    calls = []
    def fake_tmux(*args, **kw):
        calls.append(args)
        return type("R", (), {"stdout": f"{tmp_path}\n"})()
    monkeypatch.setattr(pt, "tmux", fake_tmux)
    assert pt.open_find("%7", "grep", "needle #{session_name} #(touch /tmp/x) text") == 0
    run_shell = [c for c in calls if c[0] == "run-shell"][0]
    assert run_shell[1] == "-b"  # in the background: this popup must be gone first
    assert "#{" not in run_shell[2].replace("##{", "") and "#(" not in run_shell[2].replace("##(", "")  # what tmux would expand is doubled
    command = run_shell[2].replace("##", "#")  # (tmux halves them again)
    first, _, failed = command.split("; ", 1)[1].partition(" || ")
    words = shlex.split(first)
    assert words[:3] == ["tmux", "display-popup", "-E"] and words[words.index("-T") + 1] == " OPTMUX Find "
    assert words[words.index("-d") + 1] == str(tmp_path) and words[words.index("-t") + 1] == "%7"
    find = shlex.split(words[-1])
    assert find[0].endswith("optmux-find") and find[1:3] == ["%7", "--mode=grep"]
    # the text is in a file, not in anything tmux or a shell reads
    query_file = find[3].removeprefix("--query-file=")
    assert Path(query_file).read_text() == "needle #{session_name} #(touch /tmp/x) text" and "needle" not in command
    assert "tmux display-message" in failed and "buffer" in failed  # if the popup cannot open, say where the text is
    assert any(c[0] == "load-buffer" for c in calls)  # and the text is there
    Path(query_file).unlink()


def test_open_find_leaves_out_a_start_directory_that_is_gone(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(pt, "tmux", lambda *a, **k: calls.append(a) or type("R", (), {"stdout": f"{tmp_path}/deleted\n"})())
    pt.open_find("%7", "files", "x")
    popup = [c for c in calls if c[0] == "run-shell"][0][2].partition(" || ")[0]
    assert " -d " not in popup


def test_open_find_that_cannot_start_keeps_the_text_in_the_tmux_buffer(monkeypatch):
    calls = []
    def fake_tmux(*args, **kw):
        calls.append(args)
        if args[0] == "display-message" and "-p" in args:
            raise pt.subprocess.CalledProcessError(1, "tmux")  # the pane is gone
        return type("R", (), {"stdout": ""})()
    monkeypatch.setattr(pt, "tmux", fake_tmux)
    loaded = []
    monkeypatch.setattr(pt, "load_buffer", lambda text, clipboard=False: loaded.append(text))
    assert pt.open_find("%9", "grep", "needle") == 1
    assert loaded == ["needle"] and any(c[0] == "display-message" and "buffer" in c[-1] for c in calls)


def test_the_lookup_keys_are_the_ones_find_itself_uses_for_those_sources():
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("optmux_find_for_extract", str(Path(__file__).parent.parent / "optmux/data/bin/optmux-find"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    find = importlib.util.module_from_spec(spec)
    loader.exec_module(find)
    for key, source in pt.FIND_KEYS.items():
        assert find.MODE_KEYS.get(source, find.CYCLE_KEY if source == "omni" else None) in (key, find.CYCLE_KEY) or key == "ctrl-alt-f"
    assert pt.FIND_KEYS["ctrl-f"] == "files" and find.MODE_KEYS["files"] == "ctrl-f"
    assert pt.FIND_KEYS["ctrl-g"] == "grep" and find.MODE_KEYS["grep"] == "ctrl-g"
    assert pt.FIND_KEYS["ctrl-alt-f"] == "omni" and find.CYCLE_KEY == "ctrl-alt-f"
    assert not set(pt.FIND_KEYS) & {"ctrl-t", "ctrl-y", "ctrl-alt-x"}  # extract's own keys


def test_patterns_are_drawn_with_the_icons_of_the_icons_setting(monkeypatch):
    cap = "see https://x.org/a and ./b/c.py and abc1234 and #42 and v1.2.3\n"
    for style, glyphs in (("emoji", ["🔗", "📁", "#️⃣", "🔀", "🏷️"]), ("nerd", ["\uf0c1", "\uf07b", "\ue729", "\ue726", "\uf02b"]), ("text", ["url", "path", "hash", "pr", "ver"])):
        monkeypatch.setenv("OPTMUX_ICONS", style)
        shown = "\n".join(d for _, d in pt.choices(cap, "spans"))
        assert all(g in shown for g in glyphs), style
    monkeypatch.delenv("OPTMUX_ICONS")
    monkeypatch.setenv("OPTMUX_DIR", "/nonexistent")
    assert pt.icon_style() == "nerd"


def test_the_queries_and_items_of_a_filter_are_remembered_newest_first(monkeypatch):
    options = {}
    monkeypatch.setattr(pt, "tmux", lambda *a, **k: options.__setitem__(a[2], a[3]))
    monkeypatch.setattr(pt, "show_option", lambda name: options.get(name, ""))
    assert pt.load_history("spans") == []  # nothing yet
    pt.save_state("spans", "bash", "bashrc")
    pt.save_state("spans", ".tmp/", ".tmp/x")
    pt.save_state("spans", "bash", '  an "item"\twith odd bits')  # again: moves to the front, once
    assert pt.load_history("spans") == [("bash", '  an "item"\twith odd bits'), (".tmp/", ".tmp/x")]  # (leading space and all)
    assert pt.load_history("lines") == []  # each filter has its own
    for n in range(pt.MAX_HISTORY + 5):
        pt.save_state("spans", f"q{n}", None)
    assert len(pt.load_history("spans")) == pt.MAX_HISTORY and pt.load_history("spans")[0] == (f"q{pt.MAX_HISTORY + 4}", None)
    options[pt.STATE_OPTION + "spans"] = "garbage"
    assert pt.load_history("spans") == []
    options[pt.STATE_OPTION + "spans"] = '[1, {"query": 5}, {"query": "ok"}]'
    assert pt.load_history("spans") == [("ok", None)]


@pytest.mark.skipif(shutil.which("fzf") is None, reason="fzf not installed")
def test_the_cursor_goes_back_to_the_remembered_item():
    numbered = list(reversed(list(enumerate([("alpha", "alpha"), ("beta", "beta"), ("alphabet", "alphabet")]))))
    assert pt.cursor_position(numbered, "", "spans", "beta") == ("", 2)  # best first: the newest is 1
    assert pt.cursor_position(numbered, "alp", "spans", "alpha") == ("alp", 2)
    assert pt.cursor_position(numbered, "alp", "spans", "beta") == ("alp", None)  # not in the list it filters to
    assert pt.cursor_position(numbered, "zzz", "spans", "beta", recalled=True) == ("", 2)  # a recalled query that matches nothing now is dropped
    assert pt.cursor_position(numbered, "zzz", "spans", None) == ("zzz", None)  # one you are typing is not
    assert pt.cursor_position(numbered, "", "spans", None) == ("", None)


def test_every_filter_marks_its_items_the_same_way(monkeypatch):
    for style, marks in (("emoji", {"lines": "📃", "spans": "🎨"}), ("text", {"lines": "line", "spans": "span"})):
        monkeypatch.setenv("OPTMUX_ICONS", style)
        for mode, mark in marks.items():
            shown = [d for _, d in pt.choices(CAPTURE, mode)]
            assert shown and any(mark in d for d in shown), (style, mode)
    assert [t for t, _ in pt.choices(CAPTURE, "lines")][1] == '  git commit -m "msg"'  # (what is typed has no mark)


def test_the_header_mentions_clearing_the_query(monkeypatch):
    for columns in (60, 120):
        monkeypatch.setattr(pt.shutil, "get_terminal_size", lambda columns=columns: type("S", (), {"columns": columns})())
        assert "C-u" in pt.labels("spans", "osc52")[0] and "M-p" in pt.labels("spans", "osc52")[0]


def test_no_icons_leaves_the_items_bare(monkeypatch):
    monkeypatch.setenv("OPTMUX_ICONS", "none")
    for mode in ("lines", "spans"):
        assert all(not d.startswith(("\x1b[2m", " ")) for _, d in pt.choices("see ./a/b.py and v1.2.3\n", mode)), mode
    monkeypatch.delenv("OPTMUX_ICONS")
    monkeypatch.setenv("OPTMUX_DIR", "/nonexistent")
    assert pt.icon_style() == "nerd"


def test_a_long_item_gets_its_cursor_back_too():
    long = "x" * 500
    numbered = [(0, (long, long)), (1, ("short", "short"))]
    assert pt.cursor_position(numbered, "", "spans", long[:pt.MAX_ITEM]) == ("", 1)


def test_save_state_dedupes_and_keeps_empty_history_alone(monkeypatch):
    options = {}
    monkeypatch.setattr(pt, "tmux", lambda *a, **k: options.__setitem__(a[2], a[3]))
    monkeypatch.setattr(pt, "show_option", lambda name: options.get(name, ""))
    pt.save_state("lines", "ssh", "ssh host")
    assert [q for q, _ in pt.load_history("lines")] == ["ssh"]


def test_an_emptied_query_is_saved_first_and_keeps_its_item(monkeypatch):
    options = {}
    monkeypatch.setattr(pt, "tmux", lambda *a, **k: options.__setitem__(a[2], a[3]))
    monkeypatch.setattr(pt, "show_option", lambda name: options.get(name, ""))
    pt.save_state("lines", "", "first item")
    pt.save_state("lines", "ssh", "ssh host")
    pt.save_state("lines", "", None)  # C-u, then Esc
    assert pt.load_history("lines") == [("", "first item"), ("ssh", "ssh host")]


def test_osc52_copy_goes_to_our_own_terminal_not_whichever_client_tmux_likes(monkeypatch):
    import base64

    loaded, written = [], []

    class Terminal:
        def isatty(self): return True
        def write(self, x): written.append(x)
        def flush(self): pass

    monkeypatch.setattr(pt, "load_buffer", lambda text, clipboard=False: loaded.append((text, clipboard)))
    monkeypatch.setattr(pt, "show_server_option", lambda name: "on")
    monkeypatch.setattr(pt.sys, "stdout", Terminal())
    pt.copy("héllo\nworld", "osc52")
    assert loaded == [("héllo\nworld", False)]  # (the tmux buffer too, but tmux is not asked to pick a client)
    assert written == ["\x1b]52;c;" + base64.b64encode("héllo\nworld".encode()).decode() + "\x07"]
    # set-clipboard external or off: tmux relays nothing from us, so it is asked to (as before)
    monkeypatch.setattr(pt, "show_server_option", lambda name: "external")
    written.clear()
    pt.copy("x", "osc52")
    assert loaded[-1] == ("x", True) and not written

    class NotATerminal(Terminal):
        def isatty(self): return False

    monkeypatch.setattr(pt, "show_server_option", lambda name: "on")
    monkeypatch.setattr(pt.sys, "stdout", NotATerminal())
    pt.copy("y", "osc52")
    assert loaded[-1] == ("y", True)


def test_patterns_find_quoted_text_in_all_quote_styles_but_not_apostrophes():
    line = """use `--force' or '--dry-run', "git commit -m x" and `foo` but don't, can't 'a.py'"""
    assert [(label, text) for _, label, text in pt.find_patterns(line)] == [
        ("quote", "--force"), ("quote", "--dry-run"), ("quote", "git commit -m x"), ("quote", "foo"), ("file", "a.py"),
    ]


def test_spans_mix_styled_runs_with_the_patterns_around_them_in_screen_order():
    cap = "see ./a/b.py then \x1b[32mgit commit\x1b[0m for #234 and \x1b[31m./c.py\x1b[0m\n"
    assert [t for t, _ in pt.choices(cap, "spans")] == ["./a/b.py", "git commit", "#234", "./c.py"]


def test_plain_grey_spans_are_left_out_but_emphasized_ones_stay():
    cap = ("\x1b[38;2;136;136;136mrgb grey\x1b[0m \x1b[90mbright black\x1b[0m \x1b[38;5;246mramp grey\x1b[0m "
           "\x1b[1;90mbold grey\x1b[0m \x1b[38;2;200;50;50mred\x1b[0m\n")
    assert [t for t, _ in pt.choices(cap, "spans")] == ["bold grey", "red"]


def stoplist_env(monkeypatch, tmp_path, **groups):
    """OPTMUX_DIR with a find.json holding the default `+ignore_spans` (plus `groups` of our own)."""
    import json

    import yaml

    defaults = yaml.safe_load((Path(__file__).parent.parent / "optmux/data/optmux-defaults.yaml").read_text())
    ignore = {**defaults["+optmux"]["+find"]["+ignore_spans"], **groups}
    (tmp_path / "find.json").write_text(json.dumps({"ignore_spans": ignore}))
    monkeypatch.setenv("OPTMUX_DIR", str(tmp_path))


def test_the_stoplist_hides_known_chrome_spans_and_takes_more_groups(monkeypatch, tmp_path):
    cap = "\x1b[33m\u23e9 auto mode on\x1b[0m \x1b[31mkeep me\x1b[0m /effort /mine \x1b[1mrecap:\x1b[0m\n"
    stoplist_env(monkeypatch, tmp_path, mine=["/mine", "[bad"])
    assert [t for t, _ in pt.choices(cap, "spans")] == ["keep me"]


def test_a_path_inside_a_styled_command_is_listed_as_its_own_option():
    cap = "\x1b[1m! pbcopy < /tmp/x/PR_DESCRIPTION.md\x1b[0m\n"
    assert [t for t, _ in pt.choices(cap, "spans")] == ["/tmp/x/PR_DESCRIPTION.md", "! pbcopy < /tmp/x/PR_DESCRIPTION.md"]  # the span last: first in fzf


def test_quotes_spanning_lines_are_listed_whole():
    cap = 'it reads: "Written with Claude Code: the design and\n  the work for a week."\n\nstray " mark\nsingle "one line" here\n'
    texts = [t for t, _ in pt.choices(cap, "spans")]
    assert "Written with Claude Code: the design and the work for a week." in texts
    assert "one line" in texts and len(texts) == 2


def test_the_query_it_opens_on_is_kept_even_if_it_matches_nothing():
    numbered = [(0, ("alpha", "alpha"))]
    assert pt.cursor_position(numbered, "zzz", "lines", None, recalled=False)[0] == "zzz"
    assert pt.cursor_position(numbered, "zzz", "lines", None, recalled=True)[0] == ""


def test_white_is_text_not_grey_and_the_mode_line_hint_is_covered():
    cap = "\x1b[97mwhite text\x1b[0m \x1b[38;2;255;255;255mrgb white\x1b[0m \x1b[37mansi white\x1b[0m\n"
    assert [t for t, _ in pt.choices(cap, "spans")] == ["white text", "rgb white", "ansi white"]
    import re
    import yaml
    defaults = yaml.safe_load((Path(__file__).parent.parent / "optmux/data/optmux-defaults.yaml").read_text())
    patterns = defaults["+optmux"]["+find"]["+ignore_spans"]["claude_code"]
    assert any(re.fullmatch(p, "⏵⏵ accept edits on (shift+tab to cycle)", re.I) for p in patterns)


def test_classify_whole_picks():
    assert [pt.classify(p) for p in ["https://x.org/a", "src/a.py:3:1", "foo.py", "eb0eb3f", "#234", "git commit", "v1.2.3", "  ./a/b  "]] == [
        "url", "path", "file", "hash", "pr", "other", "other", "path"]


def test_split_position():
    assert pt.split_position("a/b.py:12:3") == ("a/b.py", 12, 3)
    assert pt.split_position("a/b.py:12") == ("a/b.py", 12, None)
    assert pt.split_position("a/b.py") == ("a/b.py", None, None)


def test_editor_argv_picks_the_jump_syntax_per_editor():
    t = [("/a/x.py", 12, 3), ("/a/y.py", None, None)]
    assert pt.editor_argv("hx", t) == ["hx", "/a/x.py:12:3", "/a/y.py"]
    assert pt.editor_argv("code -w", t) == ["code", "-w", "-g", "/a/x.py:12:3", "/a/y.py"]
    assert pt.editor_argv("nano", t) == ["nano", "+12,3", "/a/x.py", "/a/y.py"]
    assert pt.editor_argv("emacs", t) == ["emacs", "+12:3", "/a/x.py", "/a/y.py"]
    assert pt.editor_argv(None, [("/t", None, None)]) == ["vi", "/t"]
    assert pt.editor_argv("  ", [("/t", None, None)]) == ["vi", "/t"]


def test_vim_jumps_once_for_one_file_and_in_every_window_for_several():
    assert pt.editor_argv("nvim", [("/a", 12, None)]) == ["nvim", "+12", "/a"]
    assert pt.editor_argv("nvim", [("/a", 12, 3)]) == ["nvim", "+call cursor(12,3)", "/a"]
    assert pt.editor_argv("vim", [("/a", None, None), ("/b", 20, None), ("/c", 5, 2)]) == [
        "vim", "-o", "/a", "/b", "/c", "-c", "2wincmd w | call cursor(20,1)", "-c", "3wincmd w | call cursor(5,2)", "-c", "1wincmd w"]
    assert pt.editor_argv("vim", [("/a", None, None), ("/b", None, None)]) == ["vim", "-o", "/a", "/b"]


def test_edit_plan_files_that_exist_else_the_text(tmp_path):
    (tmp_path / "a.py").write_text("x")
    assert pt.edit_plan(["a.py:4", "https://x.org", "nope.py"], "spans", str(tmp_path)) == ([(str(tmp_path / "a.py"), 4, None)], None, None)
    assert pt.edit_plan(["nope.py"], "spans", str(tmp_path))[2] == "no such file: nope.py"
    assert "C-o" in pt.edit_plan(["https://x.org"], "spans", str(tmp_path))[2]
    assert pt.edit_plan(["a.py", "git commit"], "spans", str(tmp_path)) == ([], "a.py\ngit commit", None)
    assert pt.edit_plan(["  #234"], "lines", str(tmp_path)) == ([], "#234", None)


def test_edit_opens_a_split_in_the_pane_directory_and_removes_its_temp_file(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(pt, "tmux", lambda *a, **k: calls.append(a) or type("R", (), {"stdout": f"{tmp_path}\n"})())
    monkeypatch.setenv("EDITOR", "vim")
    monkeypatch.setattr(pt, "split_flags", lambda pane: ["-v", "-b"])
    (tmp_path / "a.py").write_text("x")
    assert pt.edit("%1", ["a.py:7"], "spans") == 0
    assert calls[-1][:8] == ("split-window", "-Z", "-v", "-b", "-t", "%1", "-c", str(tmp_path))
    assert calls[-1][8] == f"vim +7 {tmp_path}/a.py"
    assert pt.edit("%1", ["echo $(rm -rf x)"], "spans") == 0
    import shlex
    words = shlex.split(calls[-1][8].split("; rm -f ")[0])
    assert words[0] == "vim" and Path(words[1]).read_text() == "echo $(rm -rf x)\n" and calls[-1][8].endswith(shlex.quote(words[1]))
    Path(words[1]).unlink()


def test_open_command_by_kind(monkeypatch, tmp_path):
    (tmp_path / "d").mkdir()
    (tmp_path / "f.txt").write_text("x")
    cwd = str(tmp_path)
    assert pt.open_command("https://x.org/a", cwd, "darwin") == (["open", "https://x.org/a"], None)
    assert pt.open_command("https://x.org/a", cwd, "linux") == (["xdg-open", "https://x.org/a"], None)
    assert pt.open_command("f.txt:3", cwd, "darwin")[0] == ["open", "-R", str(tmp_path / "f.txt")]
    assert pt.open_command("./d", cwd, "darwin")[0] == ["open", str(tmp_path / "d")]
    assert pt.open_command("f.txt", cwd, "linux")[0] == ["xdg-open", str(tmp_path / "f.txt")]
    assert pt.open_command("gone.txt", cwd, "darwin") == (None, "no such path: gone.txt")
    assert pt.open_command("git commit", cwd, "darwin")[0] is None
    monkeypatch.setattr(pt.shutil, "which", lambda name: None)
    assert pt.open_command("#12", cwd, "darwin")[0] is None
    monkeypatch.setattr(pt.shutil, "which", lambda name: "/bin/gh")
    assert "not in a git repository" in pt.open_command("#12", cwd, "darwin")[1]
    subprocess.run(["git", "init", "-q", cwd], check=True)
    assert pt.open_command("#12", cwd, "darwin") == (["gh", "browse", "12"], None)
    assert pt.open_command("eb0eb3f", cwd, "darwin") == (["gh", "browse", "eb0eb3f"], None)


def test_open_items_opens_each_by_its_kind_and_says_why_not(monkeypatch, tmp_path):
    opened, shown = [], []
    monkeypatch.setattr(pt, "pane_directory", lambda pane: str(tmp_path))
    monkeypatch.setattr(pt, "run_open", lambda argv, cwd: opened.append(argv))
    monkeypatch.setattr(pt, "tmux", lambda *a, **k: shown.append(a))
    pt.open_items("%1", ["https://x.org", "make test", "nope.py"])
    assert len(opened) == 1 and opened[0][-1] == "https://x.org"
    assert "can't open: make test" in shown[0][-1] and "no such path: nope.py" in shown[0][-1]


def test_restyle_paths_relative_to_the_project_or_absolute(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x")
    cwd = str(tmp_path / "src")
    picks = ["a.py:3", "gone.py", "echo hi"]
    assert pt.restyle(picks, "shown", cwd) == picks
    assert pt.restyle(picks, "relative", cwd) == ["src/a.py:3", "gone.py", "echo hi"]
    assert pt.restyle(picks, "absolute", cwd)[0] == f"{tmp_path / 'src' / 'a.py'}:3"
    link = tmp_path.parent / (tmp_path.name + "-link")
    link.symlink_to(tmp_path)
    assert pt.restyle(["a.py:3"], "relative", str(link / "src")) == ["src/a.py:3"]  # (cwd reached through a symlink)
    assert pt.editor_argv('vim "', [("/t", None, None)]) == ["vi", "/t"]


def test_labels_mention_edit_open_and_path_style(monkeypatch):
    import os
    for columns in (120, 60):
        monkeypatch.setattr(pt.shutil, "get_terminal_size", lambda columns=columns: os.terminal_size((columns, 30)))
        header = pt.labels("spans", "osc52", "relative")[0]
        assert "C-e" in header and "C-o" in header and "paths relative" in header


def test_the_editor_opens_above_or_across_the_edge_when_the_pane_is_short(monkeypatch):
    for code, flags in ((0, ["-v", "-b"]), (1, ["-f", "-v", "-b"])):
        monkeypatch.setattr(pt.subprocess, "run", lambda *a, code=code, **k: type("R", (), {"returncode": code})())
        assert pt.split_flags("%1") == flags


def test_the_editor_is_zoomed_and_gives_the_zoom_back_when_the_window_was_zoomed(monkeypatch, tmp_path):
    calls = []
    def fake_tmux(*a, **k):
        calls.append(a)
        return type("R", (), {"stdout": "1\n" if "#{window_zoomed_flag}" in a else f"{tmp_path}\n"})()
    monkeypatch.setattr(pt, "tmux", fake_tmux)
    monkeypatch.setattr(pt, "split_flags", lambda pane: ["-v", "-b"])
    monkeypatch.setenv("EDITOR", "vim")
    (tmp_path / "a.py").write_text("x")
    pt.edit("%1", ["a.py"], "spans")
    split = calls[-1]
    assert split[1] == "-Z" and split[-1].endswith("; tmux select-pane -Z -t %1")




def test_the_stoplist_covers_jump_to_bottom_and_new_messages():
    import re
    import yaml
    defaults = yaml.safe_load((Path(__file__).parent.parent / "optmux/data/optmux-defaults.yaml").read_text())
    patterns = defaults["+optmux"]["+find"]["+ignore_spans"]["claude_code"]
    for chrome in ("Jump to bottom (click) ↓", "3 new messages (click) ↓", "1 new message (click)"):
        assert any(re.fullmatch(p, chrome, re.I) for p in patterns), chrome
