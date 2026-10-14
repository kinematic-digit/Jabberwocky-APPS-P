# =====================================================================
# JWS DASHBOARD & REPORT RENDERER (jws_dashboard.py)
# VERSION: 5.9.0 [Inventory-Driven Dashboard + Evidence-Based Report]
# Location: scrubber/jws_dashboard.py
# =====================================================================
"""Builds jwt_macro_manager.conf from an Inventory and its findings.

Pure text generation: nothing here touches the printer configuration. Existing
checkbox values always win; only rows that are new to the dashboard receive a
default (0 when the entry is already switched off in the config, otherwise 1).
Hardware blocks are listed read-only (no checkbox).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .jws_analyzers import BLOCKER, INFO, WARNING, Finding, hardware_flags, macro_flags
from .jws_observer import Inventory
from .macro_manager import MacroManager, iter_dashboard_rows, macro_key_scope, normalize_component_key

BAR = "═" * 69
ACTION_LABELS = ("SNAPSHOT BACKUP", "SNAPSHOT RESTORE", "SWEEP TO QUARANTINE")
MANAGED_PREFIX = "jabberwocky_dist/"
# Tier routing is data: (tier index, substrings of the lowercase file name). Extend freely.
OPERATIONAL_HINTS = ("mainsail", "fluidd", "timelapse", "client")


@dataclass
class StateBook:
    """Resolves checkbox values: existing dashboard state wins over defaults."""

    existing: MacroManager
    keys: set[str] = field(default_factory=set)
    forced: dict[str, int] = field(default_factory=dict)

    def is_known(self, target_type: str, name: str, scope: str | None = None) -> bool:
        states = self.existing.states
        if normalize_component_key(target_type, name, scope) in states:
            return True
        if scope and normalize_component_key(target_type, name) in states:
            return True
        if target_type == "file" and "/" in name:
            return normalize_component_key("file", name.rsplit("/", 1)[-1]) in states
        return False

    def value(self, target_type: str, name: str, scope: str | None = None, default: int = 1) -> int:
        states = self.existing.states
        key = normalize_component_key(target_type, name, scope)
        self.keys.add(key)
        if key in self.forced:
            return self.forced[key]
        if key in states:
            return states[key]
        legacy = []
        if scope:
            legacy.append(normalize_component_key(target_type, name))
        if target_type == "file" and "/" in name:
            legacy.append(normalize_component_key("file", name.rsplit("/", 1)[-1]))
        for old in legacy:
            self.keys.add(old)
            if old in states:
                return states[old]
        return default


def file_states(inv: Inventory) -> dict[str, str]:
    """path -> active | masked | commented, derived from the include lines that reference it."""
    result: dict[str, str] = {}
    for ref in inv.includes:
        for child in ref.resolved:
            if ref.missing:
                continue
            prior = result.get(child)
            if prior == "active" or (prior and ref.state != "active"):
                continue
            result[child] = ref.state
    return result


def managed(inv: Inventory, path: str) -> bool:
    return inv.rel(path).startswith(MANAGED_PREFIX)


def plan_adoption(inv: Inventory, book: StateBook) -> list[tuple[str, str, str, str | None]]:
    """Plain-# entries in live files that the dashboard has never seen: (file, type, name, scope)."""
    plan = []
    states = file_states(inv)
    seen = set()
    for ref in inv.includes:
        if ref.state != "commented" or ref.missing or ref.is_glob:
            continue
        for child in ref.resolved:
            name = inv.rel(child)
            if states.get(child) == "commented" and not managed(inv, child) and not book.is_known("file", name):
                if (ref.parent, "file", name) not in seen:
                    seen.add((ref.parent, "file", name))
                    plan.append((ref.parent, "file", name, None))
    for macro in inv.macros:
        if macro.live and macro.state == "commented" and not managed(inv, macro.file):
            scope = inv.rel(macro.file)
            if not book.is_known("macro", macro.name, scope):
                key = (macro.file, "macro", macro.name.lower())
                if key not in seen:
                    seen.add(key)
                    plan.append((macro.file, "macro", macro.name, scope))
    return plan


def _tier(inv: Inventory, path: str, hardware_files: set[str]) -> int:
    low = inv.rel(path).lower()
    if path in hardware_files or path == str(inv.root_cfg):
        return 1
    if any(hint in low for hint in OPERATIONAL_HINTS):
        return 2
    return 3


