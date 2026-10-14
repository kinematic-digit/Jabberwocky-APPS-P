#=-----------------------------------------------------------------------------
# JWS V3.0 SYSTEM ARCHITECTURE CONSTANTS REPOSITORY (jws_utils.py)
#=-----------------------------------------------------------------------------
#!/usr/bin/env python3
"""Jabberwocky Scrubber (JWS v3.0) Constants & Shared Ruleset Repository.

Consolidates all system regular expressions, threshold boundaries, 
and token string patterns for the non-destructive In-Place Paradigm.
"""

from __future__ import annotations

import re
from pathlib import Path

# Script Identity Metadata
SCRIPT_REVISION = "v3.0.0"
SCRIPT_REVISION_DATE = "2026-09-21"
SCRIPT_AUTHOR = "Kinematicdigit (Jabberwocky Team)"
SCRIPT_PROJECT_URL = "https://github.com"

# In-Place Masking Identifiers & Signatures
MASK_TAG = "#-hidden-##"
MASK_START_TAG = "#-hidden-##-start-"
MASK_END_TAG = "#-hidden-##-end-"

# Core Configuration Scanning Regex Patterns
SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[#;].*)?$")
INCLUDE_RE = re.compile(r"^\s*\[include\s+([^\]]+)\]\s*(?:[#;].*)?$", re.I)
OPTION_RE = re.compile(r"^\s*([A-Za-z_][\w-]*)\s*:")
MACRO_RE = re.compile(r"^\s*\[gcode_macro\s+([^\]]+)\]\s*$", re.I)
RENAME_RE = re.compile(r"^\s*rename_existing\s*:\s*(\S+)", re.I)

# Specialized JWS Component Manifest Parsing Patterns
MANIFEST_SECTION_RE = re.compile(r"^\s*\[gcode_macro\s+_JWS_TOGGLE_MANIFEST\]\s*$", re.I)
MANIFEST_VAR_RE = re.compile(r"^\s*variable_(file|macro)_([A-Za-z0-9_]+)\s*:\s*([01])", re.I)

# Hardware Configuration Threshold Boundaries
TMC_MAX_REASONABLE_CURRENT = 6.0
PID_PLACEHOLDER_VALUES = {"pid_kp": 1.0, "pid_ki": 0.5, "pid_kd": 2.0}

class IncludeNode:
    """Represents a discrete file node within the recursive [include] tree."""
    def __init__(self, path: Path, raw_pattern: str = ""):
        self.path = path
        self.raw_pattern = raw_pattern
        self.children: list[IncludeNode] = []

def short_display_path(path: Path, config_dir: Path) -> str:
    """Shortens long user system paths relative to the active config root."""
    try:
        rel = path.resolve().relative_to(config_dir.resolve())
        return str(Path(config_dir.name) / rel)
    except (ValueError, RuntimeError):
        return str(path)
