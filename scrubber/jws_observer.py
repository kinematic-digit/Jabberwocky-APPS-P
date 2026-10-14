# =====================================================================
# JWS RECURSIVE TREE CRAWLER AND INVENTORY OBSERVER (jws_observer.py)
# VERSION: 5.9.0 [Klipper-Order Inventory Crawler]
# Location: scrubber/jws_observer.py
# =====================================================================
#!/usr/bin/env python3
"""Passive, read-only crawler.

``build_inventory`` walks the include tree exactly the way Klipper loads it
(includes resolve relative to the including file, expanded in place, in text
order) and records every include, macro and hardware block together with its
state: ``active``, ``masked`` (Jabberwocky ``#💤#``) or ``commented`` (plain
user ``#``).  Nothing here ever writes to disk.
"""

from __future__ import annotations

import glob as _glob
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .jws_utils import (
    BACKUP_NAME_RE,
    HARDWARE_RES,
    MANAGED_DIR_NAMES,
    MASK_TAG,
    IncludeNode,
)

INCLUDE_LINE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<mask>#💤#|#+)?[ \t]*\[[ \t]*include[ \t]+(?P<target>[^\]\s]+)[ \t]*\](?P<tail>.*)$",
    re.I,
)
MACRO_LINE = re.compile(
    r"^[ \t]*(?P<mask>#💤#|#+)?[ \t]*\[[ \t]*gcode_macro[ \t]+(?P<name>[^\]\s]+)[ \t]*\](?P<tail>.*)$",
    re.I,
)
SECTION_HEADER = re.compile(r"^\[(?P<name>[^\]]+)\]")


def _tail_is_comment(tail: str) -> bool:
    stripped = tail.strip()
    return not stripped or stripped[0] in "#;"


@dataclass
class IncludeRef:
    parent: str
    line_no: int
    target: str
    state: str  # active | masked | commented
    resolved: list[str] = field(default_factory=list)
    missing: bool = False
    is_glob: bool = False


@dataclass
class MacroDef:
    name: str
    file: str
    line_no: int
    state: str  # active | masked | commented
    order: int
    live: bool


@dataclass
class HardwareBlock:
    section: str
    kind: str
    owner: str
    file: str
    line_no: int
    order: int
    live: bool


@dataclass
class Inventory:
    config_dir: Path
    root_cfg: Path
    files: dict[str, dict] = field(default_factory=dict)  # path -> {"live": bool}
    texts: dict[str, str] = field(default_factory=dict)
    includes: list[IncludeRef] = field(default_factory=list)
    macros: list[MacroDef] = field(default_factory=list)
    hardware: list[HardwareBlock] = field(default_factory=list)
    physical: list[str] = field(default_factory=list)
    backups: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def rel(self, path: str | Path) -> str:
        """Dashboard identity of a file: path relative to the config dir, '/' separated."""
        try:
            return os.path.relpath(str(path), str(self.config_dir)).replace(os.sep, "/")
        except ValueError:
            return str(path)

    def live_files(self) -> list[str]:
        return [p for p, meta in self.files.items() if meta["live"]]


def _resolve_include(parent: Path, target: str) -> tuple[list[str], bool, bool]:
    """Return (existing files, is_glob, missing) following Klipper's include rules."""
    spec = os.path.join(str(parent.parent), target)
    is_glob = _glob.has_magic(spec)
    matches = sorted(_glob.glob(spec))
    resolved = [str(Path(m).resolve()) for m in matches if os.path.isfile(m)]
    missing = not resolved and not is_glob
    if missing:
        resolved = [str(Path(os.path.normpath(spec)))]
    return resolved, is_glob, missing


def _discover_physical(config_dir: Path, inv: Inventory) -> None:
    for root, dirs, names in os.walk(config_dir):
        dirs[:] = sorted(d for d in dirs if d not in MANAGED_DIR_NAMES and not d.startswith("."))
        for name in sorted(names):
            if BACKUP_NAME_RE.search(name):
                inv.backups.append(str(Path(root, name).resolve()))
            elif name.endswith((".cfg", ".conf")):
                inv.physical.append(str(Path(root, name).resolve()))


