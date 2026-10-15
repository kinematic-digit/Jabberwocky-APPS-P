# =====================================================================
# JABBERWOCKY APPS — SYSTEM COMPILE, CONFIG SCANNER & INTEGRATION ENGINE
# VERSION: 5.9.0 [Include-Tree Inventory, Adoption, Restart-Triggered Sync]
# Location: software/jws_installer.py
# =====================================================================
import hashlib
import os
import sys
import shutil
import shlex
import re
import stat
import time
import tempfile
from pathlib import Path

VERSION_STRING = "v5.9.0"
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_SCRIPT_DIR, ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from software.macro_manager.macro_manager import MacroManager, normalize_component_key
from software.macro_manager.jws_observer import build_inventory
from software.macro_manager.jws_operator import apply_in_place_masking
from software.macro_manager.jws_analyzers import run_all
from software.macro_manager.jws_dashboard import StateBook, plan_adoption, render

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
JWP_BLOCK_START = "# >>> JWP INSTALLER-MANAGED INTEGRATION >>>"
JWP_BLOCK_END = "# <<< JWP INSTALLER-MANAGED INTEGRATION <<<"
JWP_USER_CONFIG_FILES = {"jwprobe_hardware.cfg", "jwprobe_globals.cfg"}


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

    persistence_status = _prepare_jwp_persistence()
    if persistence_status in ("conflict", "error", "custom"):
        raise RuntimeError(INSTALL_NOTES[0] or "JWP persistence preparation needs attention.")
    _deploy_jwp_event_tracker()

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


def run_jwp_installation_pipeline(progress=None):
    """Install/update JWP files and its narrowly owned printer.cfg integration."""
    step = progress or _noop
    del INSTALL_NOTES[:]
    source_dir = Path(REPO_ROOT) / "software" / "jw_probe"
    config_root = Path(CONFIG_DIR)
    package_dir = config_root / "jabberwockyprobe"
    printer_cfg = Path(PRINTER_CFG)
    entry_path = package_dir / "jwprobe_entry.cfg"
    source_entry = source_dir / "jwprobe_entry.cfg"
    hardware_existed = (package_dir / "jwprobe_hardware.cfg").is_file()

    if not printer_cfg.is_file():
        raise RuntimeError(f"Cannot install JWP because printer.cfg is missing: {printer_cfg}")
    if printer_cfg.is_symlink():
        raise RuntimeError(f"Refusing to update symlinked printer.cfg: {printer_cfg}")
    if package_dir.is_symlink() or not package_dir.resolve().is_relative_to(config_root.resolve()):
        raise RuntimeError(
            f"Refusing to install through a symlink or outside the config tree: {package_dir}"
        )
    if not source_entry.is_file():
        raise RuntimeError(f"JWP source entry is missing: {source_entry}")
    event_source = source_dir / "jwp_event_tracker.py"
    extras_dir = Path(_klipper_extras_dir())
    if not event_source.is_file():
        raise RuntimeError(f"JWP event tracker source is missing: {event_source}")
    if not extras_dir.is_dir():
        raise RuntimeError(
            f"Klipper extras were not found at {extras_dir}; set JWS_KLIPPER_DIR "
            "to the Klipper source directory."
        )
    event_target = extras_dir / event_source.name
    if event_target.is_symlink():
        raise RuntimeError(f"Refusing to replace symlinked Klipper extra: {event_target}")

    step("preflight", "Checking existing JWP settings and printer integrations")
    try:
        original_printer_cfg = printer_cfg.read_text(encoding="utf-8")
        inv = build_inventory(printer_cfg, config_root)
        feature_flags, managed_text = _plan_jwp_printer_integration(
            original_printer_cfg, inv, package_dir, entry_path
        )
        for enabled, filename in (
            (feature_flags["qgl"], "jwprobe_qgl.cfg"),
            (feature_flags["bed_mesh"], "jwprobe_bed_mesh.cfg"),
        ):
            if enabled and not (source_dir / filename).is_file():
                raise RuntimeError(f"Required JWP wrapper source is missing: {source_dir / filename}")
        files_to_write = _plan_jwp_package(source_dir, package_dir, entry_path, source_entry)
        _plan_jwp_event_config(inv, package_dir, files_to_write)
    except (OSError, ValueError, RuntimeError) as exc:
        INSTALL_NOTES.insert(0, str(exc))
        raise RuntimeError(str(exc)) from exc

    try:
        event_payload = event_source.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"Unable to read JWP event tracker source: {exc}") from exc
    if not event_target.exists() or event_target.read_bytes() != event_payload:
        files_to_write[event_target] = event_payload

    write_map = dict(files_to_write)
    if managed_text != original_printer_cfg:
        write_map[printer_cfg] = managed_text.encode("utf-8")

    step("backup", "Backing up JWP files that need updating")
    _backup_jwp_changes(write_map, config_root)

    step("persistence", "Preserving or safely migrating JWP runtime variables")
    persistence_status = _prepare_jwp_persistence(
        entry_path=entry_path if entry_path.is_file() else source_entry,
        allow_missing_entry=True,
        update_entry=entry_path.is_file(),
    )
    if persistence_status in ("conflict", "error", "custom"):
        raise RuntimeError(INSTALL_NOTES[0] if INSTALL_NOTES else
                           "JWP persistence requires explicit resolution.")

    # A fresh hardware file is an example for the supported bench setup. Keep
    # it intact, but make the required operator review explicit before restart.
    if not hardware_existed:
        INSTALL_NOTES.append(
            "Fresh JWP hardware defaults were installed. Verify the probe pin and "
            "offsets in jabberwockyprobe/jwprobe_hardware.cfg before restarting Klipper."
        )

    step("deploy", "Deploying JWP configuration and read-only event tracker")
    for destination, payload in write_map.items():
        _write_bytes_atomically(destination, payload)

    flags = ", ".join(
        label for enabled, label in (
            (feature_flags["qgl"], "QGL"),
            (feature_flags["bed_mesh"], "bed mesh"),
        ) if enabled
    ) or "no QGL/bed-mesh wrappers (native sections not configured)"
    INSTALL_NOTES.append(
        f"JWP installation/update completed. Installer-managed integrations: {flags}."
    )
    return True


