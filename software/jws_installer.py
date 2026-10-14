# =====================================================================
# JABBERWOCKY APPS — SYSTEM COMPILE, CONFIG SCANNER & INTEGRATION ENGINE
# VERSION: 5.9.0 [Include-Tree Inventory, Adoption, Restart-Triggered Sync]
# Location: software/jws_installer.py
# =====================================================================
import os
import sys
import shutil
import shlex
import re
import time
from pathlib import Path

VERSION_STRING = "v5.9.0"
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_SCRIPT_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scrubber.macro_manager import MacroManager, normalize_component_key
from scrubber.jws_observer import build_inventory
from scrubber.jws_operator import apply_in_place_masking
from scrubber.jws_analyzers import run_all
from scrubber.jws_dashboard import StateBook, plan_adoption, render

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, "printer_data", "config")
PRINTER_CFG = os.path.join(CONFIG_DIR, "printer.cfg")
KLIPPER_EXTRAS_PATH = os.path.join(HOME, "klipper", "klippy", "extras")
TARGET_DIST_DIR = os.path.join(CONFIG_DIR, "jabberwocky_dist")

MANAGER_PATH = os.path.join(CONFIG_DIR, "jwt_macro_manager.conf")
HARDWARE_CFG_PATH = os.path.join(TARGET_DIST_DIR, "jwt_hardware.cfg")
QUARANTINE_DIR = os.path.join(CONFIG_DIR, "jabberwocky_quarantine")

SHELL_EXT_URL = "https://raw.githubusercontent.com/dw-0/kiauh/master/kiauh/extensions/gcode_shell_cmd/assets/gcode_shell_command.py"
BRIDGE_FILE = "jwt_sync_bridge.cfg"
INSTALL_NOTES = []  # shown by the curses UI; printing would corrupt the screen
LAST_SUMMARY = {}   # counts from the last run, shown by the curses UI


def _noop(stage, message=""):
    return None


