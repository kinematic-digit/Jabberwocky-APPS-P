# =====================================================================
# JWS V3.0 GROUND-TRUTH DASHBOARD INTERACTION LAYER (jws_state_manager.py)
# VERSION: 3.0.0
# =====================================================================
#!/usr/bin/env python3
"""Jabberwocky Scrubber (JWS v3.0) State Variable Verification Engine."""

from __future__ import annotations
from pathlib import Path
from .jws_utils import MANIFEST_SECTION_RE, MANIFEST_VAR_RE

def sync_manifest_state(state_cfg: Path, active_registry: dict[str, dict], config_dir: Path) -> dict[str, int]:
    """Prunes dead tracking keys and parses toggle manifest binary parameters."""
    state_cfg = state_cfg.resolve()
    toggle_states: dict[str, int] = {}
    if not state_cfg.is_file(): return toggle_states

    try: lines = state_cfg.read_text(encoding="utf-8").splitlines()
    except OSError: return toggle_states

    output_lines: list[str] = []
    in_manifest_section = False

    for line in lines:
        clean_line = line.split("#", 1)[0].split(";", 1)[0].strip()
        if MANIFEST_SECTION_RE.match(line):
            in_manifest_section = True
            output_lines.append(line)
            continue
        
        if in_manifest_section and clean_line.startswith("["):
            in_manifest_section = False

        var_match = MANIFEST_VAR_RE.match(line)
        if in_manifest_section and var_match:
            v_type, v_name, v_state = var_match.group(1), var_match.group(2), int(var_match.group(3))
            key = f"{v_type}_{v_name.lower()}"
            
            # Cross-reference dashboard visibility items directly against active crawler fields
            exists = False
            if v_type == "macro":
                exists = v_name.lower() in active_registry["macros"]
            elif v_type == "file":
                # Match shortened display path profiles safely
                exists = any(Path(p).name.lower().replace('.', '_') == v_name.lower() for p in active_registry["files"])

            if not exists:
                # Ghost variable pruning triggered. Skip writing this line to prune it.
                continue
            
            toggle_states[key] = v_state

        output_lines.append(line)

    try: state_cfg.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    except OSError: pass

    return toggle_states
