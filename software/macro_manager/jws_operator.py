# =====================================================================
# JWS SYSTEM MASKING OPERATOR UTILITY LAYER (jws_operator.py)
# VERSION: 5.9.0 [Plain-# Adoption + Resolved-Path Include Matching]
# Location: software/macro_manager/jws_operator.py
# =====================================================================
#!/usr/bin/env python3
"""Jabberwocky Scrubber structural text in-place masking engine.

Masking is always non-destructive: an include line or a whole macro block is
prefixed with ``#💤#`` and can be restored. A plain ``#`` written by the user is
adopted into the managed mask (target 0) or restored (target 1: the dashboard
wins).
"""

from __future__ import annotations
import glob
import os
import re
import sys
from pathlib import Path

from .macro_manager import normalize_component_key
from .jws_utils import (
    MASK_TAG,
    MASK_START_TAG,
    MASK_END_TAG,
    MASK_NOTE_PREFIX,
    MASK_REENABLE_NOTE,
    MACRO_RE,
)

INCLUDE_LINE_RE = re.compile(
    r"^(?P<indent>\s*)(?P<mask>#💤#|#+)?(?P<space>[ \t]*)"
    r"(?P<include>\[\s*include\s+(?P<target>\S+)\s*\])(?P<tail>.*)$",
    re.I,
)
PLAIN_MACRO_HEADER_RE = re.compile(
    r"^(?P<indent>\s*)#+\s*\[\s*gcode_macro\s+(?P<name>[^\]\s]+)\s*\](?P<tail>.*)$", re.I
)
COMMENTED_SECTION_RE = re.compile(r"^\s*#+\s*\[")
SECTION_LINE_RE = re.compile(r"^\[[^\]]+\]")
JWP_INSTALLER_OWNED_INCLUDES = {
    "jwprobe_entry.cfg",
    "jwprobe_qgl.cfg",
    "jwprobe_bed_mesh.cfg",
}
JWP_INSTALLER_OWNED_MACRO_FILES = {
    "jwprobe_qgl.cfg",
    "jwprobe_bed_mesh.cfg",
}


def _tail_is_comment(tail: str) -> bool:
    stripped = tail.strip()
    return not stripped or stripped[0] in "#;"


def _include_state(match: re.Match) -> str | None:
    """active | managed | plain, or None when the line is prose rather than an include."""
    mask = match.group("mask")
    if not mask:
        return "active"
    if mask == MASK_TAG:
        return "managed"
    return "plain" if _tail_is_comment(match.group("tail")) else None


def _include_matches(file_path: Path, target: str, component_name: str, config_dir: Path | None) -> bool:
    if glob.has_magic(target):
        return False
    if config_dir is None:
        return target.lower() == component_name.lower()
    resolved = os.path.realpath(os.path.join(str(file_path.parent), target)).lower()
    wanted = os.path.realpath(os.path.join(str(config_dir), component_name)).lower()
    return resolved == wanted


def _is_jwp_installer_owned_file(file_path: Path, name: str, config_dir: Path | None) -> bool:
    if config_dir is None:
        return False
    expected = os.path.realpath(
        os.path.join(str(config_dir), "jabberwockyprobe", name)
    )
    return os.path.realpath(file_path) == expected


def _is_jwp_installer_owned_include(
    file_path: Path, target: str, config_dir: Path | None
) -> bool:
    if config_dir is None:
        return False
    normalized = target.replace("\\", "/")
    name = Path(normalized).name.lower()
    if name not in JWP_INSTALLER_OWNED_INCLUDES:
        return False
    resolved_target = os.path.realpath(file_path.parent / normalized)
    expected = os.path.realpath(
        os.path.join(str(config_dir), "jabberwockyprobe", name)
    )
    return resolved_target == expected


def _collect_plain_block(lines: list[str], start: int) -> int:
    """Index just past a user-commented macro block starting at ``start``."""
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if not line.strip() or not line.lstrip().startswith("#"):
            break
        if line.lstrip().startswith(MASK_TAG) or COMMENTED_SECTION_RE.match(line):
            break
        end += 1
    return end


def _strip_one_hash(line: str) -> str:
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]
    return indent + stripped[1:] if stripped.startswith("#") else line


def _mask_block(name: str, block: list[str]) -> list[str]:
    key = name.lower().strip()
    return [f"{MASK_START_TAG} {key}", MASK_REENABLE_NOTE.replace("this macro's", f"{name}'s")] + \
        [f"{MASK_TAG}{line}" for line in block] + [f"{MASK_END_TAG} {key}"]