def _backup_files(paths, label):
    """Copy files under quarantine/<label>/<relative path>. Returns the backup folder."""
    dest_root = os.path.join(QUARANTINE_DIR, label)
    for path in paths:
        rel = os.path.relpath(os.path.realpath(path), os.path.realpath(CONFIG_DIR))
        dest = os.path.join(dest_root, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(path, dest)
    return dest_root


def _adopt_plain_comments(inv, book, stamp):
    """Turn the user's plain-# includes/macros (new to the dashboard) into managed, reversible masks."""
    plan = plan_adoption(inv, book)
    if not plan:
        return 0
    _backup_files(sorted({entry[0] for entry in plan}), f"adopt_backup_{stamp}")
    adopted = 0
    for file_path, target_type, name, scope in plan:
        manifest = {normalize_component_key(target_type, name, scope): 0}
        if apply_in_place_masking(Path(file_path), manifest, target_type, name, scope,
                                  config_dir=Path(CONFIG_DIR).resolve(), adopt_only=True):
            adopted += 1
    return adopted


def _sweep(inv, findings, stamp, keep):
    """Guarded one-shot cleanup: MOVE (never delete) backups and complete orphans into quarantine."""
    targets = [p for p in inv.backups if os.path.realpath(p) not in keep]
    for f in findings:
        if f.code == "FILE_ORPHAN":
            targets.extend(os.path.join(CONFIG_DIR, rel) for rel in f.files)
    moved = 0
    for path in targets:
        if not os.path.isfile(path):
            continue
        dest = os.path.join(QUARANTINE_DIR, f"sweep_{stamp}", os.path.relpath(os.path.realpath(path), os.path.realpath(CONFIG_DIR)))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(path, dest)
        moved += 1
    return moved


def _extruder_metrics(inv):
    metrics = {"run_current": "0.55", "stealthchop": "7.0", "rotation_dist": "35.13664"}
    patterns = {
        "run_current": r"^\s*run_current\s*:\s*(\S+)",
        "stealthchop": r"^\s*stealthchop_threshold\s*:\s*(\S+)",
        "rotation_dist": r"^\s*rotation_distance\s*:\s*(\S+)",
    }
    for path, text in inv.texts.items():
        if re.search(r"^\s*\[extruder\]", text, re.M | re.I):
            for key, pat in patterns.items():
                hit = re.search(pat, text, re.M | re.I)
                if hit:
                    metrics[key] = hit.group(1)
    return metrics


def _is_generic(inv):
    for path, text in inv.texts.items():
        if "nhk:" in text or "jwt_" in os.path.basename(path) or "jwprobe" in text:
            return False
    return True


def run_installation_pipeline(progress=None):
    """Scan the include tree, adopt user comments, write the dashboard and report, wire the sync bridge."""
    step = progress or _noop
    del INSTALL_NOTES[:]
    LAST_SUMMARY.clear()
    stamp = time.strftime("%Y%m%d_%H%M%S")

    step("backup", "Saving a safety copy of printer.cfg")
    backup_target = None
    if os.path.exists(PRINTER_CFG):
        backup_target = os.path.join(CONFIG_DIR, f"printer_{stamp}.bak")
        shutil.copy2(PRINTER_CFG, backup_target)
    os.makedirs(TARGET_DIST_DIR, exist_ok=True)

    step("scan", "Reading printer.cfg and following every [include] the way Klipper does")
    config_dir = Path(CONFIG_DIR)
    inv = build_inventory(Path(PRINTER_CFG), config_dir)
    existing = MacroManager(Path(MANAGER_PATH))
    book = StateBook(existing)

    step("adopt", "Looking for entries you already switched off with a # symbol")
    adopted = _adopt_plain_comments(inv, book, stamp)
    if adopted:
        inv = build_inventory(Path(PRINTER_CFG), config_dir)

    swept = 0
    sweep_key = normalize_component_key("action", "SWEEP TO QUARANTINE")
    if existing.states.get(sweep_key) == 1:
        step("sweep", "Moving backup and unused files into jabberwocky_quarantine (nothing is deleted)")
        swept = _sweep(inv, run_all(inv), stamp, {os.path.realpath(backup_target)} if backup_target else set())
        book.forced[sweep_key] = 0
        if swept:
            inv = build_inventory(Path(PRINTER_CFG), config_dir)

    step("analyze", "Checking for conflicts, duplicates, orphans and problems that stop Klipper")
    findings = run_all(inv)

    step("write", "Writing the dashboard and the pre-flight report")
    metrics = _extruder_metrics(inv)
    _write_hardware_cfg(metrics)
    existing_lines = []
    if os.path.isfile(MANAGER_PATH):
        with open(MANAGER_PATH, "r", encoding="utf-8", errors="ignore") as fh:
            existing_lines = fh.read().splitlines(True)
    env_mode = "GENERIC STANDALONE" if _is_generic(inv) else "ACTIVE EXPERIMENTAL"
    text, summary = render(inv, findings, book, VERSION_STRING, env_mode, metrics, existing_lines, swept)
    tmp_path = MANAGER_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp_path, MANAGER_PATH)

    summary["adopted"] = adopted
    LAST_SUMMARY.update(summary)

    step("link", "Connecting the dashboard to Klipper and installing the sync button")
    return _inject_and_link()


def _write_hardware_cfg(metrics):
    """Create the hardware baseline once; an existing file is never overwritten."""
    if os.path.exists(HARDWARE_CFG_PATH):
        return
    try:
        with open(HARDWARE_CFG_PATH, "x") as hw:
            hw.write("# =====================================================================\n# JABBERWOCKY ASC — AUTOMATED EXTRUDER PREFLIGHT CONFIGURATION TUNING\n# =====================================================================\n\n[gcode_macro _ASC_SETUP_VARIABLES]\n")
            hw.write(f"variable_asc_hardware_run_current : {metrics['run_current']}\nvariable_asc_stealthchop_threshold : {metrics['stealthchop']}\nvariable_asc_rotation_distance    : {metrics['rotation_dist']}\ngcode:\n    M118 Active toolhead hardware bounds successfully loaded.\n")
    except OSError as exc:
        if not os.path.exists(HARDWARE_CFG_PATH):
            raise RuntimeError(f"Unable to create hardware configuration {HARDWARE_CFG_PATH}: {exc}") from exc


def _klipper_extras_dir():
    base = os.environ.get("JWS_KLIPPER_DIR") or os.path.expanduser("~/klipper")
    return os.path.join(base, "klippy", "extras")


