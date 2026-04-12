from optmux.cli import merge_optmux


def test_merge_empty():
    assert merge_optmux({}, {}) == {}


def test_merge_single_layer():
    layer = {"shortcuts": {"C-M-s": "cmd"}}
    assert merge_optmux(layer) == {"shortcuts": {"C-M-s": "cmd"}}


def test_merge_later_wins():
    a = {"shortcuts": {"C-M-g": "lazygit"}}
    b = {"shortcuts": {"C-M-g": "gitui"}}
    result = merge_optmux(a, b)
    assert result["shortcuts"]["C-M-g"] == "gitui"


def test_merge_preserves_unique_keys():
    a = {"shortcuts": {"C-M-s": ""}}
    b = {"shortcuts": {"C-M-g": "lazygit"}}
    result = merge_optmux(a, b)
    assert result["shortcuts"] == {"C-M-s": "", "C-M-g": "lazygit"}


def test_merge_three_layers():
    bundled = {"shortcuts": {"C-M-s": "", "C-M-g": "lazygit"}}
    project = {"shortcuts": {"C-M-b": "gh browse ."}}
    personal = {"shortcuts": {"C-M-g": "gitui"}}
    result = merge_optmux(bundled, project, personal)
    assert result["shortcuts"] == {
        "C-M-s": "",
        "C-M-g": "gitui",  # personal wins
        "C-M-b": "gh browse .",
    }


def test_merge_tmux_config():
    a = {"tmux_config": {"colors": "set -g status-style bg=blue\n"}}
    b = {"tmux_config": {"mouse": "set -g mouse on\n"}}
    result = merge_optmux(a, b)
    assert result["tmux_config"] == {
        "colors": "set -g status-style bg=blue\n",
        "mouse": "set -g mouse on\n",
    }


def test_merge_mixed():
    layer = {
        "shortcuts": {"C-M-s": ""},
        "tmux_config": {"x": "y"},
    }
    result = merge_optmux(layer)
    assert "shortcuts" in result
    assert "tmux_config" in result


def test_merge_none_values():
    """Layer with shortcuts: None treated as empty."""
    a = {"shortcuts": {"C-M-s": ""}}
    b = {"shortcuts": None}
    result = merge_optmux(a, b)
    assert result["shortcuts"] == {"C-M-s": ""}
