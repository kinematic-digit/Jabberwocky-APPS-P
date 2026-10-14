#=-----------------------------------------------------------------------------
# JWS V3.0 GROUND-TRUTH ACTIVE TOGGLE STATE MANAGER (jws_state_manager.py)
#=-----------------------------------------------------------------------------
#!/usr/bin/env python3
"""Jabberwocky Scrubber (JWS v3.0) Ground-Truth Active Toggle State Manager.

Coordinates human-editable manifest sync loops, reads user-facing binary variables,
and automatically prunes ghost tracking states if physical assets are removed.
"""

from __future__ import annotations

import re
from pathlib import Path
from jws_utils import MANIFEST_SECTION_RE, MANIFEST_VAR_RE

def sync_manifest_state(state_cfg_path: Path, active_files: set[Path]) -> dict[str, int]:
    """Parses control manifest variables and auto-purges states matching missing physical files."""
    state_cfg_path = state_cfg_path.resolve()
    if not state_cfg_path.is_file():
        return {}

    try:
        lines = state_cfg_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    cleaned_lines: list[str] = []
    active_manifest_states: dict[str, int] = {}
    in_manifest_block = False
    modified = False

    # Extract clean file slugs from ground-truth verified active file path list
    verified_file_slugs = {f.name.lower().replace(".", "_") for f in active_files}

    for number, line in enumerate(lines, 1):
        stripped = line.strip()

        if MANIFEST_SECTION_RE.match(stripped):
            in_manifest_block = True
            cleaned_lines.append(line)
            continue

        if in_manifest_block and stripped.startswith("["):
            in_manifest_block = False

        if in_manifest_block:
            var_match = MANIFEST_VAR_RE.match(line)
            if var_match:
                var_type = var_match.group(1).lower()  # "file" or "macro"
                component_slug = var_match.group(2).lower()
                current_value = int(var_match.group(3))

                # GHOST VARIABLE PURGING: If file tracking tag is missing on metal, prune it
                if var_type == "file" and component_slug not in verified_file_slugs:
                    modified = True
                    continue  # Drops variable line out of file buffer arrays permanently

                active_manifest_states[f"{var_type}_{component_slug}"] = current_value
                cleaned_lines.append(line)
                continue

        cleaned_lines.append(line)

    if modified:
        try:
            state_cfg_path.write_text("\n".join(cleaned_lines) + "\n", encoding="utf-8")
        except OSError:
            pass

    return active_manifest_states
