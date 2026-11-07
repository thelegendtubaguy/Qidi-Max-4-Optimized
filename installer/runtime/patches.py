from __future__ import annotations

from . import klipper_cfg
from .manifest import select_patch_variant
from .models import PatchLedgerEntry, PatchResult, PatchSpec, SectionPatchSpec


INSTALL_APPLIED = "applied"
INSTALL_NOOP_DESIRED = "noop_desired"
UNINSTALL_REVERTED = "reverted"
UNINSTALL_NOOP_EXPECTED = "noop_expected"
USER_MODIFIED = "user_modified"
SECTION_DELETED = "__TLTG_SECTION_DELETED__"


def classify_install_patch(current: str, patch: PatchSpec, firmware_version: str, prior_state=None) -> PatchResult:
    variant = select_patch_variant(patch, firmware_version)
    ledger_expected = None
    if current == variant.desired:
        classification = INSTALL_NOOP_DESIRED
    elif current == variant.expected:
        classification = INSTALL_APPLIED
    elif _prior_managed_value(current, prior_state, patch):
        classification = INSTALL_APPLIED
    elif _above_maximum(current, patch):
        classification = INSTALL_APPLIED
        ledger_expected = current
    else:
        classification = USER_MODIFIED
    return PatchResult(
        id=patch.id,
        file=patch.file,
        section=patch.section,
        option=patch.option,
        current=current,
        expected=variant.expected,
        desired=variant.desired,
        classification=classification,
        ledger_expected=ledger_expected,
    )


def _above_maximum(current: str, patch: PatchSpec) -> bool:
    if patch.maximum is None:
        return False
    try:
        return float(current) > patch.maximum
    except ValueError:
        return False



def _prior_managed_value(current: str, prior_state, patch: PatchSpec) -> bool:
    prior_value = {
        "stepper_x_homing_speed": "100",
        "stepper_y_homing_speed": "100",
        "stepper_x_homing_retract_speed": "1000.0",
        "stepper_y_homing_retract_speed": "1000.0",
        "z_tilt_speed": "600",
        "bed_mesh_speed": "600",
    }.get(patch.id)
    if prior_value is None or current != prior_value or prior_state is None:
        return False
    return any(
        entry.id == patch.id
        and entry.target_tuple == patch.target_tuple
        and entry.expected == select_patch_variant(patch, prior_state.runtime_firmware).expected
        and entry.desired == prior_value
        and entry.install_result in {INSTALL_APPLIED, INSTALL_NOOP_DESIRED}
        for entry in prior_state.patch_ledger
    )


def classify_install_section_delete(
    current: str | None, patch: SectionPatchSpec, firmware_version: str
) -> PatchResult:
    variant = select_patch_variant(patch, firmware_version)
    if current is None:
        classification = INSTALL_NOOP_DESIRED
        expected = variant.expected_normalized_sha256
        current_value = SECTION_DELETED
    else:
        current_hash = klipper_cfg.normalized_section_sha256(current)
        if current_hash == variant.expected_normalized_sha256:
            classification = INSTALL_APPLIED
        else:
            classification = USER_MODIFIED
        expected = current if classification == INSTALL_APPLIED else variant.expected_normalized_sha256
        current_value = current
    return PatchResult(
        id=patch.id,
        file=patch.file,
        section=patch.section,
        option=patch.option,
        current=current_value,
        expected=expected,
        desired=SECTION_DELETED,
        classification=classification,
    )



def classify_uninstall_patch(current: str, entry: PatchLedgerEntry) -> PatchResult:
    if current == entry.desired:
        classification = UNINSTALL_REVERTED
    elif current == entry.expected:
        classification = UNINSTALL_NOOP_EXPECTED
    else:
        classification = USER_MODIFIED
    return PatchResult(
        id=entry.id,
        file=entry.file,
        section=entry.section,
        option=entry.option,
        current=current,
        expected=entry.expected,
        desired=entry.desired,
        classification=classification,
    )

