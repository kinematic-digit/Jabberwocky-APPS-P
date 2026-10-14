#=-----------------------------------------------------------------------------
# JWS V3.0 SYSTEM ARCHITECTURE CENTRAL CORE ORCHESTRATOR (jws_core.py)
#=-----------------------------------------------------------------------------
#!/usr/bin/env python3
"""Jabberwocky Scrubber (JWS v3.0) Central Core Hub Orchestrator.

The primary operational command-line run-loop execution hub that chains 
the passive discovery layer and high-risk workspace sterilization engines.
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path
from collections import defaultdict

from jws_utils import SCRIPT_REVISION, SCRIPT_REVISION_DATE, IncludeNode
from jws_observer import scan
from jws_state_manager import sync_manifest_state
from jws_operator import apply_in_place_masking
from jws_reporter import Reporter
from jws_sterilizer import execute_workspace_sterilization, prompt_sterilizer_safety_instructions

def main() -> int:
    parser = argparse.ArgumentParser(
        description="JWS v3.0 Monitored Non-Destructive Scrubber Core."
    )
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        help="Path to root printer.cfg file target.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Synchronize configuration comment masks with jws_state.cfg.",
    )
    parser.add_argument(
        "--general-hygiene",
        action="store_true",
        help="Run passive validation scans without executing masking states.",
    )
    parser.add_argument(
        "--sterilize",
        action="store_true",
        help="Activate high-risk workspace permanent file deletion engine.",
    )
    parser.add_argument(
        "--confirm-reboot-cache-clear",
        action="store_true",
        help="Verify the system has been explicitly rebooted to dump ghost caches.",
    )
    args = parser.parse_args()

    config_dir = (
        args.config.resolve().parent 
        if args.config 
        else Path("~/printer_data/config").expanduser().resolve()
    )
    
    config_target = args.config if args.config else config_dir / "printer.cfg"
    state_cfg_path = config_dir / "jws_state.cfg"
    report_path = config_dir / "jws_hygiene_report.txt"

    reporter = Reporter(output_path=report_path, no_file=False)

    sections = defaultdict(list)
    macros = defaultdict(list)
    renames = []
    root_entries = []
    visited_includes = []
    syntax_issues = []
    section_options = defaultdict(dict)
    pin_assignments = defaultdict(list)
    missing = []
    visited = set()

    # Phase 1: Read-only background recursive tree crawl pass
    root_node = IncludeNode(config_target.resolve())
    scan(
        config_target, sections, macros, renames, root_entries, visited_includes,
        syntax_issues, section_options, pin_assignments, visited, missing,
        node=root_node, is_root=True
    )

    reporter.section("JWS v3.0 Core Analytical Engine Scan")
    reporter.echo(f"  • Active Engine Build Linked: {SCRIPT_REVISION} ({SCRIPT_REVISION_DATE})")
    reporter.echo(f"  • Root Target Profile Loaded: {config_target.name}")
    reporter.echo(f"  • Total Core Configuration Assets Scanned: {len(visited)} file(s)")

    if syntax_issues:
        reporter.section("Syntax Anomalies Detected")
        for path, line_no, desc in syntax_issues:
            reporter.echo(f"    [WARN] {path.name} (line {line_no}) -> {desc}")

    # Discover and build unreferenced orphan profiles
    all_cfg_files = sorted(list(config_dir.glob("**/*.cfg")))
    orphaned_targets = [f for f in all_cfg_files if f.resolve() not in visited and f.name != "jws_state.cfg"]

    manifest_states = {}
    if state_cfg_path.is_file():
        manifest_states = sync_manifest_state(state_cfg_path, visited)

    # Phase 2: In-place non-destructive mask processing
    if args.sync and manifest_states:
        reporter.section("Executing In-Place Component Synchronization")
        for inc_path, parent_f, _ in visited_includes:
            if apply_in_place_masking(parent_f, manifest_states, "file", inc_path):
                reporter.echo(f"    🟩 Synchronized file inclusion state mask: {inc_path}")
        for macro_slug, defs in macros.items():
            for name, path, _ in defs:
                if apply_in_place_masking(path, manifest_states, "macro", name):
                    reporter.echo(f"    🟩 Synchronized macro definition block mask: {name}")

    # Phase 3: Aggressive sterilization destruction logic loop
    if args.sterilize:
        if not args.confirm-reboot-cache-clear:
            reporter.section("Sterilization Protection Intercept Activated")
            for line in prompt_sterilizer_safety_instructions(config_dir):
                reporter.echo(line)
        else:
            reporter.section("Executing Destructive Workspace Sterilization Sweep")
            # Collect files tagged as disabled (0) inside the manifest configuration panel
            disabled_targets: list[Path] = []
            for k, val in manifest_states.items():
                if val == 0 and k.startswith("file_"):
                    target_name = k.replace("file_", "").replace("_cfg", ".cfg")
                    matched_paths = [f for f in all_cfg_files if f.name.lower() == target_name]
                    if matched_paths:
                        disabled_targets.append(matched_paths[0])

            moved, errors = execute_workspace_sterilization(
                config_dir=config_dir,
                orphaned_files=orphaned_targets,
                disabled_files=disabled_targets,
                live_run=True,
                cache_confirmed=True
            )
            
            for src, _ in moved:
                reporter.echo(f"    🟥 PERMANENTLY DELETED FROM METAL: config/{src.name}")
            for src, exc in errors:
                reporter.echo(f"    [!] DELETION EXCEPTION ON ASSET: {src.name} -> {str(exc)}")
            
            reporter.echo(f"\n🟩 SWEEP COMPLETE: Purged {len(moved)} assets permanently.")
            reporter.echo(f"   Original system state backup mirrored to .jws_rollback_anchor/")

    summary_alerts = ["Syntax validation passed cleanly." if not syntax_issues else f"Syntax warnings: {len(syntax_issues)}"]
    summary_alerts.append(f"Tracking {len(manifest_states)} active dashboard variable toggles.")
    if orphaned_targets:
        summary_alerts.append(f"Detected {len(orphaned_targets)} unreferenced .cfg file assets on metal.")
    
    if args.sterilize and args.confirm-reboot-cache-clear:
        summary_alerts.append("Destructive sterilization engine run completed successfully.")
    elif args.sterilize:
        summary_alerts.append("Sterilization pass HALTED: Awaiting mandatory host safety reboot.")
    else:
        summary_alerts.append("Scrubber operating in standard non-destructive workspace tracking pass.")

    reporter.append_mirrored_dashboards("PASS" if not syntax_issues else "ATTENTION", summary_alerts)
    reporter.flush_to_stdout()
    reporter.write_to_disk()
    return 0

if __name__ == "__main__":
    sys.exit(main())
