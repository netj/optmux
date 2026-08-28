from pathlib import Path

from optmux.cli import _validate_optmux_section, load_bundled_defaults, load_optmux_conf


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


def test_validate_optmux_section_warns_on_unknown_shortcut_key(capsys):
    """Unrecognized key inside a shortcut dict prints a warning naming the shortcut."""
    optmux = {"shortcuts": {"C-M-x": {"comand": "htop"}}}
    _validate_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert "comand" in err
    assert "C-M-x" in err
    assert "test-source" in err


def test_validate_optmux_section_ignores_underscore_prefixed_keys(capsys):
    """Keys starting with '_' (e.g. YAML anchors used as scratch data) are not warned about."""
    optmux = {"_anchors": {"foo": "bar"}, "shortcuts": {"C-M-x": {"_note": "personal reminder", "command": "htop"}}}
    _validate_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert err == ""


def test_validate_optmux_section_warns_on_unknown_menu_context(capsys):
    """Unrecognized menu: context prints a warning naming the context."""
    optmux = {"menu": {"pane_wrong": ["*"]}}
    _validate_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert "pane_wrong" in err
    assert "test-source" in err


def test_validate_optmux_section_warns_on_unknown_menu_item_key(capsys):
    """Unrecognized key inside a menu item dict prints a warning."""
    optmux = {"menu": {"pane": [{"key": "w", "titel": "New Window"}]}}
    _validate_optmux_section(optmux, "test-source")
    err = capsys.readouterr().err
    assert "titel" in err
    assert "test-source" in err


def test_validate_optmux_section_accepts_known_menu_config():
    optmux = {"menu": {"pane": [{"key": "w", "title": "New Window"}, "*"]}}
    _validate_optmux_section(optmux, "test-source")  # should not raise
