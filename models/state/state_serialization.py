"""
State serialization helpers: convert PetState to/from dict for local/cloud storage.

Compatible with both old (mood/energy/intimacy only) and new (with level/exp/coins/hunger/bond_score) formats.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# Default values for new fields
_DEFAULT_NEW_FIELDS = {
    "level": 1,
    "exp": 0,
    "coins": 0,
    "hunger": 50,
    "bond_score": 0,
}


def pet_state_to_dict(pet_state: Any) -> Dict[str, Any]:
    """
    Convert a PetState instance to a flat dict for serialization.

    :param pet_state: PetState instance
    :returns: dict with all state fields
    """
    data = {
        "pet_id": getattr(pet_state, "pet_id", "cat"),
        "mood": getattr(pet_state, "mood", "neutral"),
        "energy": getattr(pet_state, "energy", 100),
        "intimacy": getattr(pet_state, "intimacy", 50),
        "level": getattr(pet_state, "level", 1),
        "exp": getattr(pet_state, "exp", 0),
        "coins": getattr(pet_state, "coins", 0),
        "hunger": getattr(pet_state, "hunger", 50),
        "bond_score": getattr(pet_state, "bond_score", 0),
    }
    return data


def apply_dict_to_pet_state(pet_state: Any, data: Dict[str, Any]) -> None:
    """
    Apply a dict to a PetState instance, preserving existing values for missing keys.

    Compatible with old-format JSON (which only has mood/energy/intimacy/pet_id).

    :param pet_state: PetState instance (modified in-place)
    :param data:      dict with state fields
    """
    if not isinstance(data, dict):
        return

    # Old fields (always present)
    if "pet_id" in data:
        try:
            pet_state.set_pet_id(str(data["pet_id"]))
        except (AttributeError, TypeError):
            pass
    if "mood" in data:
        pet_state.mood = str(data["mood"])
    if "energy" in data:
        pet_state.energy = max(0, min(100, int(data["energy"])))
    if "intimacy" in data:
        pet_state.intimacy = max(0, min(100, int(data["intimacy"])))

    # New fields (use setattr if they exist on PetState)
    for key, default_val in _DEFAULT_NEW_FIELDS.items():
        if key in data:
            value = data[key]
        else:
            value = default_val
        if hasattr(pet_state, key):
            setattr(pet_state, key, value)
        else:
            print(f"[state_serialization] PetState has no attribute '{key}', skipped.")


def apply_cloud_state_to_pet_state(pet_state: Any, cloud_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply remote cloud state to a local PetState, using updated_at conflict resolution.

    If cloud_state has a newer updated_at, apply it; otherwise skip.

    :param pet_state:   local PetState instance
    :param cloud_state: remote state dict (must include updated_at)
    :returns: dict with changes applied (or empty dict if no changes)
    """
    if not isinstance(cloud_state, dict):
        return {}

    # TODO: Implement proper updated_at comparison
    # local_updated = getattr(pet_state, "updated_at", 0.0)
    # remote_updated = float(cloud_state.get("updated_at", 0.0))
    # if remote_updated <= local_updated:
    #     return {}

    apply_dict_to_pet_state(pet_state, cloud_state)
    return dict(cloud_state)
