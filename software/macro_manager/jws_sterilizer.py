# =====================================================================
# JWS V3.0 DESTRUCTIVE PURGE & WORKSPACE STERILIZER ENGINE (jws_sterilizer.py)
# VERSION: 3.0.0
# =====================================================================
#!/usr/bin/env python3
"""Jabberwocky Scrubber (JWS v3.0) Workspace Sterilizer Purge Engine."""

from __future__ import annotations
import sys
import shutil
from datetime import datetime
from pathlib import Path

def execute_workspace_sterilization(
    config_dir: Path,
    orphaned_files: list[Path],
    disabled_files: list[Path],
    live_run: bool = False,
    cache_confirmed: bool = False
) -> tuple[list[tuple[Path, Path]], list[tuple[Path, Exception]]]:
    """Manages the aggressive destruction and relocation of unreferenced configuration elements."""
    config_dir = config_dir.resolve()
    date_stub = datetime.now().strftime("%Y%m%d")
    hidden_rollback_root = config_dir / ".jws_rollback_anchor" / f"config_backup_{date_stub}"
    
    moved_records: list[tuple[Path, Path]] = []
    error_records: list[tuple[Path, Exception]] = []
    
    targets_for_destruction = orphaned_files + disabled_files
    if not targets_for_destruction:
        return moved_records, error_records

    if not live_run or not cache_confirmed:
        return moved_records, error_records

    try:
        if not hidden_rollback_root.exists():
            shutil.copytree(
                config_dir,
                hidden_rollback_root,
                symlinks=False,
                ignore=shutil.ignore_patterns(
                    '*.bin', '*.log', '.git', 'config_backup_*', 
                    '.jws_rollback_anchor', 'jws_archive_*'
                )
            )
    except Exception as exc:
        error_records.append((config_dir, exc))
        return moved_records, error_records

    for target in targets_for_destruction:
        target_path = target.resolve()
        if not target_path.is_file():
            continue
            
        try:
            target_path.unlink()
            moved_records.append((target_path, Path("DESTRUCTIVE_PURGE_UNLINK")))
        except OSError as exc:
            error_records.append((target_path, exc))

    return moved_records, error_records

def prompt_sterilizer_safety_instructions(config_dir: Path) -> list[str]:
    """Generates the high-visibility instructions requiring host reboots."""
    instructions = [
        "⚠️  CRITICAL OPERATOR VERIFICATION GATES REQUIRED FOR HARDWARE STERILIZATION",
        "-" * 80,
        "  1. Klipper and Moonraker process data states are heavily cached in memory.",
        "  2. Deleting configurations blindly can permanently brick startup parameters.",
        "",
        "🔴 MANDATORY REBOOT PROCEDURE TO CLEAR GHOST STATES:",
        "  a. Exit this execution track and reboot your host controller via SSH:",
        "     sudo reboot",
        "  b. Refresh your web browser to ensure no old dashboard layouts are loaded.",
        "  c. Re-run this utility with explicit double flags to execute the purge:",
        f"     python3 ~/Jabberwocky-APPS/software/macro_manager/jws_core.py --sterilize --confirm-reboot-cache-clear",
        "-" * 80
    ]
    return instructions
