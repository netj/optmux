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