def build_inventory(root_cfg: Path, config_dir: Path) -> Inventory:
    config_dir = Path(config_dir).resolve()
    root_cfg = Path(root_cfg).resolve()
    inv = Inventory(config_dir=config_dir, root_cfg=root_cfg)
    counter = [0]
    visited: set[str] = set()

    def crawl(path_str: str, live: bool, follow_states: tuple[str, ...], origin: str = "live") -> None:
        if path_str in visited:
            return
        path = Path(path_str)
        if not path.is_file():
            return
        visited.add(path_str)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            inv.warnings.append(f"Could not open config resource target: {path.name}")
            return
        inv.files[path_str] = {"live": live, "origin": origin}
        inv.texts[path_str] = text

        for line_no, line in enumerate(text.splitlines(), start=1):
            inc = INCLUDE_LINE.match(line)
            if inc:
                mask = inc.group("mask")
                if not mask:
                    state = "active"
                elif mask == MASK_TAG:
                    state = "masked"
                elif _tail_is_comment(inc.group("tail")):
                    state = "commented"
                else:
                    continue  # prose such as "# [include x] some words" is user text
                resolved, is_glob, missing = _resolve_include(path, inc.group("target"))
                if live:
                    inv.includes.append(
                        IncludeRef(path_str, line_no, inc.group("target"), state, resolved, missing, is_glob)
                    )
                if state in follow_states and not missing:
                    for child in resolved:
                        crawl(child, live and state == "active", follow_states, origin)
                continue

            mac = MACRO_LINE.match(line)
            if mac:
                mask = mac.group("mask")
                if not mask:
                    state = "active"
                elif mask == MASK_TAG:
                    state = "masked"
                elif _tail_is_comment(mac.group("tail")):
                    state = "commented"
                else:
                    continue
                counter[0] += 1
                inv.macros.append(MacroDef(mac.group("name"), path_str, line_no, state, counter[0], live))
                continue

            header = SECTION_HEADER.match(line)
            if header and live:
                name = " ".join(header.group("name").split()).lower()
                for regex, kind in HARDWARE_RES:
                    hit = regex.match(name)
                    if hit:
                        counter[0] += 1
                        owner = hit.groupdict().get("owner") or name
                        inv.hardware.append(
                            HardwareBlock(name, kind, owner, path_str, line_no, counter[0], True)
                        )
                        break

    crawl(str(root_cfg), True, ("active",))
    # Second pass: files reachable only through disarmed includes, so their rows stay manageable.
    for ref in list(inv.includes):
        if ref.state in ("masked", "commented") and not ref.missing:
            for child in ref.resolved:
                crawl(child, False, ("active", "masked", "commented"), ref.state)

    _discover_physical(config_dir, inv)
    return inv


def scan(root_cfg: Path, config_dir: Path) -> tuple[IncludeNode, dict[str, dict], list[str]]:
    """Backward-compatible registry view used by the sync loop and older callers."""
    inv = build_inventory(root_cfg, config_dir)
    registry_map: dict[str, dict] = {"macros": {}, "files": {}, "orphaned_files": [], "orphaned_includes": []}
    for path, meta in inv.files.items():
        if meta["origin"] != "commented":
            registry_map["files"][path] = {"macros": []}
    for macro in inv.macros:
        if macro.state == "active" and macro.file in registry_map["files"]:
            registry_map["files"][macro.file]["macros"].append(macro.name)
            registry_map["macros"].setdefault(macro.name, macro.file)
    for ref in inv.includes:
        if ref.missing and ref.state == "active":
            registry_map["orphaned_includes"].append(ref.resolved[0])
    tracked = set(inv.files)  # commented-only targets are never orphans here
    for path in inv.physical:
        if path not in tracked and Path(path).name not in ("jwt_macro_manager.conf", "jwt_macro_manager.cfg"):
            registry_map["orphaned_files"].append(path)

    root_node = IncludeNode(str(inv.root_cfg))
    nodes = {str(inv.root_cfg): root_node}
    for ref in inv.includes:
        parent = nodes.get(ref.parent)
        if parent is None:
            continue
        for child in ref.resolved:
            node = IncludeNode(child, parent=parent)
            parent.children.append(node)
            nodes.setdefault(child, node)
    return root_node, registry_map, inv.warnings
#EOF
