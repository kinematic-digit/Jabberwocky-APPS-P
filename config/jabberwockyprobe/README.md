# Jabberwocky Probe 2.0 (JWP)

A high-reliability mechanical probe system for Klipper 3D printers. Fixed toolhead-mounted probe deployed and retracted by printer motion against a rear actuation tine—no servos, magnets, or manual docking.

---

## ⚡ Quickstart Guide (5 Minutes to First Print)

### Step 1 — Run the Preflight & Config Scrubber
Before adding JWP, run the standalone scanner to catch duplicate macros, legacy probe conflicts, and pin errors:
```bash
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py ~/printer_data/config/printer.cfg
```
*Review the generated `~/printer_data/config/jwp_hygiene_report.txt` in Mainsail/Fluidd. Resolve any `[!] BOOT-BLOCKER` or `[!] RUNTIME-ERROR` items before continuing.*

### Step 2 — Add the JWP Include
Add this single line to your `printer.cfg` (recommended after your stepper/mcu sections):
```ini
[include jabberwockyprobe/jwprobe_entry.cfg]
```
*(Keep your native `[stepper_x/y/z]` sections. Existing `[quad_gantry_level]`, `[z_tilt]`, and `[bed_mesh]` sections remain active machine geometry; preserve them until the optional leveling-envelope workflow below generates verified replacements.)*

**Persistent-data safety:** current JWP versions store live calibration in `~/printer_data/config/jwprobe_runtime_vars.cfg`, deliberately outside the deployable `jabberwockyprobe/` code folder. Updating/replacing that folder therefore cannot erase the machine profile or calibrated positions. If upgrading from an older version whose live `[save_variables]` file was `jabberwockyprobe/jwprobe_vars.cfg` and that file is still intact, copy/rename it to `~/printer_data/config/jwprobe_runtime_vars.cfg` before `FIRMWARE_RESTART` to retain the existing values. The in-folder `jwprobe_vars.cfg` is reference-only and must not be configured as the live database.

**Native leveling geometry is required, but first-time users do not need to guess probing bounds.** JWP loads safely when `[quad_gantry_level]`, `[z_tilt]`, or `[bed_mesh]` is absent and skips the missing feature. After Z calibration, the optional leveling-envelope workflow below visually verifies two diagonal plate locations, accounts for the configured probe X/Y offsets, and prints a copy-ready native configuration. Physical QGL `gantry_corners` or Z-Tilt `z_positions` must still come from the printer manufacturer/CAD because nozzle motion cannot measure where the Z drives attach.

### Step 3 — Set Your Probe Pin & Offsets
Open `jabberwockyprobe/jwprobe_hardware.cfg` and set the `pin:` and `x_offset`/`y_offset` for your toolhead board (e.g. `nhk:gpio10` for Nitehawk-36).

### Step 4 — Run the Onboarding Wizard in Console
Restart Klipper (`FIRMWARE_RESTART`), then follow the five-step console workflow. Step 5 visually verifies the installed plate position and generates native leveling/mesh geometry:

1. **Profile Machine:**
   ```
   JWP_SETUP_WIZARD          # (add AUTOZ=0 if you do not have a frame Z switch)
   ```
2. **Align Actuation Dock:**
   > **STOP — CREATE AT LEAST 20MM OF Z CLEARANCE BEFORE TYPING THE SCAN COMMAND.**
   >
   > First run `JWP_RELEASE_FOR_DOCK_CLEARANCE`. This explicit command issues `M84`; the wizard itself never releases or moves motors. Support the moving assembly, then manually **raise the gantry/nozzle** on a moving-gantry machine or **lower the bed** on a moving-bed Z machine such as a Trident. Ensure the nozzle and probe also clear the Auto-Z switch pin. The dock scan requires this one-session release handshake, checks for `probe: open` before any motion, then always performs a visibly announced fresh X/Y home. It deliberately does not home or move Z because the probe/dock calibration is not yet established. `Z_CLEAR=1` confirms that you physically verified clearance.
   - **Automated Hands-Free Scan (Recommended):**
     ```
     JWP_RELEASE_FOR_DOCK_CLEARANCE
     JWP_AUTO_ALIGN_DOCK Z_CLEAR=1  # Always stages 30mm clear, requires probe=open (manually deploy if prompted),
                                     # then performs a bounded low-current slow scan for an existing tine.
                                     # Found: saves both strikes. Not found: retreats and gives install instructions.
     ```
   - **Manual Step-by-Step Mode (Alternative):**
     ```
     JWP_ALIGN_ACTUATION_DOCK MODE=INSTALL Z_CLEAR=1     # Mount dock at rear center
     JWP_ALIGN_ACTUATION_DOCK MODE=RETRACT Z_CLEAR=1     # Nudge X until probe: TRIGGERED
     JWP_ALIGN_SAVE_POSITION
     JWP_ALIGN_ACTUATION_DOCK MODE=DEPLOY Z_CLEAR=1      # Nudge X until probe: open
     JWP_ALIGN_SAVE_POSITION
     JWP_ALIGN_FINISH
     ```
   - **Recalibrating later (or after lost saved data):** run `JWP_RELEASE_FOR_DOCK_CLEARANCE`, create the required clearance, then run `JWP_AUTO_ALIGN_DOCK Z_CLEAR=1`. It detects the physical tine with a bounded slow scan instead of trusting a saved flag, so no `INSTALLED=1`/`RECOVER=1` knowledge or remounting is needed. The manual `MODE=INSTALL` path remains available only when the scan confirms no tine was detected.
