"""Organization profile generation for the synthetic IAM benchmark."""

from __future__ import annotations

from random import Random
from typing import Any

from .templates import ORGANIZATION_PROFILES


def build_org_profiles(seed: int = 7) -> dict[str, dict[str, Any]]:
    """Return deterministic organization profiles keyed by org name."""
    rng = Random(seed)
    profiles: dict[str, dict[str, Any]] = {}
    for name, profile in ORGANIZATION_PROFILES.items():
        org_profile = {
            "name": name,
            "description": profile["description"],
            "roles": list(profile["roles"]),
            "positive_operators": dict(profile["positive_operators"]),
            "seed_offset": rng.randint(0, 10000),
        }
        profiles[name] = org_profile
    return profiles
