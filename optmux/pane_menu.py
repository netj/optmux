#!/usr/bin/env python3
"""Safely add optmux actions to tmux's built-in pane context menu."""

import subprocess


BINDING_PREFIX = "bind-key -T root MouseDown3Pane "
STABLE_ANCHOR = '"Horizontal Split" h { split-window -h }'
FLOATING_PANE_ANCHOR = (
    '"#{?#{!:#{pane_floating_flag}},Horizontal Split,}" h { split-window -h }'
)
ANCHORS = (STABLE_ANCHOR, FLOATING_PANE_ANCHOR)
MENU_ITEM = '"New Window (C-t c)" w { new-window -c "#{pane_current_path}" }'


def augment_binding(binding):
    """Return an augmented binding, or None when it is unsafe to change."""
    if "\n" in binding or "\r" in binding or not binding.startswith(BINDING_PREFIX):
        return None

    item_count = binding.count(MENU_ITEM)
    if item_count == 1:
        return binding if sum(binding.count(anchor) for anchor in ANCHORS) == 1 else None
    if item_count != 0 or "New Window (C-t c)" in binding:
        return None
    if " w {" in binding:
        return None
    anchor_counts = {anchor: binding.count(anchor) for anchor in ANCHORS}
    if sum(anchor_counts.values()) != 1:
        return None

    anchor = next(anchor for anchor, count in anchor_counts.items() if count == 1)
    return binding.replace(anchor, f"{MENU_ITEM} {anchor}", 1)


def _run_tmux(*args, input_text=None):
    return subprocess.run(
        ["tmux", *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def _current_binding():
    result = _run_tmux("list-keys", "-T", "root", "MouseDown3Pane")
    if result.returncode != 0 or not result.stdout.endswith("\n"):
        return None
    binding = result.stdout[:-1]
    return binding if "\n" not in binding and "\r" not in binding else None


def _source_binding(binding):
    return _run_tmux("source-file", "-", input_text=f"{binding}\n").returncode == 0


def install():
    """Install the menu item transactionally, leaving unsafe bindings alone."""
    before = _current_binding()
    if before is None:
        return

    candidate = augment_binding(before)
    if candidate is None or candidate == before:
        return

    if not _source_binding(candidate) or _current_binding() != candidate:
        _source_binding(before)


if __name__ == "__main__":
    try:
        install()
    except OSError:
        # Configuration loading must not damage or block an existing tmux setup.
        pass
