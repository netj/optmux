import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

sys.dont_write_bytecode = True  # a __pycache__ in data/bin would be installed as if it were a script
loader = SourceFileLoader("optmux_pick_text", str(Path(__file__).parent.parent / "optmux/data/bin/optmux-pick-text"))
pt = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(pt)

CAPTURE = "if x; then\n  \x1b[36mgit commit\x1b[0m -m \x1b[1;38;5;208m\"msg\"\x1b[0m\nfi\n\nfi\n\x1b[32mall green\x1b[0m\n\n"


def test_lines_keep_order_duplicates_and_blanks():
    texts = [t for t, _ in pt.choices(CAPTURE, "lines")]
    assert texts == ["if x; then", '  git commit -m "msg"', "fi", "", "fi", "all green"]


def test_spans_are_styled_runs_but_not_whole_lines():
    assert [t for t, _ in pt.choices(CAPTURE, "spans")] == ["git commit", '"msg"']


def test_repeated_spans_appear_once_at_latest_position():
    cap = "\x1b[31mfoo\x1b[0m bar\n\x1b[34mbaz\x1b[0m x\n\x1b[31mfoo\x1b[0m y\n"
    assert [t for t, _ in pt.choices(cap, "spans")] == ["baz", "foo"]


def test_parse_line_strips_hyperlinks_and_tracks_256_and_rgb_colors():
    plain, runs = pt.parse_line("\x1b]8;;http://x\x1b\\\x1b[38;2;1;2;3mlink\x1b[0m\x1b]8;;\x1b\\ tail")
    assert plain == "link tail"
    assert [(s, e, st.fg) for s, e, st in runs] == [(0, 4, (38, 2, 1, 2, 3))]


def test_compose_dedents_lines_and_joins_spans_with_spaces():
    assert pt.compose(["    a", "      b", ""], "lines") == "a\n  b"
    assert pt.compose(["git commit", '"msg"'], "spans") == 'git commit "msg"'


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
