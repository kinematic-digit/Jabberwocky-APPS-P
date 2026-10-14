# =====================================================================
# JABBERWOCKY APPS ECOSYSTEM — HARDENED REGEX UTILITIES & CONSTANTS
# Location: scrubber/jws_utils.py
# =====================================================================
import os
import re

SCRIPT_REVISION = "5.9.0"
SCRIPT_REVISION_DATE = "2026-10-10"

MASK_TAG = "#💤#"
MASK_START_TAG = "#💤#=== JABBERWOCKY COMPLIANCE ISOLATION BLOCK START ===#💤#"
MASK_END_TAG = "#💤#=== JABBERWOCKY COMPLIANCE ISOLATION BLOCK END ===#💤#"

MASK_REENABLE_NOTE = (
    "#💤# TO RE-ENABLE: set this macro's checkbox to 1 in jwt_macro_manager.conf, "
    "then run JABBERWOCKY_SYNC_NOW (or restart). Do not edit the lines inside this block."
)
MASK_NOTE_PREFIX = "#💤# TO RE-ENABLE:"

# Extensible catalogue of hardware section families: (regex on lowercase header, kind).
# Group 'owner' (optional) names the stepper/extruder a driver or motor block belongs to.
HARDWARE_PATTERNS = (
    (r"^(?P<owner>stepper_\w+)$", "stepper"),
    (r"^(?P<owner>manual_stepper\s+\S+)$", "manual stepper"),
    (r"^(?P<owner>extruder\d*)$", "extruder"),
    (r"^tmc\w+\s+(?P<owner>stepper_\w+|extruder\d*|manual_stepper\s+\S+)$", "driver"),
    (r"^(?P<owner>mcu(?:\s+\S+)?)$", "mcu"),
    (r"^(?P<owner>heater_bed)$", "heater"),
)
HARDWARE_RES = tuple((re.compile(pat), kind) for pat, kind in HARDWARE_PATTERNS)

# Klipper SAVE_CONFIG style backups and common editor/backup leftovers.
BACKUP_NAME_RE = re.compile(
    r"(\.bak(\.\S+)?$|\.jwp_bak(\.\S+)?$|\.orig$|\.old$|~$|^printer-\d{8}_\d+\.cfg$)", re.I
)
MANAGED_DIR_NAMES = ("jabberwocky_dist", "jabberwocky_quarantine", "jabberwocky_trash", ".jws_rollback_anchor")

SECTION_RE = re.compile(r"^\s*\[\s*([^\]\s]+)\s*\](?:\s*#.*)?$", re.M)

# Comment-Gate Aware Include Parser: Traps naked, user muted (#) and script-masked (#💤#) lines
INCLUDE_RE = re.compile(r"^\s*(?:#|#💤#)?\s*\[\s*include\s+(\S+)\s*\](?:\s*#.*)?$", re.M | re.I)

MACRO_RE = re.compile(r"^\s*\[\s*gcode_macro\s+([^\]\s]+)\s*\](?:\s*#.*)?$", re.M | re.I)
RENAME_RE = re.compile(r"^\s*rename_existing\s*:\s*(\S+)(?:\s*#.*)?$", re.M | re.I)

class IncludeNode:
    def __init__(self, file_path: str, parent=None):
        self.file_path = file_path
        self.parent = parent
        self.children = []
        self.macros = []

def get_clean_section_tokens() -> tuple:
    return (MASK_TAG, "#⚙️#", "#⚠️#", "#EOF")
#EOF