3. **Locate the Auto-Z Switch (Step 2; Auto-Z installations only):**
   ```
   JWP_ALIGN_AUTOZ_SWITCH
   JWP_ALIGN_SWITCH_NUDGE X=<mm> Y=<mm>  # Repeat as needed
   JWP_SAVE_AUTOZ_SWITCH_LOCATION
   JWP_VERIFY_AUTOZ_SWITCH_LOCATION
   ```
   If its exact XY is already known, use `JWP_SET_AUTOZ_SWITCH_LOCATION X=<mm> Y=<mm>` followed by `JWP_VERIFY_AUTOZ_SWITCH_LOCATION`.
4. **Validate Repeatability (Step 3):**
   ```
   JWP_TEST_REPEATABILITY
   JWP_CONFIRM_REPEATABILITY SPREAD=0.0060             # Example only: pass the exact reported range value
   ```
   A spread of `0.0030mm` or lower is ideal; `0.0031–0.0060mm` is acceptable. Results above `0.0060mm` fail onboarding and should trigger a mechanical inspection.
5. **Calibrate Offset (Step 4):**
   - **Auto-Z Installs:** Remove the sheet, cool the bed, unload filament, then run `JWP_MEASURE_PROBE_NOZZLE_OFFSET`. This one-time command derives the fixed probe-to-nozzle constant that `CALIBRATE_Z` reuses. Reinstall the sheet and run `CALIBRATE_Z`; successful calibration prints the Step 5 corner-check command. Pass `REDO=1` only after the probe or switch is physically remounted/replaced.
     - **Required once after upgrading from a build predating the frame-switch capture fix:** old saved probe/nozzle constants are deliberately rejected because they may contain the post-home safety-hop coordinate instead of the actual switch-trigger coordinate. Remove the build sheet, cool the bed, unload filament, then run `JWP_MEASURE_PROBE_NOZZLE_OFFSET REDO=1`; reinstall the sheet and run `CALIBRATE_Z`. `JWP_STATUS` reports `[RECALIBRATE]` until this is complete.
   - **Standalone Installs:** `DEPLOY_PROBE` → `PROBE_CALIBRATE` (paper test) → `ACCEPT` → `SAVE_CONFIG` → `RETRACT_PROBE`.

6. **Verify Bed Corners and Generate Leveling Geometry (Step 5, after Z calibration):**
   - Enter the real probe `x_offset`/`y_offset` in `jwprobe_hardware.cfg` before starting. JWP reads those values from Klipper; it never assumes the reference machine's `0,26` offset.
   - On an Auto-Z install, run `CALIBRATE_Z` in the current Klipper session first. The workflow refuses to move at an assumed Z height unless the sanity-checked Auto-Z correction was successfully applied.
   - Begin with the nominal build-plate size:
     ```
     JWP_ALIGN_BED_ENVELOPE PLATE_X=180 PLATE_Y=180
     ```
   - JWP retracts the probe and parks the nozzle near the front-right plate corner at a safe Z. Visually place the **nozzle** 5mm inside both plate edges using `JWP_BED_ENVELOPE_NUDGE X=<mm> Y=<mm>`, then run `JWP_SAVE_BED_CORNER`.
   - It moves diagonally from front-right to rear-left. This specific diagonal deliberately avoids sweeping across the front-left cutter-arm engagement zone. It also keeps the initial rear target outside the rear actuation-dock zone. Visually verify/nudge the rear-left corner and run `JWP_SAVE_BED_CORNER` again.
   - For a four-motor moving gantry, provide the two physical gantry corners from the printer manufacturer/CAD:
     ```
     JWP_GENERATE_LEVELING_CONFIG MODE=QGL GANTRY_MIN_X=-60 GANTRY_MIN_Y=-10 GANTRY_MAX_X=240 GANTRY_MAX_Y=240
     ```
     For a Z-Tilt machine, first run `JWP_GENERATE_LEVELING_CONFIG MODE=Z_TILT`; it prints the exact command syntax for supplying two to four physical Z-pivot positions. Use `MODE=MESH` when only bed mesh is needed.
   - In `printer.cfg`, replace the existing `[quad_gantry_level]`, `[z_tilt]`, and/or `[bed_mesh]` section(s) with the emitted text—do not keep both the old and new copies. Enable the matching optional JWP wrapper include(s), then `RESTART` and run `JWP_CONFIG_AUDIT`.

   The saved positions are visual checks 5mm inside the plate; JWP reconstructs the estimated plate edges, then applies a separate 20mm physical probing inset. Generated minimum nozzle coordinates also preserve the established JWP front-left cutter clearance (25mm from each axis minimum). JWP cannot discover QGL `gantry_corners` or Z-Tilt `z_positions`; those are physical Z-drive locations, not bed edges. Existing valid manufacturer values should be preserved.

