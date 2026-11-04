import re
from pathlib import Path

import yaml

from optmux.cli import load_bundled_defaults, load_optmux_conf, normalize_optmux_section, read_optmux_section


def test_load_bundled_defaults():
    """Bundled defaults load and have expected keys."""
    result = load_bundled_defaults()
    assert isinstance(result, dict)
    assert "shortcuts" in result
    assert "C-M-s" in result["shortcuts"]


def test_load_optmux_conf_exists(personal_yaml_file):
    """Loads personal config from specified path."""
    result = load_optmux_conf(conf_path=personal_yaml_file)
    assert result == {"shortcuts": {"C-M-x": "htop"}}


def test_load_optmux_conf_missing(tmp_path):
    """Non-existent path returns empty dict."""
    result = load_optmux_conf(conf_path=tmp_path / "nonexistent.yaml")
    assert result == {}


def test_load_optmux_conf_empty_file(tmp_path):
    """Empty YAML returns empty dict."""
    p = tmp_path / ".optmux.yaml"
    p.write_text("")
    result = load_optmux_conf(conf_path=p)
    assert result == {}


def test_load_optmux_conf_no_optmux_key(tmp_path):
    """YAML without optmux key returns empty dict."""
    p = tmp_path / ".optmux.yaml"
    p.write_text("something_else:\n  key: value\n")
    result = load_optmux_conf(conf_path=p)
    assert result == {}


def test_load_optmux_conf_warns_on_unknown_top_level_key(tmp_path, capsys):
    """Unrecognized top-level optmux: key prints a warning."""
    p = tmp_path / ".optmux.yaml"
    p.write_text("optmux:\n  shortcuuts:\n    C-M-x: htop\n")
    load_optmux_conf(conf_path=p)
    err = capsys.readouterr().err
    assert "shortcuuts" in err


def test_normalize_optmux_section_warns_on_unknown_shortcut_key(capsys):
    """Unrecognized key inside a shortcut dict prints a warning naming the shortcut."""
    optmux = {"shortcuts": {"C-M-x": {"comand": "htop"}}}
    normalize_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert "comand" in err
    assert "C-M-x" in err
    assert "test-source" in err


def test_normalize_optmux_section_ignores_underscore_prefixed_keys(capsys):
    """Keys starting with '_' (e.g. YAML anchors used as scratch data) are not warned about."""
    optmux = {"_anchors": {"foo": "bar"}, "shortcuts": {"C-M-x": {"_note": "personal reminder", "command": "htop"}}}
    normalize_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert err == ""


def test_normalize_optmux_section_warns_on_unknown_menu_context(capsys):
    """Unrecognized menu: context prints a warning naming the context."""
    optmux = {"menu": {"pane_wrong": ["*"]}}
    normalize_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert "pane_wrong" in err
    assert "test-source" in err


def test_normalize_optmux_section_warns_on_unknown_menu_item_key(capsys):
    """Unrecognized key inside a menu item dict prints a warning."""
    optmux = {"menu": {"pane": [{"key": "w", "titel": "New Window"}]}}
    normalize_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert "titel" in err
    assert "test-source" in err


def test_normalize_optmux_section_accepts_known_menu_config():
    optmux = {"menu": {"pane": [{"key": "w", "title": "New Window"}, "*"]}}
    normalize_optmux_section(optmux, "test-source")  # should not raise


# --- `+keyword` syntax -------------------------------------------------------------------------------------------


def test_plus_syntax_loads_as_bare_keywords(capsys):
    data = yaml.safe_load("""\
+optmux:
  +shortcuts:
    C-M-x:
      +command: htop
      +new_window: true
    command: a shortcut key may be named like a keyword
  +menu:
    +pane:
    - +key: e
      +title: Edit
      +command: vim
    - "*"
  +find:
    +preview: false
    +lsp:
      python:
        +extensions:
        - py
        +servers:
        - +command: pylsp
  +plugins:
    netj/claritmux:
      +tip_url: https://example.com
      claritmux_status_date: 0
  +env:
    find: not a keyword here
""")
    result = read_optmux_section(data, "src")
    assert capsys.readouterr().err == ""
    assert result["shortcuts"]["C-M-x"] == {"command": "htop", "new_window": True}
    assert result["shortcuts"]["command"] == "a shortcut key may be named like a keyword"
    assert result["menu"]["pane"] == [{"key": "e", "title": "Edit", "command": "vim"}, "*"]
    assert result["find"] == {"preview": False, "lsp": {"python": {"extensions": ["py"], "servers": [{"command": "pylsp"}]}}}
    assert result["plugins"]["netj/claritmux"] == {"_tip_url": "https://example.com", "claritmux_status_date": 0}
    assert result["env"] == {"find": "not a keyword here"}


