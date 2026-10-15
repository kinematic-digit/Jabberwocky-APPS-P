# =====================================================================
# JWS SYSTEM CORE RUN-LOOP ORCHESTRATOR (jws_core.py)
# VERSION: 5.9.1 [Read-Only Report Independent of Dashboard and Root File]
# Location: software/macro_manager/jws_core.py
# =====================================================================
#!/usr/bin/env python3
"""Jabberwocky Scrubber central orchestration engine.

Modes:
  (default)   audit only: prints dashboard state, changes nothing
  --report    read-only inventory and findings, safe when Klipper is down
  --sync      apply dashboard toggles to the config files
  --restart-if-changed
              with --sync: request firmware restart only if a file changed
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.request
from pathlib import Path

CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_SCRIPT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BUILD_VERSION = "5.9.1"
RESTART_LOCK_NAME = ".jws_sync_lock"
RESTART_COOLDOWN_SECONDS = 120

from software.macro_manager.jws_observer import build_inventory, scan
from software.macro_manager.jws_operator import apply_in_place_masking
from software.macro_manager.jws_analyzers import run_all
from software.macro_manager.jws_dashboard import _findings_text
from software.macro_manager.macro_manager import (
    MacroManager,
    decode_component_key,
    macro_key_scope,
)


def parse_visual_checkboxes(manager_path: Path) -> dict[str, int]:
    """Compatibility wrapper around the shared dashboard state contract."""
    return MacroManager(manager_path).states


def request_restart(moonraker_url: str, timeout: float = 10.0) -> bool:
    """Ask Moonraker to restart Klipper firmware. Return True on HTTP success."""
    req = urllib.request.Request(
        moonraker_url.rstrip("/") + "/printer/firmware_restart",
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return 200 <= resp.status < 300


def _restart_allowed(config_dir: Path) -> bool:
    lock = config_dir / RESTART_LOCK_NAME
    try:
        return time.time() - lock.stat().st_mtime > RESTART_COOLDOWN_SECONDS
    except OSError:
        return True


def _resolve_config_dir(cli_value: str | None) -> Path:
    """Resolve the config directory from CLI, environment, or default."""
    if cli_value:
        return Path(os.path.expanduser(cli_value)).resolve()

    env_value = os.getenv("PRINTER_CONFIG_DIR")
    if env_value:
        return Path(os.path.expanduser(env_value)).resolve()

    return Path(os.path.expanduser("~/printer_data/config")).resolve()


def run_report(config_dir: Path, root_cfg: Path) -> int:
    """Print read-only findings without requiring printer.cfg or dashboard state."""
    print("\n📡 =================== JWS RUNTIME MANIFEST AUDIT ===================")
    print(f"  • Build              : {BUILD_VERSION} (REPORT)")
    print(f"  • Config Base Path   : {config_dir}")
    print("  • Dashboard entries  : not read (read-only report)")
    print("===================================================================\n")

    try:
        inventory = build_inventory(root_cfg, config_dir)
        findings = run_all(inventory)
    except Exception as exc:
        print(
            f"❌ Diagnostic report failed: {exc}",
            file=sys.stderr,
        )
        return 2

    print(
        f"Files in active tree: {len(inventory.live_files())}   "
        f"Macros: {len(inventory.macros)}   "
        f"Hardware blocks: {len(inventory.hardware)}"
    )
    print(_findings_text(findings))
    return 0


def run_sync(
    config_dir: Path,
    root_cfg: Path,
    toggle_manifest: dict,
) -> list[str]:
    """Apply dashboard toggles. Return one line per modified entry."""
    changes: list[str] = []
    inventory = build_inventory(root_cfg, config_dir)
    targets = [
        Path(path)
        for path, meta in inventory.files.items()
        if meta["origin"] != "commented"
    ]

    for key in toggle_manifest:
        target_type, name = decode_component_key(key)
        if target_type != "file":
            continue

        for path in targets:
            if apply_in_place_masking(
                path,
                toggle_manifest,
                "file",
                name.lower(),
                config_dir=config_dir,
            ):
                changes.append(
                    f"include {name} -> "
                    f"{'ON' if toggle_manifest[key] else 'OFF'} "
                    f"in {inventory.rel(path)}"
                )

    # Re-read the tree because toggling an include can reveal or hide files.
    inventory = build_inventory(root_cfg, config_dir)
    targets = [
        Path(path)
        for path, meta in inventory.files.items()
        if meta["origin"] != "commented"
    ]

    for key in toggle_manifest:
        target_type, name = decode_component_key(key)
        if target_type != "macro":
            continue

        scope = macro_key_scope(key)
        for path in targets:
            if scope and scope not in (
                inventory.rel(path).lower(),
                path.name.lower(),
            ):
                continue

            if apply_in_place_masking(
                path,
                toggle_manifest,
                "macro",
                name,
                scope,
                config_dir=config_dir,
            ):
                changes.append(
                    f"macro {name} -> "
                    f"{'ON' if toggle_manifest[key] else 'OFF'} "
                    f"in {inventory.rel(path)}"
                )

    return changes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="JWS Central Sync Loop",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Apply browser dashboard toggles to config files",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Read-only scan and findings; works when Klipper is down",
    )
    parser.add_argument(
        "--config-dir",
        help="Klipper config folder (default: ~/printer_data/config)",
    )
    parser.add_argument(
        "--restart-if-changed",
        action="store_true",
        help="With --sync: restart firmware only if files changed",
    )
    parser.add_argument(
        "--moonraker-url",
        default=os.getenv(
            "JWS_MOONRAKER_URL",
            "http://127.0.0.1:7125",
        ),
    )
    args = parser.parse_args(argv)

    config_dir = _resolve_config_dir(args.config_dir)
    root_cfg = config_dir / "printer.cfg"

    # Report mode must run before the root-file check and must not load
    # dashboard state. This allows the report to diagnose a missing root
    # file or a broken dashboard without attempting any repair or sync.
    if args.report:
        return run_report(config_dir, root_cfg)

    if not root_cfg.is_file():
        print(
            f"❌ Critical Error: Master target config missing at {root_cfg}",
            file=sys.stderr,
        )
        return 1

    manager_cfg = config_dir / "jwt_macro_manager.conf"
    manager = MacroManager(manager_cfg)
    toggle_manifest = dict(manager.states)

    mode = "SYNC" if args.sync else "AUDIT ONLY, no files changed; use --sync"
    print("\n📡 =================== JWS RUNTIME MANIFEST AUDIT ===================")
    print(f"  • Build              : {BUILD_VERSION} ({mode})")
    print(f"  • Config Base Path   : {config_dir}")
    print(f"  • Dashboard entries  : {len(toggle_manifest)}")
    print("===================================================================\n")

    if not args.sync:
        return 0

    changes = run_sync(config_dir, root_cfg, toggle_manifest)
    for line in changes:
        print(f"  ✎ {line}")

    print(f"✅ Sync pass complete. {len(changes)} item(s) changed.")

    if args.restart_if_changed:
        if not changes:
            print("  ➔ Nothing changed, no restart needed.")
        elif not _restart_allowed(config_dir):
            print(
                "  ➔ A restart was triggered moments ago; skipping to avoid a loop. "
                "Run FIRMWARE_RESTART manually if needed."
            )
        else:
            (config_dir / RESTART_LOCK_NAME).write_text(
                str(time.time()),
                encoding="utf-8",
            )
            try:
                request_restart(args.moonraker_url)
                print("  ➔ Firmware restart requested.")
            except Exception as exc:
                print(
                    f"  ⚠️  Could not request a restart ({exc}). "
                    "Run FIRMWARE_RESTART manually.",
                    file=sys.stderr,
                )
                return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())

# EOF
