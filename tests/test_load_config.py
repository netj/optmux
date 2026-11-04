from pathlib import Path

from optmux.cli import normalize_optmux_section, load_bundled_defaults, load_optmux_conf


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


def testnormalize_optmux_section_warns_on_unknown_shortcut_key(capsys):
    """Unrecognized key inside a shortcut dict prints a warning naming the shortcut."""
    optmux = {"shortcuts": {"C-M-x": {"comand": "htop"}}}
    normalize_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert "comand" in err
    assert "C-M-x" in err
    assert "test-source" in err


def testnormalize_optmux_section_ignores_underscore_prefixed_keys(capsys):
    """Keys starting with '_' (e.g. YAML anchors used as scratch data) are not warned about."""
    optmux = {"_anchors": {"foo": "bar"}, "shortcuts": {"C-M-x": {"_note": "personal reminder", "command": "htop"}}}
    normalize_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert err == ""


def testnormalize_optmux_section_warns_on_unknown_menu_context(capsys):
    """Unrecognized menu: context prints a warning naming the context."""
    optmux = {"menu": {"pane_wrong": ["*"]}}
    normalize_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert "pane_wrong" in err
    assert "test-source" in err


def testnormalize_optmux_section_warns_on_unknown_menu_item_key(capsys):
    """Unrecognized key inside a menu item dict prints a warning."""
    optmux = {"menu": {"pane": [{"key": "w", "titel": "New Window"}]}}
    normalize_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert "titel" in err
    assert "test-source" in err


def testnormalize_optmux_section_accepts_known_menu_config():
    optmux = {"menu": {"pane": [{"key": "w", "title": "New Window"}, "*"]}}
    normalize_optmux_section(optmux, "test-source")  # should not raise


# --- `+keyword` syntax -------------------------------------------------------------------------------------------

import yaml

from optmux.cli import normalize_optmux_section, read_optmux_section


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
        +extensions: [py]
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
    examples = sorted(Path(__file__).parent.parent.glob("*example*.optmux.yaml"))
    assert any(p.name == "example-full.optmux.yaml" for p in examples)
    for p in examples:
        read_optmux_section(yaml.safe_load(p.read_text()), p.name)
    assert capsys.readouterr().err == ""


def test_example_full_plugins_mirror_the_bundled_defaults():
    """example-full.optmux.yaml's live plugin entries are optmux-defaults.yaml's; update both together."""
    from pathlib import Path
    p = Path(__file__).parent.parent / "example-full.optmux.yaml"
    mine = read_optmux_section(yaml.safe_load(p.read_text()), p.name)["plugins"]
    assert mine == load_bundled_defaults()["plugins"]