### Step 6 — Add to `PRINT_START`
`JWP_PRINT_PREP` internally handles homing, Auto-Z, QGL/Z-Tilt, and Bed Mesh -- do **not** call `G28`, `QUAD_GANTRY_LEVEL`, `Z_TILT_ADJUST`, or `BED_MESH_CALIBRATE` yourself beforehand; JWP intercepts/wraps those commands and runs them internally in the correct order, with correct probe deploy/retract around each one. Remove those calls (and any old Klicky/legacy `G29`/`M420` leftovers) from your slicer's Start G-code entirely.

**Temperature ordering matters** for two reasons specific to this probe: (1) the fixed probe touches the bed for mesh/leveling, so the bed should already be at its *printing* temperature (thermal expansion affects the mesh) before that happens; (2) the Auto-Z step briefly touches the *nozzle* itself to a frame switch, so the hotend should still be cold/low at that point -- a fully-heated nozzle oozes onto the switch and can corrupt the touch reading. Recommended slicer `PRINT_START` structure:

```ini
[gcode_macro PRINT_START]
gcode:
    {% set bed_temp = params.BED_TEMP|default(60)|float %}
    {% set extruder_temp = params.EXTRUDER_TEMP|default(210)|float %}

    M140 S{bed_temp}                  ; start heating bed (non-blocking)
    M104 S150                          ; pre-heat nozzle to a safe, non-oozing standby temp
    M190 S{bed_temp}                  ; WAIT for full bed temp before probing/leveling
    JWP_PRINT_PREP                     ; homing + Auto-Z + QGL/Z-Tilt + Bed Mesh (nozzle still cool)
    M109 S{extruder_temp}             ; NOW wait for full nozzle temp, after all switch/bed touches are done
    ; ... your purge/prime line here ...
```

*Adjust `BED_TEMP=`/`EXTRUDER_TEMP=` to match whatever parameter names your slicer profile actually passes (PrusaSlicer/OrcaSlicer/SuperSlicer typically send these two; Cura/Bambu Studio use different names -- match your own Start G-code box).*

*Done! You are ready to print.*

---

## 📋 Quick Command Cheat Sheet

| Command | What it does |
|---|---|
| `JWP_STATUS` | Displays current onboarding & calibration status across all steps |
| `JWP_CONFIG_AUDIT` | Audits parsed configuration, active leveling modules, and legacy wrappers |
| `JWP_AUTO_ALIGN_DOCK Z_CLEAR=1` | Single-command dock discovery/alignment: stages clear, requires probe=open, slowly detects an existing tine and saves both strikes; if none is detected, retreats and gives installation instructions |
| `JWP_ALIGN_BED_ENVELOPE PLATE_X=<mm> PLATE_Y=<mm>` | After Z calibration, visually verifies two diagonal nozzle positions used to derive safe native leveling and mesh bounds |
| `JWP_BED_ENVELOPE_NUDGE X=<mm> Y=<mm>` / `JWP_SAVE_BED_CORNER` | Adjusts and saves each visual bed-envelope corner |
| `JWP_GENERATE_LEVELING_CONFIG MODE=QGL\|Z_TILT\|MESH` | Applies configured probe offsets and prints a copy-ready native Klipper configuration; physical gantry/Z-pivot coordinates remain required |
| `DEPLOY_PROBE` / `RETRACT_PROBE` | Manually deploys or retracts probe against the rear tine |
| `QUERY_PROBE` | Reports pin state (`open` = Deployed, `TRIGGERED` = Retracted) |
| `JWP_PRINT_PREP` | Smart print start routine (Auto-Z + QGL/Z-Tilt + Bed Mesh) |
| `TOGGLE_JWP_GANTRY_LEVELING` | Web button to enable/disable QGL or Z-Tilt during print prep |
| `TOGGLE_JWP_BED_MESH` | Web button to enable/disable bed mesh probing during print prep |
| `TOGGLE_JWP_REPEAT_PRINT_FAST_PATH` | Web button to enable/disable 15-minute quick trust window for back-to-back prints |

---

## 📖 Complete Technical Reference Manual

<details>
<summary><strong>1. Physical Mechanics & Probe State Truth Table (Click to expand)</strong></summary>

### How the Probe Works
The Jabberwocky Probe is a **mechanically actuated** sliding armature with two detented states (deployed and retracted). It changes state by driving the toolhead against a **single fixed tine** mounted at the rear center of the frame (`Y = bed_max_y`).

**The same physical X position sets either state, depending on approach direction:**
* **Retract:** Toolhead approaches from higher X moving in **−X** (pushes pin in, latches RETRACTED).
* **Deploy:** Toolhead approaches from lower X moving in **+X** (pushes pin out, latches DEPLOYED).

