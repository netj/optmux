from optmux import cli

NEW = {"LESS": "-XRiMWSc --mouse", "LESS_OSC8_OPEN_ANY": "\x10-optmux-open-url", "PAGER": "less"}


def test_new_less_unchanged():
    assert cli.adapt_env_for_less(NEW, 710) == NEW


def test_unknown_less_unchanged():
    assert cli.adapt_env_for_less(NEW, None) == NEW


def test_old_link_protocol_between_661_and_701():
    env = cli.adapt_env_for_less(NEW, 668)
    assert "LESS_OSC8_OPEN_ANY" not in env
    assert env["LESS_OSC8_ANY"] == "echo \"optmux-open-url '%o'\""
    assert env["LESS_OSC8_file"] == "-"
    assert env["LESS"] == NEW["LESS"]


def test_no_links_below_661_and_no_mouse_below_551():
    env = cli.adapt_env_for_less(NEW, 600)
    assert not any(k.startswith("LESS_OSC8") for k in env)
    assert env["LESS"] == "-XRiMWSc --mouse"
    env = cli.adapt_env_for_less(NEW, 487)
    assert env["LESS"] == "-XRiMWSc"


def test_input_not_mutated():
    cli.adapt_env_for_less(NEW, 487)
    assert NEW["LESS"] == "-XRiMWSc --mouse"


def test_less_version_parsed_from_stub(tmp_path):
    less = tmp_path / "less"
    less.write_text('#!/bin/sh\necho "less 668 (POSIX regular expressions)"\n')
    less.chmod(0o755)
    assert cli.less_version(str(less)) == 668
    assert cli.less_version(str(tmp_path / "nope")) is None