def _hardware_section(inv: Inventory) -> str:
    flags = hardware_flags(inv)
    out = [BAR, " 🔩 SYSTEM CONTROLS: HARDWARE BLOCKS (REPORT ONLY — NO CHECKBOXES)", BAR,
           "  These define your real hardware. They are listed so you can spot duplicates and",
           "  overrides. The dashboard never switches them on or off.", ""]
    if not inv.hardware:
        out.append("  (no hardware blocks found in the active configuration)")
    for block in inv.hardware:
        flag = flags.get((block.file, block.section))
        badge, note = "    ", ""
        if flag:
            badge = "[H!] " if flag[0] == "!" else "[H?] "
            others = ", ".join(flag[1])
            note = (f" — ACTIVE OVERRIDE of: {others}" if flag[0] == "!" else f" — OVERRIDDEN by a later file (also in: {others})")
        out.append(f"  🔩 {badge}[{block.section}] ({block.kind}) in {inv.rel(block.file)}{note}")
    return "\n".join(out) + "\n\n"


def _macro_row(book, inv, mflags, path, macro_name, state, count) -> str:
    scope = inv.rel(path)
    default = 1 if state == "active" else 0
    value = book.value("macro", macro_name, scope, default)
    badge, note = "", ""
    flag = mflags.get((path, macro_name.lower()))
    if flag:
        if flag[0] == "!":
            badge = "[D!] "
            note = f" (🚀 ACTIVE RUNTIME OVERRIDE — Conflicts with: {', '.join(flag[1])})"
        else:
            badge = "[D?] "
            note = f" (🛑 OVERWRITTEN/INACTIVE — Active target resides in: {flag[1][-1]})"
    elif count > 1:
        badge, note = "[D?] ", " (🛑 INTERNAL DUPLICATE — defined more than once in this file)"
    if state != "active":
        note += " (💤 currently switched off)"
    return f"  ├── [ {value} ] ▶ {badge}{macro_name.upper()}{note}\n"


def _file_block(inv, book, mflags, path, states) -> str:
    rel = inv.rel(path)
    origin = inv.files[path]["origin"]
    include_state = "active" if path == str(inv.root_cfg) else states.get(path, "active")
    default = 1 if include_state == "active" else 0
    note = ""
    if path == str(inv.root_cfg):
        note = "  (ROOT FILE — always loaded)"
    elif include_state == "masked":
        note = "  (include is switched off by Jabberwocky)"
    elif include_state == "commented":
        note = "  (include was commented out with a plain #)"
    elif not inv.files[path]["live"]:
        note = "  (loaded only by a switched-off file)"
    value = book.value("file", rel, None, default)
    block = f"📂 EXTENSION SOURCE: {rel.upper()}{note}\n[ {value} ] 📂 {rel.upper()} (MASTER INCLUDE MAP)\n"

    per_name: dict[str, tuple[str, str, int]] = {}
    for macro in inv.macros:
        if macro.file != path:
            continue
        key = macro.name.lower()
        prev = per_name.get(key)
        state = macro.state if not prev or macro.state == "active" else prev[1]
        per_name[key] = (macro.name, state, (prev[2] if prev else 0) + (1 if macro.state == "active" else 0))
    for key in sorted(per_name):
        name, state, count = per_name[key]
        block += _macro_row(book, inv, mflags, path, name, state, count)
    return block + "\n"


def _findings_text(findings: list[Finding]) -> str:
    if not findings:
        return "  ➔ No findings. Nothing in this scan needs attention.\n"
    out = []
    titles = {BLOCKER: "🛑 BLOCKERS — Klipper cannot start until these are fixed",
              WARNING: "⚠️  WARNINGS — Klipper starts, but check these",
              INFO: "ℹ️  NOTES — informational"}
    for category in (BLOCKER, WARNING, INFO):
        group = [f for f in findings if f.category == category]
        if not group:
            continue
        out.append(f"\n{titles[category]}")
        for f in group:
            out.append(f"  • {f.title}")
            if f.detail:
                out.append(f"      Why: {f.detail}")
            if f.files and len(f.files) <= 8:
                out.append(f"      Files: {', '.join(f.files)}")
            elif f.files:
                out.append(f"      Files: {', '.join(f.files[:8])} … (+{len(f.files) - 8} more)")
            if f.remedy:
                out.append(f"      What to do: {f.remedy}")
    return "\n".join(out) + "\n"