### Probe State Truth Table (Pin configured `^!`)
| Physical State | `QUERY_PROBE` reports | `printer.probe.last_query` |
|---|---|---|
| **Deployed** | `probe: open` / untriggered | `False` |
| **Retracted** | `probe: TRIGGERED` | `True` |

Macros always evaluate `live_deployed = not printer.probe.last_query` to verify physical contact rather than trusting cached software flags.
</details>

<details>
<summary><strong>2. Preflight & Hygiene Scrubber Details (by Kinematicdigit)</strong></summary>

The preflight tool (`tools/jwp_config_preflight.py`) operates outside Klipper to detect errors that would prevent Klipper from starting or cause mid-print movement aborts.

### Usage Options:
```bash
# Standard JWP Migration Scan:
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py ~/printer_data/config/printer.cfg

# Standalone General Klipper Audit (any printer):
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene ~/printer_data/config/printer.cfg

# Show Include Tree, Find Unreferenced Live .cfg Files, and List Active Macros:
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene --tree --find-orphans --macro-table ~/printer_data/config/printer.cfg

# Also Report G-code File Count/Disk Usage (gcodes folder auto-detected as a sibling of config/):
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene --gcode-stats ~/printer_data/config/printer.cfg

# Also Report Log Folder Size (logs folder auto-detected as a sibling of config/):
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene --log-stats ~/printer_data/config/printer.cfg

# Preview Moving Orphaned .cfg Files into orphan/ (dry run, moves nothing):
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene --find-orphans --quarantine-orphans ~/printer_data/config/printer.cfg

# Actually Move Orphaned .cfg Files into orphan/ (subdirectory layout preserved):
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene --find-orphans --quarantine-orphans --confirm ~/printer_data/config/printer.cfg

# Preview Moving Disabled (commented-include) Files into disabled/, and Backup/Hidden Files into backup_review/ (dry run):
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene --find-orphans --quarantine-disabled --quarantine-filtered ~/printer_data/config/printer.cfg

# Actually Move Disabled and Backup/Hidden Files for review (subdirectory layout preserved):
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene --find-orphans --quarantine-disabled --quarantine-filtered --confirm ~/printer_data/config/printer.cfg
```

`--find-orphans` excludes clearly archival copies (paths containing `archive`/`backup`, filenames containing `.bak`, `bak`, `_old`, `_orig`, or `_copy`, and Moonraker's automatic "Save & Restart" timestamp backups like `printer-20250730_072747.cfg`). It also distinguishes a file whose only reference is a commented-out `[include ...]` line -- reported as `[DISABLED]` (intentionally turned off, not abandoned) instead of `[INFO]` -- and separately flags a `[WARN] Dangling Commented-Out Include` when a commented-out `[include ...]` points at a file that no longer exists at all (a stale reference left behind after deleting the file). `--macro-table` lists active `gcode_macro` and `delayed_gcode` definitions grouped by the included `.cfg` file that defines them. `--gcode-stats` reports total G-code file count, combined size, the largest files, and free disk space in the `gcodes` folder (use `--gcode-dir` to point at a non-standard location) -- useful for spotting a nearly-full SD card/disk before it halts a print. `--log-stats` reports the same for the `logs` folder (use `--log-dir` to override), broken out into rotated log backups (`klippy.log.1`, `.2`, ...) and Moonraker crash-dump `.zip` archives, both of which are safe to delete manually. `--quarantine-orphans` moves files found by `--find-orphans` into an `orphan/` folder inside the config directory, preserving their original subdirectory layout (e.g. `config/old/foo.cfg` -> `config/orphan/old/foo.cfg`); it is a dry run by default (prints the planned moves) -- pass `--confirm` to actually move the files. Files once quarantined are excluded from future orphan scans so they are not re-flagged or nested repeatedly.

`--find-orphans` also separately reports (but does not count as true orphans) archival/backup-named files (`[FILTERED]`, previously silently dropped with no visibility at all) and hidden dotfiles whose name starts with `.` (`[HIDDEN]`, typically editor swap/backup artifacts) -- both are candidates worth reviewing for deletion. `--quarantine-disabled` moves files whose only reference is a commented-out `[include ...]` into a `disabled/` folder, kept separate from true orphans since they may be re-enabled later (uncomment the include and move the file back). `--quarantine-filtered` moves both `[FILTERED]` and `[HIDDEN]` files into a `backup_review/` folder for deletion consideration. Both new flags follow the same dry-run-by-default + `--confirm` pattern as `--quarantine-orphans`, and their destination folders are likewise excluded from future scans.

**Report formatting:** every major section now prints a thin divider line under its `=== Header ===`, and any section whose findings can be acted on (duplicate macros, orphans/disabled/filtered/hidden files, quarantine moves, rename_existing wrappers, gcode/log storage, syntax issues, etc.) includes a short one-line note on how to fix or move what's listed -- e.g. "Move for review with --quarantine-orphans (add --confirm to actually move)". Inside `--find-orphans`, the four file categories (disabled / unreferenced / filtered / hidden) are each grouped under their own `--- Subsection ---` divider with the matching note, and a one-line `Summary: N disabled, N unreferenced, N filtered, N hidden` count sits right under the section header before any individual file paths are listed.

**Rotating-backup collapsing:** any file listing that could realistically contain repeated auto-backups -- `--find-orphans`'s filtered/hidden listings and all three `--quarantine-*` preview/moved listings -- collapses 3 or more files that only differ by a trailing date/serial suffix (e.g. Moonraker/Mainsail's own `printer-20240803_144219.cfg` save-triggered backups, or hand-numbered `foo_bak`/`foo_bak2`/`foo_bak3.cfg`) into a single line, e.g. `[FILTERED] 5x rotating backup files matching 'printer*.cfg' (oldest: ..., newest: ...)`. Groups of 1 or 2 are still listed individually. This only changes what's *displayed* -- quarantine moves still act on every real file in the group, none are skipped.