def test_strict_section_says_to_write_plus_for_a_bare_keyword(capsys):
    result = normalize_optmux_section({"+shortcuts": {"C-M-x": {"command": "htop"}}, "env": {"A": "1"}}, "src", strict=True)
    err = capsys.readouterr().err
    assert "'command' (write +command)" in err and "'env' (write +env)" in err
    assert result == {"shortcuts": {"C-M-x": {}}}


def test_bare_optmux_still_works_but_is_deprecated(capsys):
    result = read_optmux_section({"optmux": {"shortcuts": {"C-M-x": {"command": "htop"}}}}, "my.yaml")
    err = capsys.readouterr().err
    assert result == {"shortcuts": {"C-M-x": {"command": "htop"}}}
    assert "my.yaml" in err and "deprecated" in err and "+optmux:" in err


def test_plus_optmux_is_not_deprecated(capsys):
    read_optmux_section({"+optmux": {"+icons": "emoji"}}, "my.yaml")
    assert capsys.readouterr().err == ""


def test_both_forms_merge_with_plus_winning(capsys):
    data = {"optmux": {"shortcuts": {"C-M-a": "old", "C-M-b": "old"}}, "+optmux": {"+shortcuts": {"C-M-b": "new"}}}
    result = read_optmux_section(data, "my.yaml")
    assert result["shortcuts"] == {"C-M-a": "old", "C-M-b": "new"}
    assert "both" in capsys.readouterr().err


def test_unknown_plus_keyword_is_warned_about(capsys):
    normalize_optmux_section({"+shortcutz": {}, "+menu": {"+pane": [{"+titel": "x", "+key": "k"}], "+nope": []}}, "src", strict=True)
    err = capsys.readouterr().err
    assert "+shortcutz" in err and "+titel" in err and "'+nope'" in err


def test_examples_load_without_warnings(capsys):
    """The example files in the repo use the current syntax and only words optmux knows."""
    from pathlib import Path
    examples = sorted(Path(__file__).parent.parent.glob("*.optmux.yaml"))
    assert any(p.name == "transform.optmux.yaml" for p in examples)
    for p in examples:
        read_optmux_section(yaml.safe_load(p.read_text()), p.name)
    assert capsys.readouterr().err == ""


def test_transform_example_works_with_every_setting_switched_on(capsys, tmp_path):
    """transform.optmux.yaml is for taking lines from, so each commented-out line must be valid to use."""
    from optmux.cli import generate_plugins_conf, generate_shortcut_line, generate_tmux_conf_files, merge_optmux

    text = (Path(__file__).parent.parent / "transform.optmux.yaml").read_text()
    # delete the `#` of commented-out settings (`#key` or `#  key`); `# prose` has exactly one space
    on = re.sub(r"^( *)#(?=[^\s!]| {2})", r"\1", text, flags=re.M)
    assert on != text
    data = yaml.safe_load(on)
    mine = read_optmux_section(data, "transform")
    assert capsys.readouterr().err == ""
    assert mine["plugins"]["Morantron/tmux-fingers"]["fingers-pattern-1"] == r"\b[A-Z][A-Z0-9]+-\d+\b"
    assert all(generate_shortcut_line(key, value) is not None for key, value in mine["shortcuts"].items())
    merged = merge_optmux(load_bundled_defaults(), mine)
    assert "@fingers-hint-position" in generate_plugins_conf(merged["plugins"])
    assert merged["find"]["ignore_files"]["dependencies"] and merged["find"]["ignore_files"]["mine"]
    assert merged["find"]["lsp"]["python"]["servers"] and merged["find"]["lsp"]["ruby"]["command"]
    tmux_dir = tmp_path / "tmux"
    tmux_dir.mkdir()
    generate_tmux_conf_files(tmux_dir, merged, load_bundled_defaults()["shortcuts"])
    assert "set -g history-limit 100000" in (tmux_dir / "tmux.optmux-extras.my-settings.conf").read_text()
    assert capsys.readouterr().err == ""


def test_a_plugin_can_carry_a_list_of_tip_urls_and_only_that_keyword(capsys):
    result = normalize_optmux_section(
        {"+plugins": {"a/b": {"+tip_url": ["u1", "u2"], "+bogus": 1, "some-option": 2}, "c/d": False, "e/f": None}},
        "src", strict=True,
    )
    assert result["plugins"] == {"a/b": {"_tip_url": ["u1", "u2"], "some-option": 2}, "c/d": False, "e/f": None}
    assert "'+bogus'" in capsys.readouterr().err


