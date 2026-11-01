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
    assert pt.compose(["foo", "bar"], "words") == "foo bar"


def test_compose_puts_picks_that_contain_whitespace_on_their_own_lines():
    assert pt.compose(["git commit -m x", "make test"], "spans") == "git commit -m x\nmake test"
    assert pt.compose(["make test", "foo"], "spans") == "make test\nfoo"


def test_patterns_find_urls_paths_files_hashes_and_versions_without_overlaps():
    line = "see https://github.com/netj/optmux/pull/38. ~/a/cli.py:12:3 foo.py eb0eb3f v0.13.2 1452 deadbeef"
    assert [(label, text) for _, label, text in pt.find_patterns(line)] == [
        ("url", "https://github.com/netj/optmux/pull/38"),
        ("path", "~/a/cli.py:12:3"),
        ("file", "foo.py"),
        ("hash", "eb0eb3f"),
        ("ver", "v0.13.2"),
    ]


def test_pattern_choices_are_labelled_and_deduplicated_at_latest_position():
    cap = "a.py b.py\nc.py a.py\n"
    assert [t for t, _ in pt.choices(cap, "patterns")] == ["b.py", "c.py", "a.py"]


def test_words_skip_short_ones():
    assert [t for t, _ in pt.choices("an ox, tiger-lily (rose)\n", "words")] == ["tiger-lily", "rose"]


def test_cycle_wraps_around():
    assert pt.cycle(pt.FILTERS, pt.FILTERS[-1]) == pt.FILTERS[0]


def test_labels_shrink_in_narrow_terminals(monkeypatch):
    import os
    monkeypatch.setattr(pt.shutil, "get_terminal_size", lambda: os.terminal_size((120, 30)))
    wide = pt.labels("words", "osc52")
    assert wide[1] == "--prompt=words filtered (C-M-x to switch) > "
    assert "C-f in files" in wide[0] and "C-g by grep" in wide[0] and "C-M-f everywhere" in wide[0]
    monkeypatch.setattr(pt.shutil, "get_terminal_size", lambda: os.terminal_size((60, 30)))
    narrow = pt.labels("words", "osc52")
    assert narrow[1] == "--prompt=words (C-M-x) > "
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
    assert pt.find_query(["optmux/pick.py:119", "def  pickable"], "typed") == "optmux/pick.py:119 def pickable"
    assert pt.find_query(["  multi\n  line  "], "") == "multi line"
    assert pt.find_query([], " typed ") == "typed" and pt.find_query([], "  ") == ""
    assert len(pt.find_query(["x" * 1000], "")) == pt.MAX_QUERY


def test_lookup_keys_start_find_in_the_right_source_and_leave_cycling_to_the_opener_key():
    assert pt.FIND_KEYS == {"ctrl-f": "files", "ctrl-g": "grep", "ctrl-alt-f": "omni"}
    assert "ctrl-alt-x" not in pt.FIND_KEYS and "ctrl-t" not in pt.FIND_KEYS and "ctrl-y" not in pt.FIND_KEYS


def test_open_find_continues_as_find_in_the_panes_directory(monkeypatch, tmp_path):
    import os
    ran = []
    monkeypatch.setattr(pt, "tmux", lambda *a, **k: type("R", (), {"stdout": f"{tmp_path}\n"})())
    monkeypatch.setattr(pt.os, "execv", lambda exe, argv: ran.append((exe, argv)))
    monkeypatch.chdir(tmp_path.parent)
    pt.open_find("%7", "grep", "needle text")
    exe, argv = ran[0]
    assert os.path.samefile(os.getcwd(), tmp_path)  # the pane's project, not wherever the popup started
    assert argv[1].endswith("optmux-find") and argv[2:] == ["%7", "--mode", "grep", "--query", "needle text"]