**Duplicate origin/duplicate tagging:** each duplicate `[section]` or `gcode_macro` finding now lists every location on its own line, tagged `[ORIGIN]` for the first copy the scanner reaches while following your include order, and `[DUPLICATE]` for every later copy -- so you can tell at a glance which file is most likely the one to keep and which are the copies worth renaming or deleting. This is a heuristic based on include order, not a guarantee of which copy is "correct" -- always check the actual macro/section content before deleting.

**Report section order:** the report now runs Hardware Profile -> Legend -> Include Ordering Hygiene -> Macro Table -> `rename_existing` Wrappers -> Orphaned/Disabled/Filtered/Hidden Files -> Dangling Includes -> final PASS/NOT READY summary. The orphan/disabled/filtered/hidden file listings (lower priority, mostly informational) were moved near the bottom, after the `rename_existing` wrappers section (higher priority, since unexpected wrappers can indicate macro conflicts).

**Risky/deprecated G-code command detection:** the scanner now scans every `gcode_macro`/`delayed_gcode` body (across the whole include tree) for known commands that bypass Klipper's normal kinematic limits, homing state, or position tracking -- `FORCE_MOVE`, `SET_KINEMATIC_POSITION`, `STEPPER_BUZZ`, `SET_STEPPER`, and `M302 ... P1` (the cold-extrusion safety override). These are meant for manual bench calibration/wiring bring-up only; finding one still wired into a macro that runs automatically (print-start, homing overrides, probe alignment, etc.) is a common sign of leftover debug/bench-testing code that never got cleaned up. Each finding is reported under `=== Risky / Deprecated G-code Commands In Macros ===` (placed right after the duplicate-macro checks, since this is actionable safety content, not low-priority housekeeping) grouped by the macro and file it was found in, with the exact line, the command, and a short reason why it's flagged. This is a fixed, deliberately conservative command list -- it does not attempt to catch every possible risky pattern, only ones Klipper's own docs single out as bypass-safety-checks/manual-only.

**Hardware & Calibration Sanity Checks:** a dedicated section, `=== Hardware & Calibration Sanity Checks ===`, deliberately kept separate from `=== Include Ordering, Structural, Pin & Kinematic Hygiene ===` -- the latter is about the *layout/structure* of the config (include order, duplicate sections, pin collisions, travel bounds), while this one is about *values* that are syntactically fine but numerically suspicious or stale left over from bring-up/calibration:
- **TMC current sanity:** flags `run_current`/`hold_current` outside a plausible Amps range (e.g. a datasheet mA value like `1500` pasted in place of `1.5`), and `hold_current` set higher than `run_current` (unusual -- idle current is normally lower).
- **`autotune_tmc` vs. manual current conflict:** if an `[autotune_tmc <stepper>]` section is active for a stepper that also has a manually-set `run_current` in its `[tmcXXXX <stepper>]` section, autotune_tmc recalculates current at runtime and silently overrides the manual value -- flagged so you know why changing `run_current` "does nothing."
- **PID tuning staleness:** any `[extruder]`, `[heater_bed]`, `[heater_generic ...]`, or `[temperature_fan ...]` section with `control: pid` is checked for missing `pid_Kp/Ki/Kd` (never tuned) or for the exact `Kp=1.0 Ki=0.5 Kd=2.0` placeholder values from Klipper's example config (strong sign `PID_CALIBRATE` was never actually run, or the tuned values were lost).
- **Orphaned `SAVE_CONFIG` entries:** a section with saved values in the auto-generated `SAVE_CONFIG` block but no matching manually-authored `[section]` anywhere (commonly left behind after removing/renaming hardware) is flagged as safe to delete from that block. Sections Klipper legitimately only ever saves (`[input_shaper]`, `[axis_twist_compensation]`, `[bed_mesh <profile>]`, etc.) are whitelisted so this never false-positives on a normal install.