def _plan_jwp_package(source_dir, package_dir, entry_path, source_entry):
    if not source_dir.is_dir():
        raise RuntimeError(f"JWP source directory is missing: {source_dir}")

    try:
        entry_text = entry_path.read_text(encoding="utf-8") if entry_path.is_file() \
            else source_entry.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Unable to read the JWP entry file: {exc}") from exc
    if not source_entry.is_file():
        raise RuntimeError(f"JWP source entry is missing: {source_entry}")
    for include in _active_includes(source_entry.read_text(encoding="utf-8")):
        if Path(include).name in {"jwprobe_qgl.cfg", "jwprobe_bed_mesh.cfg"}:
            continue
        if not (source_dir / Path(include).name).is_file():
            raise RuntimeError(f"JWP source entry references a missing file: {include}")

    filename = _save_variables_filename(entry_text)
    canonical = "~/printer_data/config/jwprobe_runtime_vars.cfg"
    legacy = "~/printer_data/config/jabberwockyprobe/jwprobe_vars.cfg"
    if filename not in (canonical, legacy):
        raise RuntimeError(
            f"JWP uses custom save_variables path {filename!r}; resolve it explicitly "
            "before installing or updating."
        )
    if filename == legacy:
        updated = _replace_save_variables_filename(entry_text, legacy, canonical)
        if updated is None:
            raise RuntimeError("The legacy save_variables entry could not be updated safely.")
        entry_text = updated

    # The wrapper files are wired from printer.cfg, not from the master entry.
    entry_text = _without_jwp_wrapper_includes(entry_text)
    files = {}
    package_real = package_dir.resolve()
    for source in sorted(source_dir.glob("jwprobe_*.cfg")):
        if source.name in {"jwprobe_vars.cfg", "jwprobe_runtime_vars.cfg"}:
            continue
        destination = package_dir / source.name
        if destination.name == "jwprobe_entry.cfg":
            payload = entry_text.encode("utf-8")
        else:
            try:
                payload = source.read_bytes()
            except OSError as exc:
                raise RuntimeError(f"Unable to read JWP source {source}: {exc}") from exc

        # Hardware bindings and globals are user/machine-owned after first
        # installation. Their source copies are used only to seed a fresh tree.
        if destination.name in JWP_USER_CONFIG_FILES and destination.exists():
            continue
        if destination.exists() and destination.is_symlink():
            raise RuntimeError(f"Refusing to replace symlinked JWP configuration: {destination}")
        if not destination.parent.resolve().is_relative_to(package_real):
            raise RuntimeError(f"JWP package path escapes its config directory: {destination}")
        if not destination.exists() or destination.read_bytes() != payload:
            files[destination] = payload
    return files