def render(inv: Inventory, findings: list[Finding], book: StateBook, version: str, env_mode: str,
           hardware_metrics: dict, existing_lines=(), swept: int = 0) -> tuple[str, dict]:
    """Return (dashboard text, summary dict)."""
    mflags = macro_flags(inv)
    states = file_states(inv)
    hardware_files = {b.file for b in inv.hardware}

    actions = "".join(
        f"[ {book.value('action', label, None, 0)} ] ⚙️ SYSTEM ACTION: {label}\n" for label in ACTION_LABELS
    )

    tiers = {
        1: BAR + "\n ⚙️ TIER 1: SYSTEM ESSENTIALS (FILES THAT DEFINE YOUR HARDWARE)\n" + BAR + "\n",
        2: BAR + "\n 📋 TIER 2: OPERATIONAL ESSENTIALS (DASHBOARD UI INTERFACES & UTILITIES)\n" + BAR + "\n",
        3: BAR + "\n 📂 TIER 3: GENERAL DEFINITIONS (USER MACROS & OPTIONAL MODULES)\n" + BAR + "\n",
    }
    has_macro_file = {m.file for m in inv.macros}
    rows_written = 0
    for path in sorted(inv.files, key=lambda p: inv.rel(p).lower()):
        if managed(inv, path):
            continue
        is_root = path == str(inv.root_cfg)
        if is_root and path not in has_macro_file:
            continue
        if not is_root and path not in states and path not in has_macro_file:
            continue
        tiers[_tier(inv, path, hardware_files)] += _file_block(inv, book, mflags, path, states)
        rows_written += 1

    def _keep(key: str) -> bool:
        if key in book.keys:
            return False
        scope = macro_key_scope(key)
        # A stale macro under a file that is still listed would be re-scoped wrongly; drop it.
        return not (scope and normalize_component_key("file", scope) in book.keys)

    preserved = [line for line, parsed in iter_dashboard_rows(existing_lines) if parsed and _keep(parsed[0])]
    if preserved:
        tiers[3] += (
            BAR + "\n 📌 PRESERVED EXISTING DASHBOARD ENTRIES (not found in the current scan)\n" + BAR + "\n"
            + "".join(line if line.endswith("\n") else line + "\n" for line in preserved) + "\n"
        )

    counts = Counter(f.category for f in findings)
    summary = {
        "files": len(inv.files),
        "macros": len({(m.file, m.name.lower()) for m in inv.macros if m.state == "active"}),
        "blockers": counts[BLOCKER],
        "warnings": counts[WARNING],
        "notes": counts[INFO],
        "hardware": len(inv.hardware),
        "backups": len(inv.backups),
        "swept": swept,
        "rows": rows_written,
    }

    header = f"""=====================================================================
JABBERWOCKY APPS — MACRO MANAGER DASHBOARD & PRE-FLIGHT REPORT
Location: ~/printer_data/config/jwt_macro_manager.conf
VERSION: {version} [{env_mode}]
=====================================================================
HOW TO USE THIS PAGE:
  1. Find the file or macro you want to change in SECTION 1 below.
  2. Change the number in its brackets: 1 = ON, 0 = OFF.
     (Turning a file OFF only comments out its [include] line; the file is kept.
      Turning a macro OFF only hides it; the macro text is kept.)
  3. Flags: [D!] = this copy is the one Klipper uses, [D?] = a later file overrides it.
  4. Save, then run JABBERWOCKY_SYNC_NOW in the Mainsail console. It applies your
     changes and restarts Klipper. A plain restart also applies them.
     If that button is missing, run over SSH:
       python3 ~/Jabberwocky-APPS/scrubber/jws_core.py --sync
     then FIRMWARE_RESTART.
  Hardware blocks (stepper, extruder, mcu ...) are listed for your information only.
=====================================================================

"""
    text = (
        header
        + _hardware_section(inv)
        + BAR + "\n SECTION 1: INTERACTIVE EXTENSION DASHBOARD PANEL\n" + BAR + "\n\n"
        + actions + "\n"
        + tiers[1] + tiers[2] + tiers[3]
    )

    metrics = hardware_metrics
    report = (
        BAR + "\n SECTION 2: PRE-FLIGHT SCRUBBER REPORT (READ-ONLY FINDINGS)\n" + BAR + "\n"
        "🔍 SUMMARY:\n"
        f"  • Config files in the active tree : {len(inv.live_files())}\n"
        f"  • Files tracked in total          : {summary['files']}\n"
        f"  • Active macros                   : {summary['macros']}\n"
        f"  • Hardware blocks                 : {summary['hardware']}\n"
        f"  • Blockers / Warnings / Notes     : {summary['blockers']} / {summary['warnings']} / {summary['notes']}\n"
        f"  • Backup files in config folder   : {summary['backups']}\n"
        f"  • Files moved by the last sweep   : {swept}\n"
        + _findings_text(findings)
        + "\n🧪 EXTRUDER BASELINE (read from your config):\n"
        f"  • run_current: {metrics['run_current']}   stealthchop_threshold: {metrics['stealthchop']}   "
        f"rotation_distance: {metrics['rotation_dist']}\n"
        "\n🆘 IF KLIPPER WILL NOT START:\n"
        "  1. Open Mainsail's config editor (it still works) and read the error shown by Klipper.\n"
        "  2. Look at BLOCKERS above. Each one says which file and what to do.\n"
        "  3. Fix the include or macro, or run over SSH:\n"
        "       python3 ~/Jabberwocky-APPS/scrubber/jws_core.py --report   (read-only check)\n"
        "       python3 ~/Jabberwocky-APPS/scrubber/jws_core.py --sync     (apply dashboard)\n"
        "  4. Then press FIRMWARE RESTART. Backups are in the config folder and in\n"
        "     jabberwocky_quarantine/ (nothing is ever deleted).\n"
    )
    return text + report, summary
