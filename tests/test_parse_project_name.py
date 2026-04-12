import pytest

from optmux.cli import parse_project_name


@pytest.mark.parametrize(
    "input_path, expected",
    [
        ("myproject.yaml", "myproject"),
        ("myproject.optmux.yaml", "myproject"),
        ("myproject.tmuxp.yaml", "myproject"),
        ("myproject.optmuxp.yaml", "myproject"),
        ("myproject", "myproject"),
        ("/home/user/projects/foo.optmux.yaml", "foo"),
        ("my.project.optmux.yaml", "my.project"),
        ("plain.yaml", "plain"),
        # strips all matching suffixes in order
        ("myproject.optmux.tmuxp.yaml", "myproject"),
    ],
)
def test_parse_project_name(input_path, expected):
    assert parse_project_name(input_path) == expected
