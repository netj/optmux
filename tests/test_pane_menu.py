from optmux import pane_menu
from optmux.pane_menu import (
    FLOATING_PANE_ANCHOR,
    MENU_ITEM,
    STABLE_ANCHOR,
    augment_binding,
)


STABLE_BINDING = (
    'bind-key -T root MouseDown3Pane display-menu -x M -y M '
    "'' "
    f'{STABLE_ANCHOR} "Vertical Split" v {{ split-window -v }} Kill X {{ kill-pane }}'
)
FLOATING_PANE_BINDING = (
    'bind-key -T root MouseDown3Pane display-menu -x M -y M '
    "'' "
    f'{FLOATING_PANE_ANCHOR} "Vertical Split" v {{ split-window -v }} Kill X {{ kill-pane }}'
)


def test_augment_binding_inserts_new_window_into_stable_menu():
    augmented = augment_binding(STABLE_BINDING)

    assert augmented is not None
    assert augmented.count(MENU_ITEM) == 1
    assert augmented.replace(f"{MENU_ITEM} ", "", 1) == STABLE_BINDING


def test_augment_binding_inserts_new_window_into_floating_pane_menu():
    augmented = augment_binding(FLOATING_PANE_BINDING)

    assert augmented is not None
    assert augmented.count(MENU_ITEM) == 1
    assert augmented.replace(f"{MENU_ITEM} ", "", 1) == FLOATING_PANE_BINDING


def test_augment_binding_is_idempotent():
    augmented = augment_binding(STABLE_BINDING)

    assert augment_binding(augmented) == augmented


def test_augment_binding_fails_closed_without_exact_anchor():
    custom = STABLE_BINDING.replace(
        STABLE_ANCHOR, '"Split Sideways" h { split-window -h }'
    )

    assert augment_binding(custom) is None


def test_augment_binding_fails_closed_on_ambiguous_anchor():
    assert augment_binding(f"{STABLE_BINDING} {STABLE_ANCHOR}") is None


def test_augment_binding_fails_closed_with_both_recognized_anchor_shapes():
    assert augment_binding(f"{STABLE_BINDING} {FLOATING_PANE_ANCHOR}") is None


def test_augment_binding_fails_closed_on_conflicting_label():
    custom = STABLE_BINDING.replace("Kill", '"New Window (C-t c)" Kill')

    assert augment_binding(custom) is None


def test_augment_binding_fails_closed_on_accelerator_collision():
    custom = STABLE_BINDING.replace(
        "Kill X", 'Something w { display-message no } Kill X'
    )

    assert augment_binding(custom) is None


def test_install_restores_original_binding_when_postcheck_fails(monkeypatch):
    readings = iter([STABLE_BINDING, "unexpected binding"])
    sourced = []
    monkeypatch.setattr(pane_menu, "_current_binding", lambda: next(readings))
    monkeypatch.setattr(
        pane_menu,
        "_source_binding",
        lambda binding: sourced.append(binding) or True,
    )

    pane_menu.install()

    assert sourced == [augment_binding(STABLE_BINDING), STABLE_BINDING]


def test_install_restores_original_binding_when_candidate_source_fails(monkeypatch):
    sourced = []
    monkeypatch.setattr(pane_menu, "_current_binding", lambda: STABLE_BINDING)

    def source_binding(binding):
        sourced.append(binding)
        return binding == STABLE_BINDING

    monkeypatch.setattr(pane_menu, "_source_binding", source_binding)

    pane_menu.install()

    assert sourced == [augment_binding(STABLE_BINDING), STABLE_BINDING]