def _apply_include(lines, file_path, component_name, desired, config_dir, adopt_only):
    matches = []
    for idx, line in enumerate(lines):
        m = INCLUDE_LINE_RE.match(line)
        if (
            m
            and not _is_jwp_installer_owned_include(file_path, m.group("target"), config_dir)
            and _include_matches(file_path, m.group("target"), component_name, config_dir)
        ):
            state = _include_state(m)
            if state:
                matches.append((idx, m, state))
    has_active = any(state == "active" for _, _, state in matches)
    out = list(lines)
    changed = False
    for idx, m, state in matches:
        body = f"{m.group('space')}{m.group('include')}{m.group('tail')}"
        if desired == 0 and state in ("active", "plain"):
            if adopt_only and state == "active":
                continue
            out[idx] = f"{m.group('indent')}{MASK_TAG}{body}"
            changed = True
        elif desired == 1 and state in ("managed", "plain") and not adopt_only and not has_active:
            out[idx] = f"{m.group('indent')}{body}"
            changed = True
    return out, changed


def _apply_macro(lines, component_name, desired, adopt_only):
    name_key = component_name.lower().strip()
    start_marker = f"{MASK_START_TAG} {name_key}"
    end_marker = f"{MASK_END_TAG} {name_key}"
    has_active = any(
        (m := MACRO_RE.match(line)) and m.group(1).strip().lower() == name_key for line in lines
    )
    out: list[str] = []
    changed = False
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped == start_marker:
            close = index + 1
            while close < len(lines) and lines[close].strip() != end_marker:
                close += 1
            block = lines[index + 1 : close]
            if desired == 1 and not adopt_only and not has_active:
                for item in block:
                    if item.startswith(MASK_NOTE_PREFIX):
                        continue
                    out.append(item[len(MASK_TAG):] if item.startswith(MASK_TAG) else item)
                changed = True
                if close + 1 < len(lines) and not lines[close + 1].strip():
                    close += 1  # drop the spacer added when the block was masked
            else:
                out.extend(lines[index : min(close + 1, len(lines))])
            index = close + 1
            continue

        macro_match = MACRO_RE.match(line)
        if macro_match and macro_match.group(1).strip().lower() == name_key:
            if desired == 0 and not adopt_only:
                end = index + 1
                while end < len(lines) and not SECTION_LINE_RE.match(lines[end]) \
                        and not lines[end].strip().startswith(MASK_START_TAG):
                    end += 1
                out.extend(_mask_block(component_name, lines[index:end]))
                if end < len(lines) and lines[end].strip():
                    out.append("")
                changed = True
                index = end
                continue

        plain = PLAIN_MACRO_HEADER_RE.match(line)
        if (
            plain
            and plain.group("name").strip().lower() == name_key
            and _tail_is_comment(plain.group("tail"))
            and not line.lstrip().startswith(MASK_TAG)
        ):
            end = _collect_plain_block(lines, index)
            block = lines[index:end]
            if desired == 0:
                out.extend(_mask_block(component_name, [_strip_one_hash(b) for b in block]))
                if end < len(lines) and lines[end].strip():
                    out.append("")
                changed = True
                index = end
                continue
            if desired == 1 and not adopt_only and not has_active:
                out.extend(_strip_one_hash(b) for b in block)
                changed = True
                index = end
                continue

        out.append(line)
        index += 1
    return out, changed


def apply_in_place_masking(
    file_path: Path,
    toggle_manifest: dict,
    target_type: str,
    component_name: str,
    scope: str | None = None,
    config_dir: Path | None = None,
    adopt_only: bool = False,
) -> bool:
    """Mask or restore one include or macro while preserving surrounding text.

    ``adopt_only`` limits the change to converting a user's plain ``#`` into the
    managed mask; it never unmasks and never disables a live entry.
    """
    if not file_path.is_file():
        return False

    lookup_key = normalize_component_key(target_type, component_name, scope)
    raw_payload = toggle_manifest.get(lookup_key, 1)
    if type(raw_payload) not in (int, bool) or raw_payload not in (0, 1):
        raise ValueError(f"Invalid dashboard value for {lookup_key}: {raw_payload!r}")
    desired_state = int(raw_payload)

    try:
        if target_type == "macro" and any(
            file_path.name.lower() == name
            and _is_jwp_installer_owned_file(file_path, name, config_dir)
            for name in JWP_INSTALLER_OWNED_MACRO_FILES
        ):
            return False
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if target_type == "file":
            output, modified = _apply_include(lines, file_path, component_name, desired_state, config_dir, adopt_only)
        elif target_type == "macro":
            output, modified = _apply_macro(lines, component_name, desired_state, adopt_only)
        else:
            return False

        if modified:
            file_path.write_text("\n".join(output) + "\n", encoding="utf-8")
            return True
    except OSError as e:
        print(f"[ERROR] Unable to write file update to {file_path}: {e}", file=sys.stderr)

    return False
#EOF