Fixing these checks also required teaching the scanner to actually parse the `#*#`-prefixed `SAVE_CONFIG` block: it previously treated every `#*#` line as a plain comment (and used a `:`-based option pattern that doesn't match the block's `key = value` syntax), so the existing "manual value also has saved values" shadowing check had never actually been able to fire. It now parses `[section]` headers and `key = value` options inside that block correctly.

**Report revision & citation:** every report now opens with a revision line (`Revision r<N> (updated <date>) -- Report generated <timestamp>`) and an author/project line (`Author / Maintainer: Kinematicdigit (Jabberwocky Team) -- <project URL>`), so a report can always be tied back to the exact scanner build that produced it.

**Scan Result Summary (5-point score):** a scored summary banner is spliced in near the top of every report (right after the hardware profile/legend, before any detail sections) once the full scan completes, so you see the headline result before scrolling through details. Worst-to-best, first match wins: **1/5 Blockers found** (Klipper will fail to start or run unsafely), **2/5 Warnings/info to review** (non-fatal issues worth a look), **3/5 Clean, but duplicate/orphan file(s) present** (non-blocking duplicates or `--find-orphans` unreferenced files), **4/5 Clean, with commented-out include(s)** (only disabled `[include ...]` lines found), **5/5 Perfect (excluding relocated files)** (nothing above applies; filtered/hidden/backup-named files never count against the score since they're advisory-only). A "What was scanned" checklist under the score shows every check category run and whether it came back 100% clean or found N finding(s), so a passing section is acknowledged explicitly rather than only implied by its absence.

**Print / Pause / Cancel / Resume Lifecycle Hygiene:** a dedicated section, `=== Print / Pause / Cancel / Resume Lifecycle Hygiene ===`, that reads directly into the body of every `PRINT_START`/`START_PRINT`, `PRINT_END`/`END_PRINT`/`CANCEL_PRINT`, `PAUSE`/`M600`, and `RESUME` macro (not just their option key/value pairs) to catch problems that only show up in the actual g-code sequence:
- **Missing end-of-job shutdown steps:** `PRINT_END`/`END_PRINT`/`CANCEL_PRINT` are checked for `TURN_OFF_HEATERS` (or `M104`/`M140 S0`) and a fan-off (`M107`/`M106 S0`) -- heaters left on wastes power and heat-soaks the machine unattended.
- **Immediate motor-disable vs. JWP's quick-reprint/rescan workflow:** on a probe-equipped machine like JWP, an immediate `M84`/`M18` in `PRINT_END`/`CANCEL_PRINT` is flagged as an `[INFO]` recommendation to *remove* it, not add it -- disabling steppers right away forces Klipper to treat the axes as unhomed again, throwing away dock-alignment confidence and forcing a full re-home before the next quick reprint/rescan. The intended behavior is to let Klipper's own `[idle_timeout]` release the motors after a real idle period instead.
- **`[idle_timeout]` duration sanity:** the scanner reads your actual configured `timeout:` (or notes that no `[idle_timeout]` section exists, in which case Klipper's 600s/10-minute built-in default applies) and recommends a ~1800s (30 minute) sweet spot for JWP's workflow -- long enough to survive normal quick-reprint/rescan turnaround without forcing a re-home, short enough not to hold power/heat all day. Flagged `[WARN]` if under 900s (15 min, likely to release mid-turnaround) or over 3600s (60 min, needlessly wastes power/heat), and `[INFO]` if no `[idle_timeout]` section exists at all.
- **A `PAUSE`/`M600` that disables steppers:** flagged as a real bug -- doing so during a resumable pause loses the toolhead's tracked position, so `RESUME` can no longer safely continue. Motor-disable only belongs in `PRINT_END`/`CANCEL_PRINT`.
- **Unguarded optional-hardware calls:** bare calls to plugin/module-provided commands (`MMU_END`, `CARTOGRAPHER_TOUCH`, `set_case_light_on`/`off`, `status_*` LED macros, `START_IDLE_RAINBOW`) with no surrounding `{% if 'x' in printer %}` guard -- these raise "Unknown command" the instant the macro runs on a printer without that module, even though the config still loads fine.
- **Leftover slicer placeholder syntax:** bracket-style tokens like `[nozzle_temperature_initial_layer]` or `[bed_mesh_algo]` (PrusaSlicer/SuperSlicer/OrcaSlicer) and curly tokens like `{material_bed_temperature}` (Cura) are only ever substituted inside the *slicer's own* Start/End G-code text box -- finding one literally inside a `.cfg` file is almost always a wiki example pasted into the wrong place, and the scanner names which slicer's syntax it recognizes.
- **Chamber/case light left on:** if any `PRINT_START`/`START_PRINT` definition calls `set_case_light_on` but no `PRINT_END`/`CANCEL_PRINT`/`PAUSE` macro anywhere ever calls `set_case_light_off`, it's flagged as a suggestion to add the matching off-call.
- **Back-to-back duplicate lines:** an identical command repeated twice in a row with nothing in between (e.g. two `M400`s) -- almost always a harmless but pointless leftover, safe to remove one copy.
- **Inconsistent `PRINT_START` parameter naming:** if multiple `PRINT_START`/`START_PRINT` definitions exist (e.g. one from a bench-test file, one from the "real" macro set) and they expect different slicer parameter names (`BED_TEMP`/`HOTEND_TEMP` vs. `BED`/`EXTRUDER`), whichever one actually loads silently falls back to its own default temperature if the slicer's real Start G-code call uses the other naming scheme -- flagged so the mismatch doesn't go unnoticed.

**Print Start/End G-code: Slicer Compatibility & Deprecated Command Hygiene:** a dedicated section that scans `PRINT_START`/`START_PRINT`/`PRINT_END`/`END_PRINT`/`CANCEL_PRINT` macro bodies for legacy Marlin/RepRapFirmware commands Klipper doesn't implement natively -- `G29`, `M420`, `M900`, `M572`, `M203`, `M201`, `M205`, `M907`. A hit with no matching `[gcode_macro <NAME>]` shim defined anywhere in the config is flagged `[!] RUNTIME-ERROR` (Klipper raises "Unknown command" the instant that line runs); a hit that IS shimmed is downgraded to `[INFO]` (verify the shim actually does what you expect). When any legacy command is found, the section also appends a one-time reference note on how the top three slicers (PrusaSlicer/SuperSlicer/OrcaSlicer, Cura, Bambu Studio) customarily integrate with a Klipper `PRINT_START`/`PRINT_END` macro pair -- this can't be verified against the `.cfg` itself, since a slicer's own Start/End G-code lives in the slicer profile, never in a config file.

### Report Status Legend:
* **`[!] BOOT-BLOCKER`**: Klipper will fail to start/connect (e.g. duplicate `[probe]`, duplicate macros, MCU pin collisions, includes inside `SAVE_CONFIG`).
* **`[!] RUNTIME-ERROR`**: Configuration boots, but homing/probing/mesh moves will abort or crash (e.g. probe offset travel conflicts with `mesh_min` / `position_min`).
* **`[WARN]`**: Action recommended (e.g. active legacy probe config to remove, missing `[respond]`).
* **`[INFO]`**: Non-fatal notice/awareness (optional modules, normal wrappers).
* **`[KEEP]`**: Native hardware verified. Retain this native configuration in `printer.cfg`.
* **`[OK]`**: Check passed.
</details>

<details>
<summary><strong>3. Web UI Dashboard Button Overrides (Mainsail & Fluidd)</strong></summary>

Mainsail and Fluidd dashboard buttons execute raw Klipper commands (`QUAD_GANTRY_LEVEL`, `BED_MESH_CALIBRATE`, `Z_TILT_ADJUST`). To make these buttons automatically deploy and retract the Jabberwocky Probe without manual intervention, uncomment the corresponding include lines in `jabberwockyprobe/jwprobe_entry.cfg`:

```ini
[include jwprobe_qgl.cfg]         # Hooks Mainsail/Fluidd QGL button
[include jwprobe_bed_mesh.cfg]    # Hooks Mainsail/Fluidd Bed Mesh button
[include jwprobe_z_tilt.cfg]     # Hooks Mainsail/Fluidd Z-Tilt button
```

*Note: If your printer lacks a 4-motor gantry or mesh leveling, leave these lines commented; JWP automatically detects absent modules and skips them.*

*Compared to Klicky-Probe (see `macros/debug/config/Klicky/klicky-quad-gantry-level.cfg`): Klicky's QGL button override uses the exact same core mechanism as `jwprobe_qgl.cfg` -- `[gcode_macro QUAD_GANTRY_LEVEL]` with `rename_existing:` pointing at a renamed copy of the native command, so Mainsail/Fluidd's QGL button (and any raw `QUAD_GANTRY_LEVEL` g-code) is transparently intercepted regardless of trigger source. JWP's version forwards the original command's params with `{rawparams}` (a single, order-preserving passthrough) rather than Klicky's manual `{% for p in params %}...{% endfor %}` reconstruction, which is the more robust of the two approaches. Note Klicky's own probe attach/dock calls in that reference file are commented out (`#Attach_Probe` / `#Dock_Probe`) -- JWP's unconditional `DEPLOY_PROBE` call (see comment in `jwprobe_qgl.cfg`) is the actively-maintained equivalent. Because `rename_existing` targets are bound at Klipper's `klippy:connect` stage (after all config sections load), include order relative to your native `[quad_gantry_level]` section does not matter -- but declaring `[gcode_macro QUAD_GANTRY_LEVEL]` twice (e.g. leaving an old Klicky QGL override file included alongside `jwprobe_qgl.cfg`) is a hard duplicate-section config error at boot, not a silent override. If your `QUAD_GANTRY_LEVEL` command still appears to run stock/native behavior with no boot error, the most common cause is simply that `[include jwprobe_qgl.cfg]` is still commented out in your `jwprobe_entry.cfg` -- check that first, then run `FIRMWARE_RESTART` after uncommenting it.*

**Known UX gap — heightmap/mesh-viewer panel "Home" icon:** Mainsail's/Fluidd's dedicated Bed Mesh heightmap panel has its own small home/reset icon in its own toolbar. This is *not* the same as the main dashboard's "Home All" button -- it's a hardcoded frontend action that sends a raw `G28 X Y` (no Z) directly. Even though JWP's `[homing_override]` now captures every `G28` call including this one (see below), the result is the same by design: an `X Y`-only request still only homes `X`/`Y` and leaves `Z` unhomed, because forcing `Z` into every partial home would be wrong behavior, not a fix. If you need `Z` homed before using that panel, run a plain `G28` first (console or main dashboard), then open the heightmap panel.

*Compared to Klicky-Probe (see `macros/debug/config/Klicky/klicky-macros.cfg`): Klicky's `[homing_override]` uses `axes: xyz` (captures every `G28` call, full or partial) rather than being scoped to a single axis. JWP's `jwprobe_homing.cfg` now matches this: `axes: xyz`, parsing `'X'/'Y'/'Z' in params` the same way Klicky does, so JWP has visibility into and control over every homing request (a bare `G28` still means "home everything," matching stock semantics). Any request that includes `Z` is routed through JWP's real Auto-Z switch-travel sequence rather than a plain `G28 Z`; requests that don't include `Z` only home the axes actually named -- exactly matching Klicky's own params-parsing behavior, and consistent with the heightmap-panel note above.*
</details>

<details>
<summary><strong>4. Configuration Ownership: What to Keep vs Remove</strong></summary>

| Keep in assembled Klipper config | Remove from assembled Klipper config | Configured in JWP |
|---|---|---|
| `[stepper_x]`, `[stepper_y]`, `[stepper_z]`, MCUs, heaters, fans, kinematics | Old Klicky/Euclid `DEPLOY_PROBE`, `RETRACT_PROBE`, `ATTACH_PROBE`, `DOCK_PROBE` | `jwprobe_hardware.cfg` (`[probe]` pin & offsets) |
| Native `[quad_gantry_level]`, `[z_tilt]`, `[bed_mesh]` coordinate sections, directly in `printer.cfg` | Old macro overrides that `rename_existing` leveling commands to dock/undock | `jwprobe_globals.cfg` (speeds, currents, tolerances) |
| Slicer `PRINT_START` / `PRINT_END` | Extra copies of JWP variables or saved coordinates | `jwprobe_runtime_vars.cfg` (auto-persisted calibration, managed by Klipper) |
</details>

<details>
<summary><strong>5. Smart Print-Prep Routing & Repeat-Print Fast Path</strong></summary>

### Intelligent Decision Flow
`JWP_PRINT_PREP` handles print startup intelligently:
1. **Full Calibration Flow (Default):** Runs Auto-Z sanity check → Smart QGL/Z-Tilt (if configured) → Fresh Bed Mesh (if configured) → Sets final nozzle Z-offset.
2. **Repeat-Print Fast Path (Optional):** When enabled via `TOGGLE_JWP_REPEAT_PRINT_FAST_PATH`, back-to-back prints within the trust window (default: 900s / 15 min) perform a rapid Auto-Z delta check. If drift is `< 0.050mm`, redundant QGL and full bed mesh probing are skipped, cutting print startup time to seconds.

A passing `JWP_TEST_REPEATABILITY` result is required to trust Auto-Z, but it does **not** by itself enable a fast path or skip QGL/mesh. The explicit repeat-print toggle above is the only mechanism allowed to skip fresh leveling/mesh work.

### Diagnostic Tools (Optional Buttons)
| Macro Button | Function |
|---|---|
| `JWP_DIAG_BED_THERMAL` | Measures center bed Z expansion from cold to hot |
| `JWP_DIAG_MESH_BARE_COLD` / `_HOT` | Captures bed mesh profile on bare aluminum cold vs heated |
| `JWP_DIAG_MESH_SHEET_COLD` / `_HOT` | Captures bed mesh profile on build sheet cold vs heated |
</details>

<details>
<summary><strong>6. Where Configuration & Calibration Data Lives</strong></summary>

| Data | File Location | Survives Updates? |
|---|---|---|
| Calibration results (profile, dock strikes, switch coordinates, offsets, repeatability) | `~/printer_data/config/jwprobe_runtime_vars.cfg` | **Yes** (Persisted via `SAVE_VARIABLE`, outside the deployable JWP folder so updates cannot overwrite it) |
| Native QGL/Z-Tilt geometry and bed-mesh configuration | `~/printer_data/config/printer.cfg` | **Yes** (User-owned, outside the deployable JWP folder) |
| Hardware pin & probe offsets | `~/printer_data/config/jabberwockyprobe/jwprobe_hardware.cfg` | User editable |
| Speeds, currents, overshoot tolerances, trust windows | `~/printer_data/config/jabberwockyprobe/jwprobe_globals.cfg` | Framework defaults |
</details>