def _ensure_shell_command_extension():
    """Return True if Klipper has gcode_shell_command; install it from KIAUH if absent."""
    extras = _klipper_extras_dir()
    target = os.path.join(extras, "gcode_shell_command.py")
    if os.path.isfile(target):
        return True
    if not os.path.isdir(extras):
        INSTALL_NOTES.append(f"Klipper extras not found at {extras}; set JWS_KLIPPER_DIR. Sync button NOT installed.")
        return False
    try:
        import urllib.request
        with urllib.request.urlopen(SHELL_EXT_URL, timeout=15) as resp:
            code = resp.read().decode("utf-8")
        if "load_config_prefix" not in code:
            raise ValueError("unexpected extension content")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(code)
        INSTALL_NOTES.append(f"Installed gcode_shell_command extension to {target}")
        return True
    except Exception as exc:
        INSTALL_NOTES.append(f"Could not install gcode_shell_command ({exc}). Install it via KIAUH; sync button NOT installed.")
        return False


def _render_sync_bridge():
    src = os.path.join(REPO_ROOT, "jabberwocky_dist", BRIDGE_FILE)
    with open(src, "r", encoding="utf-8") as fh:
        text = fh.read()
    for key, value in {
        "__JWS_CONFIG_DIR__": shlex.quote(CONFIG_DIR),
        "__JWS_PYTHON__": shlex.quote(sys.executable or "python3"),
        "__JWS_CORE_PATH__": shlex.quote(os.path.join(REPO_ROOT, "scrubber", "jws_core.py")),
        "__JWS_MOONRAKER_PORT__": re.sub(r"\D", "", os.environ.get("JWS_MOONRAKER_PORT", "7125")) or "7125",
    }.items():
        text = text.replace(key, value)
    with open(os.path.join(TARGET_DIST_DIR, BRIDGE_FILE), "w", encoding="utf-8") as fh:
        fh.write(text)


def _inject_and_link():
    legal_includes = ("jwt_clutch_logic.cfg", "jwt_factory_blueprints.cfg", "macromanager.cfg")
    source_dist = os.path.join(REPO_ROOT, "jabberwocky_dist")
    if os.path.exists(source_dist):
        for file in os.listdir(source_dist):
            if file in legal_includes:
                shutil.copy2(os.path.join(source_dist, file), os.path.join(TARGET_DIST_DIR, file))
    bridge_ready = False
    bridge_path = os.path.join(TARGET_DIST_DIR, BRIDGE_FILE)
    if os.path.isfile(os.path.join(source_dist, BRIDGE_FILE)) and _ensure_shell_command_extension():
        _render_sync_bridge()
        bridge_ready = True
        INSTALL_NOTES.append("Sync button installed: run JABBERWOCKY_SYNC_NOW in the Mainsail console.")
    elif os.path.isfile(bridge_path):
        os.remove(bridge_path)
    try:
        with open(PRINTER_CFG, "r") as f: original = f.read()
        banner = r"\n?# =+\n# JABBERWOCKY ASYNCHRONOUS PRINT PROTECTION SUITE INTEGRATION[^\n]*\n# =+\n"
        lines = re.sub(banner, "\n", original).splitlines(True)
        filtered_lines = [l for l in lines if "jwt_clutch_logic.cfg" not in l and BRIDGE_FILE not in l and "jwt_macro_proxies.cfg" not in l and "Jabberwocky-APPS" not in l]
        save_config_idx = next((i for i, line in enumerate(filtered_lines) if "SAVE_CONFIG" in line), -1)
        include_block = f"\n# =====================================================================\n# JABBERWOCKY ASYNCHRONOUS PRINT PROTECTION SUITE INTEGRATION ({VERSION_STRING})\n# =====================================================================\n[include jabberwocky_dist/jwt_clutch_logic.cfg]\n"
        if bridge_ready:
            include_block += f"[include jabberwocky_dist/{BRIDGE_FILE}]\n"
        include_block += "\n"
        if save_config_idx != -1: filtered_lines.insert(save_config_idx, include_block)
        else: filtered_lines.append(include_block)
        with open(PRINTER_CFG, "w") as f: f.writelines(filtered_lines)
    except OSError as exc:
        INSTALL_NOTES.append(f"Could not update printer.cfg: {exc}")
    return True
#EOF