def _plan_jwp_event_config(inventory, package_dir, files_to_write):
    """Ensure the read-only tracker is registered against the configured probe pin."""
    hardware = package_dir / "jwprobe_hardware.cfg"
    external_registration_count = 0
    external_registrations = []
    for path, content in inventory.texts.items():
        if Path(path).resolve() == hardware.resolve():
            continue
        external_registration_count += _section_count(content, "jwp_event_tracker")
        sections = _section_values(content, "jwp_event_tracker", "pin")
        external_registrations.extend(sections)

    staged_hardware = files_to_write.get(hardware)
    hardware_text = (
        staged_hardware.decode("utf-8") if staged_hardware is not None
        else hardware.read_text(encoding="utf-8") if hardware.is_file()
        else ""
    )
    hardware_registration_count = _section_count(hardware_text, "jwp_event_tracker")
    staged_registrations = _section_values(hardware_text, "jwp_event_tracker", "pin")
    registered_pins = external_registrations + staged_registrations
    registration_count = external_registration_count + hardware_registration_count
    if registration_count > 1:
        raise RuntimeError(
            "Multiple [jwp_event_tracker] sections are configured; resolve the duplicate "
            "before installing JWP."
        )
    if registration_count != len(registered_pins):
        raise RuntimeError(
            "A [jwp_event_tracker] section has no single pin setting; resolve it before installing JWP."
        )

    probe_pins = _section_values(hardware_text, "probe", "pin")
    if len(probe_pins) != 1:
        raise RuntimeError(
            f"JWP hardware file {hardware} must contain exactly one [probe] pin "
            "before event tracking can be installed."
        )
    probe_pin = probe_pins[0]
    if registered_pins:
        if registered_pins[0] != probe_pin:
            raise RuntimeError(
                "[jwp_event_tracker] pin differs from the JWP [probe] pin; "
                "resolve the configuration explicitly."
            )
        if external_registrations and staged_registrations:
            if hardware.is_symlink():
                raise RuntimeError(
                    f"JWP hardware file is symlinked and would need an integration edit: {hardware}"
                )
            files_to_write[hardware] = _without_section(
                hardware_text, "jwp_event_tracker"
            ).encode("utf-8")
        return

    if hardware.is_symlink():
        raise RuntimeError(
            f"JWP hardware file is symlinked and would need an integration edit: {hardware}"
        )
    addition = (
        "\n[jwp_event_tracker]\n"
        "# Read-only event capture reuses the configured JWP probe switch.\n"
        f"pin: {probe_pin}\n"
        "telemetry_file: ~/printer_data/config/jwp_calibration_profile.csv\n"
    )
    files_to_write[hardware] = hardware_text.rstrip("\n").encode("utf-8") + addition.encode("utf-8")