def test_plus_keywords_are_accepted_in_the_legacy_section_too(capsys):
    result = normalize_optmux_section({"+shortcuts": {"C-M-x": {"+command": "htop", "new_window": True}}}, "src")
    assert result == {"shortcuts": {"C-M-x": {"command": "htop", "new_window": True}}}
    assert capsys.readouterr().err == ""


def test_strict_section_catches_typos_in_shortcuts_menus_and_find(capsys):
    normalize_optmux_section(
        {"+shortcuts": {"C-M-x": {"+comand": "htop"}}, "+menu": {"+pane": [{"+titel": "x"}]}, "+find": {"+lspp": {}}},
        "src", strict=True,
    )
    err = capsys.readouterr().err
    assert "'+comand'" in err and "'+titel'" in err and "'+lspp'" in err


def test_a_non_mapping_plus_optmux_is_warned_about(capsys):
    assert read_optmux_section({"+optmux": ["shortcuts"]}, "my.yaml") == {}
    assert "`+optmux:` is not a mapping" in capsys.readouterr().err
    assert read_optmux_section({"+optmux": None}, "my.yaml") == {}
    assert capsys.readouterr().err == ""


def test_bundled_defaults_load_clean_through_the_file_reader(capsys):
    load_bundled_defaults()
    assert capsys.readouterr().err == ""


def test_shortcut_keys_yaml_reads_as_numbers_work_as_text(capsys, tmp_path):
    """`1:` is an int in YAML; it is the key "1" (prefix+1), not a crash."""
    from optmux.cli import generate_tmux_conf_files, merge_optmux

    data = yaml.safe_load("+optmux:\n  +shortcuts:\n    1: echo one\n    C-M-9: echo nine\n")
    mine = read_optmux_section(data, "src")
    assert list(mine["shortcuts"]) == ["1", "C-M-9"]
    tmux_dir = tmp_path / "tmux"
    tmux_dir.mkdir()
    generate_tmux_conf_files(tmux_dir, merge_optmux(load_bundled_defaults(), mine), load_bundled_defaults()["shortcuts"])
    assert "bind 1 " in (tmux_dir / "tmux.optmux-shortcuts.conf").read_text()
    assert capsys.readouterr().err == ""


def test_shortcut_keys_yaml_reads_as_booleans_or_null_are_skipped_with_a_hint(capsys):
    """`on:`, `no:` and `~:` lose their letters in YAML, so they warn (quote them) instead of crashing."""
    data = yaml.safe_load("+optmux:\n  +shortcuts:\n    on: echo a\n    no: echo b\n    ~: echo c\n    ok: echo d\n")
    assert read_optmux_section(data, "src")["shortcuts"] == {"ok": "echo d"}
    err = capsys.readouterr().err
    assert err.count("is not text") == 3 and "quote it" in err and "shortcut True" in err


def test_menu_item_keys_and_titles_that_yaml_reads_as_non_text(capsys):
    from optmux import menu

    mine = read_optmux_section(yaml.safe_load("""\
+optmux:
  +menu:
    +pane:
    - +key: 1
      +title: 2024
      +command: echo a
    - +key: on
      +title: Skipped
      +command: echo b
"""), "src")
    assert mine["menu"]["pane"] == [{"key": "1", "title": 2024, "command": "echo a"}]
    assert "is not text" in capsys.readouterr().err
    out = menu.generate_menu_conf(mine["menu"], source="src")
    assert "'2024' '1'" in out


def test_plugin_names_that_yaml_reads_as_non_text_do_not_crash(capsys):
    from optmux.cli import generate_plugins_conf

    plugins = read_optmux_section(yaml.safe_load("+optmux:\n  +plugins:\n    1:\n    off:\n    a/b:\n"), "src")["plugins"]
    assert list(plugins) == ["1", "a/b"]
    assert "set -g @plugin '1'" in generate_plugins_conf(plugins)
    assert "plugin False" in capsys.readouterr().err


def test_two_spellings_of_one_shortcut_key_are_warned_about(capsys):
    data = yaml.safe_load("+optmux:\n  +shortcuts:\n    '1': echo a\n    1: echo b\n")
    assert read_optmux_section(data, "src")["shortcuts"] == {"1": "echo b"}
    assert "same key as an earlier one" in capsys.readouterr().err


def test_float_shortcut_keys_must_be_quoted(capsys):
    assert read_optmux_section(yaml.safe_load("+optmux:\n  +shortcuts:\n    1.5: echo\n"), "src")["shortcuts"] == {}
    assert "quote it" in capsys.readouterr().err
