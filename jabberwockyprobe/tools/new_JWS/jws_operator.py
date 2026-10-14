#=-----------------------------------------------------------------------------
# JWS V3.0 IN-PLACE COMMENT MASKING OPERATOR ENGINE (jws_operator.py)
#=-----------------------------------------------------------------------------
#!/usr/bin/env python3
"""Jabberwocky Scrubber (JWS v3.0) In-Place Comment Masking Operator."""

from __future__ import annotations
from pathlib import Path
from .jws_utils import MASK_TAG, MASK_START_TAG, MASK_END_TAG, INCLUDE_RE, MACRO_RE

def apply_in_place_masking(target_path: Path, toggle_states: dict[str, int], target_type: str = "file", component_name: str = "") -> bool:
    target_path = target_path.resolve()
    if not target_path.is_file(): return False
    try: lines = target_path.read_text(encoding="utf-8").splitlines()
    except OSError: return False

    key = f"{target_type}_{component_name.lower().replace('.', '_')}"
    desired_state = toggle_states.get(key, 1)
    output_lines: list[str] = []
    modified, idx, total_lines = False, 0, len(lines)

    if target_type == "file":
        while idx < total_lines:
            line = lines[idx]
            stripped = line.strip()
            
            # Guard against edge-case trailing commentary footnotes
            inc_match = INCLUDE_RE.match(line.split("#", 1)[0].split(";", 1)[0])
            is_target_include = inc_match and inc_match.group(1).strip().lower() == component_name.lower()
            is_masked_include = stripped == MASK_TAG and (idx + 2 < total_lines) and lines[idx + 2].strip().startswith("#[include")

            if desired_state == 0 and is_target_include:
                output_lines.extend(["# " + "-" * 78, f"# ⚠️ JWS ISOLATION: Masked by System.", f"# 👉 TO UNDO: Switch '{key}: 1' inside jws_state.cfg.", "# " + "-" * 78, MASK_TAG, "#" + line])
                modified, idx = True, idx + 1
                continue
            if desired_state == 1 and is_masked_include:
                if output_lines and output_lines[-1].startswith("# ---"):
                    while output_lines and output_lines[-1].startswith("#"): output_lines.pop()
                target_inc_line = lines[idx + 2]
                output_lines.append(target_inc_line[1:] if target_inc_line.startswith("#") else target_inc_line)
                modified, idx = True, idx + 3
                continue
            output_lines.append(line)
            idx += 1

    elif target_type == "macro":
        while idx < total_lines:
            line = lines[idx]
            stripped = line.strip()
            macro_match = MACRO_RE.match(line.split("#", 1)[0].split(";", 1)[0])
            is_target_macro = macro_match and macro_match.group(1).strip().lower() == component_name.lower()

            if desired_state == 0 and is_target_macro:
                output_lines.extend(["# " + "-" * 78, f"# ⚠️ JWS ISOLATION: Temporarily Commented Out.", "# " + "-" * 78, f"{MASK_START_TAG} {component_name.lower()}"])
                while idx < total_lines:
                    macro_line = lines[idx]
                    if macro_line.strip().startswith("[") and not is_target_macro: break
                    output_lines.append("#" + macro_line)
                    idx += 1
                output_lines.append(f"{MASK_END_TAG} {component_name.lower()}")
                modified = True
                continue
            if desired_state == 1 and stripped == f"{MASK_START_TAG} {component_name.lower()}":
                if output_lines and output_lines[-1].startswith("# ---"):
                    while output_lines and output_lines[-1].startswith("#"): output_lines.pop()
                idx += 1
                while idx < total_lines:
                    macro_line = lines[idx]
                    if macro_line.strip() == f"{MASK_END_TAG} {component_name.lower()}":
                        idx += 1
                        break
                    output_lines.append(macro_line[1:] if macro_line.startswith("#") else macro_line)
                    idx += 1
                modified = True
                continue
            output_lines.append(line)
            idx += 1

    if modified:
        try: target_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
        except OSError: return False
    return modified
