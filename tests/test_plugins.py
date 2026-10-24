from optmux.cli import generate_plugins_conf, generate_tmux_conf_files, merge_optmux


def test_merge_plugins_later_replaces_entry():
    a = {"plugins": {"a/x": ["set -g @x 1"], "b/y": None}}
    b = {"plugins": {"a/x": ["set -g @x 2"], "c/z": None}}
    assert merge_optmux(a, b)["plugins"] == {
        "a/x": ["set -g @x 2"], "b/y": None, "c/z": None,
    }


def test_generate_plugins_conf_lines_and_order():
    out = generate_plugins_conf({
        "a/x": ["set -g @x 1", "set -g @y 2"],
        "b/y": None,
        "c/z": "set -g @z 3\nset -g @w 4",
    })
    assert out == (
        "set -g @tpm_plugins 'a/x b/y c/z'\n"
        "set -g @plugin 'a/x'\nset -g @x 1\nset -g @y 2\n"
        "set -g @plugin 'b/y'\n"
        "set -g @plugin 'c/z'\nset -g @z 3\nset -g @w 4\n"
    )


def test_generate_plugins_conf_false_disables():
    out = generate_plugins_conf({"a/x": ["set -g @x 1"], "b/y": False})
    assert "b/y" not in out and "@x" in out


def test_plugins_file_written_and_change_detected(tmp_path):
    cfg = {"plugins": {"a/x": None}}
    assert generate_tmux_conf_files(tmp_path, cfg) is True
    assert "@plugin 'a/x'" in (tmp_path / "optmux-plugins.conf").read_text()
    assert generate_tmux_conf_files(tmp_path, cfg) is False
    generate_tmux_conf_files(tmp_path, {})
    assert not (tmp_path / "optmux-plugins.conf").exists()


def test_generate_plugins_conf_dict_options():
    out = generate_plugins_conf({
        "a/x": {"x_area": "window recent", "@x_on": True, "x_off": False, "x_n": 5,
                "x_q": 'say "hi"'},
    })
    assert out == (
        "set -g @tpm_plugins 'a/x'\n"
        "set -g @plugin 'a/x'\n"
        'set -g @x_area "window recent"\n'
        'set -g @x_on "on"\n'
        'set -g @x_off "off"\n'
        'set -g @x_n "5"\n'
        'set -g @x_q "say \\"hi\\""\n'
    )


def test_plugin_url_github_and_full_url():
    from optmux.cli import plugin_url
    assert plugin_url("laktak/extrakto") == "https://github.com/laktak/extrakto"
    assert plugin_url("https://example.com/x/y.git") == "https://example.com/x/y.git"
    assert plugin_url("git@github.com:x/y.git") == "git@github.com:x/y.git"


def test_generate_plugins_tips_aligned_and_skips_disabled():
    from optmux.cli import generate_plugins_tips
    out = generate_plugins_tips({"a/x": None, "bb/yyy": {"o": 1}, "c/z": False})
    assert out == (
        "  a/x     https://github.com/a/x\n"
        "  bb/yyy  https://github.com/bb/yyy\n"
    )
    assert generate_plugins_tips({}) == ""


def test_plugins_tips_file_written_and_removed(tmp_path):
    generate_tmux_conf_files(tmp_path, {"plugins": {"a/x": None}})
    assert "https://github.com/a/x" in (tmp_path / "tips-plugins.txt").read_text()
    generate_tmux_conf_files(tmp_path, {})
    assert not (tmp_path / "tips-plugins.txt").exists()


def test_underscore_keys_are_metadata_not_options():
    out = generate_plugins_conf({"a/x": {"_url": "https://v/1", "opt": 1}})
    assert "_url" not in out and 'set -g @opt "1"' in out


def test_plugins_tips_showcase_urls():
    from optmux.cli import generate_plugins_tips
    out = generate_plugins_tips({
        "a/x": {"_url": "https://v/1", "o": 1},
        "bb/y": {"_url": ["https://p/1", "https://p/2"]},
        "c/z": None,
    })
    assert out == (
        "  a/x   https://github.com/a/x\n"
        "        -> https://v/1\n"
        "  bb/y  https://github.com/bb/y\n"
        "        -> https://p/1\n"
        "        -> https://p/2\n"
        "  c/z   https://github.com/c/z\n"
    )
