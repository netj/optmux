import shutil

import pytest

HAS_TMUX = shutil.which("tmux") is not None
skip_no_tmux = pytest.mark.skipif(not HAS_TMUX, reason="tmux not found on PATH")


@pytest.fixture
def bundled_defaults():
    """Mirrors optmux-defaults.yaml content."""
    return {
        "shortcuts": {
            "C-M-s": "",
            "C-M-c": {"command": "wtcode", "new_window": True},
            "C-M-f": {"command": "${VISUAL:-${EDITOR:-vim}} $(fzf || echo .)"},
            "C-M-g": "lazygit",
        }
    }


@pytest.fixture
def sample_optmux_config():
    """Config with various shortcut types + tmux_config."""
    return {
        "shortcuts": {
            "C-M-s": "",
            "C-M-g": "lazygit",
            "C-M-e": {"command": "vim README.md", "new_window": True},
            "E": {"send-keys": "vim .", "zoom": False},
        },
        "tmux_config": {
            "project-settings": "set -g status-style bg=blue\n",
        },
    }


@pytest.fixture
def project_yaml_file(tmp_path):
    """Create a temporary .optmux.yaml project file, return its path."""
    content = """\
session_name: myproject
start_directory: .
optmux:
  shortcuts:
    C-M-b: gh browse .
  tmux_config:
    project-settings: |
      set -g status-style bg=blue
windows:
  - window_name: editor
    panes:
      - vim .
"""
    p = tmp_path / "myproject.optmux.yaml"
    p.write_text(content)
    return p


@pytest.fixture
def personal_yaml_file(tmp_path):
    """Create a temporary personal ~/.optmux.yaml, return its path."""
    content = """\
optmux:
  shortcuts:
    C-M-x: htop
"""
    p = tmp_path / ".optmux.yaml"
    p.write_text(content)
    return p


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Update golden files with actual output",
    )


@pytest.fixture
def update_golden(request):
    return request.config.getoption("--update-golden")