def _without_section(text, section_name):
    lines = text.splitlines(keepends=True)
    output = []
    skipping = False
    for line in lines:
        header = re.match(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$", line)
        if header:
            skipping = header.group(1).strip().lower() == section_name.lower()
        if not skipping:
            output.append(line)
    return "".join(output)


def _section_values(text, section_name, option):
    values = []
    active_section = None
    for line in text.splitlines():
        header = re.match(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$", line)
        if header:
            active_section = header.group(1).strip().lower()
        elif active_section == section_name.lower():
            match = re.match(rf"^\s*{re.escape(option)}\s*:\s*(\S.*?)\s*$", line, re.I)
            if match:
                values.append(match.group(1).strip())
    return values


def _section_count(text, section_name):
    return len(re.findall(
        rf"^\s*\[{re.escape(section_name)}\]\s*(?:#.*)?$",
        text,
        re.M | re.I,
    ))


def _without_jwp_wrapper_includes(text):
    output = []
    for line in text.splitlines(keepends=True):
        match = re.match(
            r"^\s*\[\s*include\s+([^\]\s]+)\s*\]\s*(?:#.*)?(?:\r?\n)?$",
            line,
            re.IGNORECASE,
        )
        if match and Path(match.group(1).replace("\\", "/")).name.lower() in {
            "jwprobe_qgl.cfg", "jwprobe_bed_mesh.cfg"
        }:
            continue
        output.append(line)
    return "".join(output)


def _plan_jwp_printer_integration(printer_text, inventory, package_dir, entry_path):
    lines = printer_text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.strip() == JWP_BLOCK_START]
    ends = [i for i, line in enumerate(lines) if line.strip() == JWP_BLOCK_END]
    if len(starts) != len(ends) or len(starts) > 1:
        raise RuntimeError(
            "JWP integration markers are duplicated or malformed in printer.cfg; "
            "preserve the file and resolve the markers manually."
        )
    if bool(starts) != bool(ends) or (starts and ends[0] <= starts[0]):
        raise RuntimeError(
            "JWP integration markers are malformed in printer.cfg; no changes were made."
        )
    block_range = (starts[0], ends[0]) if starts else None
    if block_range:
        contents = [
            line.strip() for line in lines[block_range[0] + 1:block_range[1]]
            if line.strip() and not line.lstrip().startswith("#")
        ]
        allowed = {
            "[include jabberwockyprobe/jwprobe_entry.cfg]",
            "[include jabberwockyprobe/jwprobe_qgl.cfg]",
            "[include jabberwockyprobe/jwprobe_bed_mesh.cfg]",
        }
        if any(line.lower() not in {value.lower() for value in allowed} for line in contents):
            raise RuntimeError(
                "The JWP-owned printer.cfg block contains unrecognized content; "
                "preserve it and resolve the block manually."
            )

    active_files = inventory.texts
    feature_flags = {
        "qgl": _inventory_has_section(active_files, "quad_gantry_level"),
        "bed_mesh": _inventory_has_section(active_files, "bed_mesh"),
    }
    wrapper_sections = {
        "gcode_macro quad_gantry_level": "jwprobe_qgl.cfg",
        "gcode_macro bed_mesh_calibrate": "jwprobe_bed_mesh.cfg",
    }
    owned_wrapper_paths = {
        (package_dir / name).resolve() for name in wrapper_sections.values()
    }
    native_aliases = {
        "_jwp_native_quad_gantry_level": (
            "jwprobe_qgl.cfg", "gcode_macro quad_gantry_level"
        ),
        "_jwp_native_bed_mesh_calibrate": (
            "jwprobe_bed_mesh.cfg", "gcode_macro bed_mesh_calibrate"
        ),
    }
    for path, content in active_files.items():
        resolved = Path(path).resolve()
        section = None
        for line in content.splitlines():
            header = re.match(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$", line)
            if header:
                section = header.group(1).strip().lower()
                continue
            if not section or not section.startswith("gcode_macro "):
                continue
            rename = re.match(r"^\s*rename_existing\s*:\s*(\S+)", line, re.I)
            if not rename:
                continue
            alias = rename.group(1).lower()
            if alias not in native_aliases:
                continue
            wrapper_file, wrapper_section = native_aliases[alias]
            if resolved == (package_dir / wrapper_file).resolve() and section == wrapper_section:
                continue
            raise RuntimeError(
                f"Conflicting rename_existing alias {rename.group(1)!r} in {path}; "
                "JWP left printer.cfg unchanged."
            )
        if resolved in owned_wrapper_paths:
            continue
        for section in wrapper_sections:
            if re.search(rf"^\s*\[{re.escape(section)}\]\s*(?:#.*)?$", content, re.M | re.I):
                raise RuntimeError(
                    f"Conflicting user or third-party wrapper [{section}] in {path}; "
                    "JWP left printer.cfg unchanged."
                )

    master_target = "jabberwockyprobe/jwprobe_entry.cfg"
    external_master = 0
    for path, content in active_files.items():
        path_obj = Path(path)
        for line_number, include in _active_include_records(content):
            target = include.replace("\\", "/").strip().lower()
            target_name = Path(target).name
            within_block = _line_in_jwp_block(path_obj, line_number, block_range)
            if target_name == "jwprobe_entry.cfg" and target != master_target:
                raise RuntimeError(
                    f"JWP master entry uses non-canonical include {include!r} in {path}; "
                    "resolve the include path before installation."
                )
            if target_name == "jwprobe_entry.cfg" and not within_block and path_obj.resolve() != Path(PRINTER_CFG).resolve():
                raise RuntimeError(
                    f"JWP master entry is included from {path}; move it to printer.cfg "
                    "before using the installer-managed integration."
                )
            if target_name == "jwprobe_entry.cfg" and not within_block:
                external_master += 1
            if target_name in {"jwprobe_qgl.cfg", "jwprobe_bed_mesh.cfg"} and not within_block:
                if path_obj.resolve() == entry_path.resolve() and target in {
                    "jwprobe_qgl.cfg", "jwprobe_bed_mesh.cfg"
                }:
                    continue  # removed from the entry as part of this package update
                raise RuntimeError(
                    f"JWP wrapper include {include!r} is outside the installer-owned "
                    f"block in {path}; resolve it before installation."
                )
    if external_master > 1:
        raise RuntimeError("Duplicate JWP master includes were found; resolve them before installation.")

    expected = []
    if external_master == 0:
        expected.append("[include jabberwockyprobe/jwprobe_entry.cfg]")
    if feature_flags["qgl"]:
        expected.append("[include jabberwockyprobe/jwprobe_qgl.cfg]")
    if feature_flags["bed_mesh"]:
        expected.append("[include jabberwockyprobe/jwprobe_bed_mesh.cfg]")
    block = [JWP_BLOCK_START + "\n", *(line + "\n" for line in expected), JWP_BLOCK_END + "\n"]
    if block_range:
        updated_lines = lines[:block_range[0]] + block + lines[block_range[1] + 1:]
    else:
        marker = next(
            (
                i for i, line in enumerate(lines)
                if re.match(r"^\s*#\*#\s*<[-]+\s*SAVE_CONFIG\b", line, re.I)
            ),
            len(lines),
        )
        updated_lines = lines[:marker] + (["\n"] if marker and lines[marker - 1].strip() else []) \
            + block + (["\n"] if marker < len(lines) and lines[marker].strip() else []) \
            + lines[marker:]
    return feature_flags, "".join(updated_lines)


def _inventory_has_section(texts, section):
    return any(
        re.search(rf"^\s*\[{re.escape(section)}\]\s*(?:#.*)?$", text, re.M | re.I)
        for text in texts.values()
    )


def _active_includes(text):
    return [include for _line_number, include in _active_include_records(text)]


def _active_include_records(text):
    includes = []
    for line_number, line in enumerate(text.splitlines()):
        match = re.match(r"^\s*\[\s*include\s+([^\]\s]+)\s*\]\s*(?:#.*)?$", line, re.I)
        if match:
            includes.append((line_number, match.group(1)))
    return includes


def _line_in_jwp_block(path, line_number, block_range):
    if block_range is None or Path(path).resolve() != Path(PRINTER_CFG).resolve():
        return False
    return block_range[0] < line_number < block_range[1]


def _backup_jwp_changes(write_map, config_root):
    existing = [path for path in write_map if path.exists()]
    if not existing:
        return None
    quarantine = config_root / "jabberwocky_quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("jwp_install_%Y%m%d_%H%M%S")
    for suffix in range(10000):
        label = stamp if suffix == 0 else f"{stamp}_{suffix}"
        backup_root = quarantine / label
        try:
            backup_root.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise RuntimeError("Could not allocate a unique JWP recovery backup directory.")
    try:
        for source in existing:
            try:
                relative = source.resolve().relative_to(config_root.resolve())
            except ValueError:
                relative = Path("klipper_extras") / source.name
            destination = backup_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    except OSError as exc:
        raise RuntimeError(
            f"JWP backup failed at {backup_root}; no deployment files were changed: {exc}"
        ) from exc
    INSTALL_NOTES.append(f"Backed up existing JWP files to {backup_root}")
    return backup_root


def _write_bytes_atomically(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


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


def _prepare_jwp_persistence(
    entry_path=None, allow_missing_entry=False, update_entry=True
):
    """Prepare JWP variables without replacing existing user data."""
    entry = Path(entry_path) if entry_path is not None else (
        Path(CONFIG_DIR) / "jabberwockyprobe" / "jwprobe_entry.cfg"
    )
    if not entry.is_file():
        if not allow_missing_entry:
            return "not-configured"
        INSTALL_NOTES.insert(0, f"JWP entry source is unavailable: {entry}")
        return "error"

    canonical = Path(CONFIG_DIR) / "jwprobe_runtime_vars.cfg"
    legacy = Path(CONFIG_DIR) / "jabberwockyprobe" / "jwprobe_vars.cfg"
    migration = Path(CONFIG_DIR) / ".jwprobe_runtime_vars.migration"
    canonical_name = "~/printer_data/config/jwprobe_runtime_vars.cfg"
    legacy_name = "~/printer_data/config/jabberwockyprobe/jwprobe_vars.cfg"

    try:
        text = entry.read_text(encoding="utf-8")
    except OSError as exc:
        INSTALL_NOTES.insert(0, f"JWP persistence was not changed: cannot read {entry}: {exc}")
        return "error"

    filename = _save_variables_filename(text)
    if filename is None:
        INSTALL_NOTES.insert(0, "JWP persistence was not changed: entry has no single [save_variables] filename.")
        return "error"

    if filename not in (canonical_name, legacy_name):
        INSTALL_NOTES.insert(
            0,
            f"JWP persistence uses custom path {filename}; installer left it unchanged.",
        )
        return "custom"

    try:
        legacy_is_seed = _is_jwp_seed_file(legacy)
        legacy_runtime_exists = legacy.exists() and not legacy_is_seed
        if canonical.exists() and legacy_runtime_exists:
            marker_valid = _valid_jwp_migration_marker(migration, legacy)
            marker_value = migration.read_text(encoding="ascii").strip() if marker_valid else ""
            migration_digest = marker_value[len("sha256="):] if marker_value.startswith("sha256=") else ""
            interrupted_copy_matches = (
                marker_valid
                and filename == legacy_name
                and hashlib.sha256(canonical.read_bytes()).hexdigest()
                == migration_digest
            )
            if not marker_valid or (filename == legacy_name and not interrupted_copy_matches):
                INSTALL_NOTES.insert(
                    0,
                    "JWP persistence conflict: both jwprobe_runtime_vars.cfg and "
                    "jabberwockyprobe/jwprobe_vars.cfg exist. Both were preserved; "
                    "resolve which data is authoritative before changing the entry path.",
                )
                return "conflict"
        elif legacy_runtime_exists:
            if migration.exists():
                _resume_jwp_variable_migration(legacy, canonical, migration)
            else:
                _migrate_jwp_legacy_variables(legacy, canonical, migration)
        elif not canonical.exists() and migration.exists():
            # Resume a migration interrupted after its intent marker was written.
            _resume_jwp_variable_migration(legacy, canonical, migration)
        elif not canonical.exists():
            _create_empty_jwp_variables(canonical)

        if filename == legacy_name:
            updated = _replace_save_variables_filename(text, legacy_name, canonical_name)
            if updated is None:
                INSTALL_NOTES.insert(
                    0,
                    f"JWP runtime variables are prepared at {canonical}, but "
                    f"{entry} could not be updated safely. Do not restart Klipper "
                    "until the entry filename is corrected.",
                )
                return "error"
            if updated != text and update_entry and entry.is_file():
                _write_text_atomically(entry, updated)

        return "ready"
    except (OSError, ValueError) as exc:
        INSTALL_NOTES.insert(0, f"JWP persistence preparation failed without overwriting existing data: {exc}")
        return "error"


def _is_jwp_seed_file(path):
    """Identify the checked-in seed by its explicit header, not its filename."""
    if not path.is_file():
        return False
    try:
        header = path.read_bytes()[:2048].lower()
    except OSError:
        raise
    return b"repo seed copy only" in header


def _save_variables_filename(text):
    """Return the sole filename value inside [save_variables], or None."""
    section = None
    filenames = []
    for line in text.splitlines():
        header = re.match(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$", line)
        if header:
            section = header.group(1).strip().lower()
            continue
        if section == "save_variables":
            match = re.match(r"^\s*filename\s*:\s*(.*?)\s*(?:#.*)?$", line, re.IGNORECASE)
            if match:
                filenames.append(match.group(1).strip())
    return filenames[0] if len(filenames) == 1 else None


def _replace_save_variables_filename(text, expected, replacement):
    """Replace only the filename setting in a single [save_variables] section."""
    lines = text.splitlines(keepends=True)
    section = None
    matches = []
    for index, line in enumerate(lines):
        header = re.match(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$", line)
        if header:
            section = header.group(1).strip().lower()
            continue
        if section == "save_variables":
            match = re.match(
                r"^(\s*filename\s*:\s*)(\S+)(\s*(?:#.*)?)(\r?\n?)$",
                line,
                re.IGNORECASE,
            )
            if match:
                matches.append((index, match))
    if len(matches) != 1:
        return None
    index, match = matches[0]
    if match.group(2) == replacement:
        return text
    if match.group(2) != expected:
        return None
    lines[index] = f"{match.group(1)}{replacement}{match.group(3)}{match.group(4)}"
    return "".join(lines)


def _create_empty_jwp_variables(path):
    """Create an empty Klipper variable store exclusively for a fresh install."""
    _create_file_atomically_if_absent(path, b"[Variables]\n")
    INSTALL_NOTES.insert(0, "Initialized an empty JWP runtime variable store; no seed calibration values were copied.")


def _migrate_jwp_legacy_variables(legacy, canonical, marker):
    """Copy the legacy store once and journal its digest before changing config."""
    legacy_data = legacy.read_bytes()
    marker_data = f"sha256={hashlib.sha256(legacy_data).hexdigest()}\n"
    if marker.exists():
        raise ValueError(f"migration marker already exists at {marker}; inspect it before retrying")
    _create_file_atomically_if_absent(marker, marker_data.encode("ascii"))
    _resume_jwp_variable_migration(legacy, canonical, marker)
    INSTALL_NOTES.insert(
        0,
        "Migrated the legacy JWP variable file without deleting it; the original remains as a recovery copy."
    )


def _resume_jwp_variable_migration(legacy, canonical, marker):
    """Resume an interrupted legacy migration without overwriting either file."""
    if not _valid_jwp_migration_marker(marker, legacy):
        raise ValueError(
            f"legacy migration cannot be verified; preserve all files and inspect {marker}"
        )
    marker_value = marker.read_text(encoding="ascii").strip()
    expected_digest = marker_value[len("sha256="):] if marker_value.startswith("sha256=") else ""
    legacy_data = legacy.read_bytes()
    if hashlib.sha256(legacy_data).hexdigest() != expected_digest:
        raise ValueError("legacy JWP variable file changed during migration")
    if canonical.exists():
        if hashlib.sha256(canonical.read_bytes()).hexdigest() == expected_digest:
            return
        raise ValueError(
            f"canonical variable file appeared during legacy migration; preserve both files and inspect {canonical}"
        )
    _create_file_atomically_if_absent(canonical, legacy_data)


def _create_file_atomically_if_absent(path, content):
    """Atomically create a file without ever replacing a concurrent user file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o644)
        os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _valid_jwp_migration_marker(marker, legacy):
    if not marker.is_file() or not legacy.is_file():
        return False
    try:
        expected = marker.read_text(encoding="ascii").strip()
    except OSError:
        return False
    return expected == f"sha256={hashlib.sha256(legacy.read_bytes()).hexdigest()}"


def _write_text_atomically(path, text):
    """Replace a small config file atomically while retaining its mode."""
    temp_path = path.with_name(path.name + ".jwp-tmp")
    mode = path.stat().st_mode
    try:
        with temp_path.open("x", encoding="utf-8", newline="") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _deploy_jwp_event_tracker():
    """Install the Klipper extra when the printer config contains JWP."""
    config_entry = Path(CONFIG_DIR) / "jabberwockyprobe" / "jwprobe_entry.cfg"
    if not config_entry.is_file():
        return False

    source = Path(REPO_ROOT) / "software" / "jw_probe" / "jwp_event_tracker.py"
    if not source.is_file():
        raise RuntimeError(f"JWP event tracker source is missing: {source}")

    extras = Path(_klipper_extras_dir())
    if not extras.is_dir():
        raise RuntimeError(
            f"JWP is configured, but Klipper extras were not found at {extras}; "
            "set JWS_KLIPPER_DIR to the Klipper source directory."
        )

    target = extras / source.name
    try:
        shutil.copy2(source, target)
    except OSError as exc:
        raise RuntimeError(
            f"Unable to deploy the JWP event tracker to {target}: {exc}"
        ) from exc

    INSTALL_NOTES.append(f"Installed JWP event tracker to {target}")
    return True


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
        "__JWS_CORE_PATH__": shlex.quote(
            os.path.join(REPO_ROOT, "software", "macro_manager", "jws_core.py")
        ),
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
