from pathlib import Path

from optmux.cli import load_bundled_defaults, load_optmux_conf


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
