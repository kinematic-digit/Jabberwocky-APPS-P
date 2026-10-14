# =====================================================================
# JWS ANALYZER REGISTRY (jws_analyzers.py)
# VERSION: 5.9.0 [Pluggable Hygiene Checks]
# Location: scrubber/jws_analyzers.py
# =====================================================================
"""Read-only hygiene checks over an Inventory.

Add a new check by writing a function decorated with ``@analyzer`` that takes
an ``Inventory`` and returns a list of ``Finding``.  Nothing else needs to change.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .jws_observer import Inventory
from .jws_utils import MANAGED_DIR_NAMES

BLOCKER, WARNING, INFO = "BLOCKER", "WARNING", "INFO"


@dataclass
class Finding:
    category: str  # BLOCKER | WARNING | INFO
    code: str
    title: str
    detail: str = ""
    files: list[str] = field(default_factory=list)
    remedy: str = ""


_ANALYZERS: list[Callable[[Inventory], list[Finding]]] = []


def analyzer(func):
    _ANALYZERS.append(func)
    return func


def run_all(inv: Inventory) -> list[Finding]:
    findings: list[Finding] = []
    for func in _ANALYZERS:
        findings.extend(func(inv))
    order = {BLOCKER: 0, WARNING: 1, INFO: 2}
    return sorted(findings, key=lambda f: (order.get(f.category, 9), f.code))


def live_macro_defs(inv: Inventory):
    """Active macro definitions in live files, grouped by lowercase name, in load order."""
    groups: dict[str, list] = defaultdict(list)
    for macro in inv.macros:
        if macro.live and macro.state == "active":
            groups[macro.name.lower()].append(macro)
    return groups


def macro_flags(inv: Inventory) -> dict[tuple[str, str], tuple[str, list[str]]]:
    """Map (file, lowercase macro) -> ('!'|'?', other files). '!' is the definition Klipper keeps."""
    flags: dict[tuple[str, str], tuple[str, list[str]]] = {}
    for name, defs in live_macro_defs(inv).items():
        files = list(dict.fromkeys(d.file for d in defs))
        if len(files) < 2:
            continue
        winner = defs[-1].file
        for file in files:
            others = [inv.rel(f) for f in files if f != file]
            flags[(file, name)] = ("!" if file == winner else "?", others)
    return flags


def hardware_flags(inv: Inventory) -> dict[tuple[str, str], tuple[str, list[str]]]:
    groups: dict[str, list] = defaultdict(list)
    for block in inv.hardware:
        if block.live:
            groups[block.section].append(block)
    flags: dict[tuple[str, str], tuple[str, list[str]]] = {}
    for section, blocks in groups.items():
        files = list(dict.fromkeys(b.file for b in blocks))
        if len(files) < 2:
            continue
        for file in files:
            others = [inv.rel(f) for f in files if f != file]
            flags[(file, section)] = ("!" if file == files[-1] else "?", others)
    return flags


@analyzer
def missing_root(inv: Inventory) -> list[Finding]:
    if inv.root_cfg.is_file():
        return []
    return [Finding(BLOCKER, "ROOT_MISSING", "printer.cfg was not found",
                    str(inv.root_cfg), [], "Restore printer.cfg from a backup; Klipper cannot start without it.")]


@analyzer
def missing_includes(inv: Inventory) -> list[Finding]:
    out = []
    for ref in inv.includes:
        if ref.state == "active" and ref.missing:
            out.append(Finding(
                BLOCKER, "INCLUDE_MISSING",
                f"[include {ref.target}] points to a file that does not exist",
                f"Line {ref.line_no} of {inv.rel(ref.parent)}. Klipper refuses to start with this line.",
                [inv.rel(ref.parent)],
                f"Put the file back, or disable the line: open {inv.rel(ref.parent)} and add a # in front of it "
                f"(or untick it in the dashboard and run --sync over SSH).",
            ))
    return out


@analyzer
def duplicate_macros(inv: Inventory) -> list[Finding]:
    out = []
    for name, defs in sorted(live_macro_defs(inv).items()):
        files = list(dict.fromkeys(d.file for d in defs))
        if len(files) > 1:
            out.append(Finding(
                WARNING, "MACRO_DUPLICATE",
                f"Macro {defs[0].name} is defined in {len(files)} files",
                f"Klipper merges them; the last one loaded ({inv.rel(files[-1])}) wins.",
                [inv.rel(f) for f in files],
                "Keep one definition: untick the macro in the dashboard for the copy you do not want.",
            ))
    return out


@analyzer
def duplicate_hardware(inv: Inventory) -> list[Finding]:
    out = []
    for (file, section), (flag, others) in sorted(hardware_flags(inv).items(), key=lambda kv: kv[0][1]):
        if flag == "!":
            out.append(Finding(
                WARNING, "HARDWARE_DUPLICATE",
                f"[{section}] is defined in more than one file",
                f"Options from {inv.rel(file)} override earlier copies in: {', '.join(others)}.",
                [inv.rel(file)] + others,
                "Check that the values you expect are the ones in the last-loaded file. Hardware blocks are report-only.",
            ))
    return out


def _referenced_names(inv: Inventory) -> str:
    return "\n".join(text for path, text in inv.texts.items())


@analyzer
def unloaded_files(inv: Inventory) -> list[Finding]:
    """Config files not in the live tree. Separated into disarmed, mentioned and complete orphans."""
    out = []
    live = set(inv.live_files())
    corpus = _referenced_names(inv).lower()
    for path in inv.physical:
        if path in live:
            continue
        p = Path(path)
        rel = inv.rel(path)
        if any(part in MANAGED_DIR_NAMES for part in Path(rel).parts):
            continue
        if p.name.lower().startswith("jwt_macro_manager"):
            continue
        if path in inv.files:
            out.append(Finding(INFO, "FILE_DISARMED", f"{rel} is switched off",
                               "Its include line is masked or commented, so Klipper ignores it.", [rel],
                               "Tick its row in the dashboard to bring it back."))
        elif p.name.lower() in corpus:
            out.append(Finding(INFO, "FILE_UNLOADED", f"{rel} is mentioned but not loaded",
                               "Another file references this name, but no active [include] loads it.", [rel],
                               "Add an [include] if you want it, otherwise leave it."))
        else:
            out.append(Finding(WARNING, "FILE_ORPHAN", f"{rel} is a complete orphan",
                               "No file includes it or mentions it.", [rel],
                               "Review it. It can be moved to quarantine with the guarded sweep action."))
    return out


@analyzer
def backups(inv: Inventory) -> list[Finding]:
    if not inv.backups:
        return []
    rels = [inv.rel(b) for b in inv.backups]
    return [Finding(INFO, "BACKUPS", f"{len(rels)} backup file(s) found in the config folder",
                    "Backups are ignored by Klipper but clutter the Mainsail editor.", rels,
                    "Optional: turn the quarantine sweep action to 1 and re-run the installer to move them aside (never deleted).")]


@analyzer
def disarmed_summary(inv: Inventory) -> list[Finding]:
    out = []
    for ref in inv.includes:
        if ref.state != "active" and ref.missing and not ref.is_glob:
            out.append(Finding(WARNING, "COMMENTED_MISSING",
                               f"Disabled include '{ref.target}' has no file behind it",
                               f"Line {ref.line_no} of {inv.rel(ref.parent)} is switched off and no such file exists.",
                               [inv.rel(ref.parent)],
                               "Delete the line, or restore/rename the file and re-enable it. "
                               "Report only; no dashboard row is created."))
    return out
