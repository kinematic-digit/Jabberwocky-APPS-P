# =====================================================================
# JWS V3.0 SYSTEM ARCHITECTURE PACKAGE INITIALIZATION ANCHOR (__init__.py)
# VERSION: 5.9.0
# =====================================================================
#!/usr/bin/env python3
"""Jabberwocky Scrubber (JWS v3.0) Package Initialization Anchor.

Governs structural package bindings, isolates component visibility, and 
exposes clean public APIs for multi-module synchronization loops.
"""

from __future__ import annotations

__version__ = "3.0.0"
__author__ = "Kinematicdigit (Jabberwocky Team)"

# Enforce clean namespace exposure across the verified layout
__all__ = [
    "SCRIPT_REVISION",
    "SCRIPT_REVISION_DATE",
    "IncludeNode",
    "scan",
    "Reporter",
    "sync_manifest_state",
    "apply_in_place_masking",
    "execute_workspace_sterilization",
    "prompt_sterilizer_safety_instructions",
]

# Lazy imports to decouple the bootstrap layer from heavy sub-modules.
from .jws_utils import SCRIPT_REVISION, SCRIPT_REVISION_DATE, IncludeNode

import importlib

def __getattr__(name: str):
    """Dynamically import sub‑modules on first attribute access.

    This keeps the package import lightweight and avoids pulling in
    optional heavy modules when only a subset of the API is required.
    """
    if name == "scan":
        return importlib.import_module(".jws_observer", __package__).scan
    if name == "sync_manifest_state":
        return importlib.import_module(".jws_state_manager", __package__).sync_manifest_state
    if name == "apply_in_place_masking":
        return importlib.import_module(".jws_operator", __package__).apply_in_place_masking
    if name == "Reporter":
        return importlib.import_module(".jws_reporter", __package__).Reporter
    if name == "execute_workspace_sterilization":
        return importlib.import_module(".jws_sterilizer", __package__).execute_workspace_sterilization
    if name == "prompt_sterilizer_safety_instructions":
        return importlib.import_module(".jws_sterilizer", __package__).prompt_sterilizer_safety_instructions
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
