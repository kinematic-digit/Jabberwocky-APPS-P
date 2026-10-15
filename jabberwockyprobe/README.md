# Jabberwocky Probe 2.0 (JWP) User Guide & Operator Reference (Part 1)

A high-reliability mechanical probe system for Klipper 3D printers. Fixed toolhead-mounted probe deployed and retracted by printer motion against a rear actuation tine—no servos, magnets, or manual docking.

---

## ⚡ Quickstart Guide (5 Minutes to First Print)

### Step 1 — Run the Preflight & Config Scrubber
Before adding JWP, run the standalone scanner to catch duplicate macros, legacy probe conflicts, and pin errors:
```bash
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py ~/printer_data/config/printer.cfg
```
*Review the generated `~/printer_data/config/jwp_hygiene_report.txt` in Mainsail/Fluidd. Resolve any `[!] BOOT-BLOCKER` or `[!] RUNTIME-ERROR` items before continuing.*

### Step 2 — Install JWP
Use **Install / Update JWP** in the APPS Curses installer. It deploys the package,
adds the master include when needed, and manages QGL / bed-mesh wrappers only
when the matching native sections are configured. It preserves unrelated
`printer.cfg` content and backs up changes. Existing native leveling geometry
remains machine-owned; do not replace it unless you have verified replacement
values.

**Persistent-data safety:** JWP stores live calibration in `~/printer_data/config/jwprobe_runtime_vars.cfg`, outside the deployable code folder. The installer updates code while preserving hardware bindings, user globals, and runtime data. A legacy-only runtime file is copied byte-for-byte to the canonical path and retained as a recovery copy. Fresh installs create an empty `[Variables]` store only when needed; the `jwprobe_vars.cfg` seed is never installed as live data. If both paths exist without a verifiable migration record, installation stops and preserves both.

**Leveling Blueprint Isolation:** JWP loads safely even if `[quad_gantry_level]`, `[z_tilt]`, or `[bed_mesh]` blocks are missing from your configuration by gracefully skipping unconfigured features. After Z calibration is established, the optional leveling-envelope macro visually logs your real plate margins, accounts for your toolhead's active X/Y probe offsets, and outputs copy-ready native layout blocks. Physical `gantry_corners` or `z_positions` parameters must still come from manufacturer specifications or CAD files, as nozzle contact cannot map structural drive pivot points.

### Step 3 — Set Your Probe Pin & Offsets
Open `jabberwockyprobe/jwprobe_hardware.cfg` and configure the hardware target pin and positional offsets matching your toolhead board (e.g., `pin: ^!nhk:gpio10` for an inverted, pull-up configuration on the LDO Nitehawk-36).

### Step 4 — Run the Onboarding Wizard in Console
Restart Klipper (`FIRMWARE_RESTART`), then follow the structural five-step console deployment path. Step 5 visually calibrates your exact plate boundaries and outputs native leveling/mesh envelopes:

1. **Profile Machine:**
   ```gcode
   JWP_SETUP_WIZARD          # (Append AUTOZ=0 if your machine lacks a dedicated frame Z switch)
   ```
2. **Align Actuation Dock:**
   > ⚠️ **CRITICAL: EXERCISE ABSOLUTE PHYSICAL VIGILANCE. CREATE AT LEAST 20MM OF Z CLEARANCE BEFORE EXECUTING MOVEMENT ROUTINES.**
   >
   > First execute `JWP_RELEASE_FOR_DOCK_CLEARANCE`. This explicit safety gate issues `M84` and prints instructions; the wizard will never drop motor torque or actuate axes as an implicit side effect. Manually raise the gantry (or lower the bed on moving-bed mechanics like the Trident) to guarantee that the nozzle, probe arm, and collision plunger clear the Auto-Z switch pin. The automated dock scan consumes a one-session verification handshake, runs a stationary `QUERY_PROBE` to confirm an open state, then performs an explicit, announced `G28 X Y` home. It deliberately avoids Z axis motion since spatial calibrations are not yet verified. `Z_CLEAR=1` acts as your legal software affirmation that physical bounds are safe.
   - **Automated Hands-Free Scan (Recommended):**
     ```gcode
     JWP_RELEASE_FOR_DOCK_CLEARANCE
     JWP_AUTO_ALIGN_DOCK Z_CLEAR=1  # Stages clear, verifies probe: open, and slow-scans to locate the physical tine.
                                     # Success auto-persists both strike locations.
     ```
   - **Manual Calibration Path (Alternative Debug Mode):**
     ```gcode
     JWP_ALIGN_ACTUATION_DOCK MODE=INSTALL Z_CLEAR=1     # Positions toolhead to mount the physical dock at rear center
     JWP_ALIGN_ACTUATION_DOCK MODE=RETRACT Z_CLEAR=1     # Step-nudge X until console reports probe: TRIGGERED
     JWP_ALIGN_SAVE_POSITION
     JWP_ALIGN_ACTUATION_DOCK MODE=DEPLOY Z_CLEAR=1      # Step-nudge X until console reports probe: open
     JWP_ALIGN_SAVE_POSITION
     JWP_ALIGN_FINISH
     ```
   - **Maintenance Realignment:** If structural work occurs or data is lost, execute `JWP_RELEASE_FOR_DOCK_CLEARANCE` followed by `JWP_AUTO_ALIGN_DOCK Z_CLEAR=1`. The script sweeps the area to find the tine dynamically without relying on old software flags, completely eliminating manual guessing.

3. **Locate the Auto-Z Switch (Step 2; Auto-Z installations only):**
   ```gcode
   JWP_ALIGN_AUTOZ_SWITCH
   JWP_ALIGN_SWITCH_NUDGE X=<mm> Y=<mm>  # Repeat incremental adjustments as needed
   JWP_SAVE_AUTOZ_SWITCH_LOCATION
   JWP_VERIFY_AUTOZ_SWITCH_LOCATION      # Executes a real G28 Z over the switch to confirm physical trigger
   ```
   If exact mechanical coordinates are already documented, bypass manual jogging via `JWP_SET_AUTOZ_SWITCH_LOCATION X=<mm> Y=<mm>` followed by `JWP_VERIFY_AUTOZ_SWITCH_LOCATION`.

4. **Validate Repeatability (Step 3):**
   ```gcode
   JWP_TEST_REPEATABILITY
   JWP_CONFIRM_REPEATABILITY SPREAD=0.0042             # Pass the exact statistical range reported by the terminal
   ```
   An install spread under `0.0030mm` is ideal; up to `0.0060mm` is the absolute ceiling to pass the onboard lock. Values exceeding `0.0060mm` throw a hard gate refusal, signaling mechanical issues, loose linkages, or structural play.

5. **Calibrate Absolute Offset (Step 4):**
   - **Auto-Z Installations:** Remove your flexible print sheet, clear any filament from the nozzle tip, let the bed cool completely to ambient, then execute `JWP_MEASURE_PROBE_NOZZLE_OFFSET`. This derives the immutable mechanical constant mapping your nozzle-to-probe gap over a rigid bare bed. Reinstall your sheet and run `CALIBRATE_Z` to validate the live workspace.
     - *Upgrade Precaution:* Upgrading from ancestral JWP releases requires running `JWP_MEASURE_PROBE_NOZZLE_OFFSET REDO=1` on a bare, cold bed to clear invalid legacy positions that may have captured post-trigger safety hops.
   - **Standalone Deployments:** `DEPLOY_PROBE` → `PROBE_CALIBRATE` (Standard paper test) → `ACCEPT` → `SAVE_CONFIG` → `RETRACT_PROBE`.

6. **Verify Bed Corners and Generate Leveling Geometry (Step 5):**
   - Ensure your toolhead's real probe offsets are accurately saved in `jwprobe_hardware.cfg` before initializing. JWP polls Klipper directly; it never relies on default placeholder metrics.
   - For Auto-Z setups, a successful `CALIBRATE_Z` pass must have occurred within the active Klipper session. The routing matrix will refuse motion tracking unless a valid correction layer is loaded.
   - Initialize using your nominal bed size:
     ```gcode
     JWP_ALIGN_BED_ENVELOPE PLATE_X=180 PLATE_Y=180
     ```
   - JWP stows the probe arm and transits the nozzle to the front-right plate boundary at a safe elevation. Jog the nozzle exactly 5mm inside both visible edges via `JWP_BED_ENVELOPE_NUDGE X=<mm> Y=<mm>` and commit via `JWP_SAVE_BED_CORNER`.
   - The toolhead executes an automated axial movement, shifting diagonally to the rear-left corner. This path safely bypasses the front-left cutter engagement array and avoids traveling within the rear 10mm actuation dock zone. Verify or adjust the alignment, then execute `JWP_SAVE_BED_CORNER` a final time.
   - Generate your optimized configuration block. For four-motor systems, append your structural parameters:
     ```gcode
     JWP_GENERATE_LEVELING_CONFIG MODE=QGL GANTRY_MIN_X=-60 GANTRY_MIN_Y=-10 GANTRY_MAX_X=240 GANTRY_MAX_Y=240
     ```
     For Z-Tilt architectures, run `JWP_GENERATE_LEVELING_CONFIG MODE=Z_TILT` to fetch your tailored input parameter layout. Paste the terminal output directly into your `printer.cfg`, replacing legacy `[quad_gantry_level]`, `[z_tilt]`, or `[bed_mesh]` blocks. Uncomment your clean matching wrapper inclusion line in `jwprobe_entry.cfg` and run a `JWP_CONFIG_AUDIT`.

### Step 6 — Streamline Your `PRINT_START` Routine
`JWP_PRINT_PREP` acts as your public slicer entry point, internally coordinating homing, Auto-Z calibration, gantry leveling, and bed mesh creation. **Do not embed manual `G28`, `QUAD_GANTRY_LEVEL`, or `BED_MESH_CALIBRATE` calls in your slicer text boxes.** Strip all legacy probe wrappers, Klicky attachments, or outdated `G29`/`M420` tracking loops from your slicer profile.

**Thermal Scheduling Rules:** To safeguard your hardware, organize your start script to manage thermal expansion sequentially:
1. Bring the heated bed to its final targeted printing temperature first to allow the frame to settle before any leveling or probing occurs.
2. Maintain the hotend at a restricted, non-oozing standby thermal threshold (e.g., 150°C) during initial touch-offs. A fully heated nozzle will bleed molten plastic onto the Auto-Z switch pin, corrupting metrology results.

```ini
[gcode_macro PRINT_START]
gcode:
    {% set bed_temp = params.BED_TEMP|default(60)|float %}
    {% set extruder_temp = params.EXTRUDER_TEMP|default(210)|float %}

    M140 S{bed_temp}                  ; Initialize bed heating loop (Non-blocking)
    M104 S150                          ; Pre-heat nozzle to safe, non-oozing standby threshold
    M190 S{bed_temp}                  ; Wait for bed mass to fully heat stabilize
    JWP_PRINT_PREP                     ; Coordinates Homing + Auto-Z + QGL/Z-Tilt + Mesh Probing (Nozzle is cool)
    M109 S{extruder_temp}             ; Bring hotend to final printing temperature once all physical switch touches conclude
    # ... Insert your primary purge line or nozzle prime path here ...
```

## 📋 Quick Command Cheat Sheet

| Command | Operational Definition / Functional Scope |
|---|---|
| `JWP_STATUS` | Displays live onboarding verification records and active calibration layers across all steps. |
| `JWP_CONFIG_AUDIT` | Programmatically parses active configuration variables to identify legacy overrides or wrapper conflicts. |
| `JWP_AUTO_ALIGN_DOCK Z_CLEAR=1` | Orchestrates a hands-free dock scan, locating the physical rear tine and mapping strike limits via low current loops. |
| `JWP_ALIGN_BED_ENVELOPE` | Initializes an interactive tool tracking visual plate boundaries to generate safe probing limits. |
| `JWP_BED_ENVELOPE_NUDGE` / `JWP_SAVE_BED_CORNER` | Modifies and locks in coordinate profiles for individual bounding layout corners. |
| `JWP_GENERATE_LEVELING_CONFIG` | Combines probe geometries to generate code blocks for native Klipper leveling systems. |
| `DEPLOY_PROBE` / `RETRACT_PROBE` | Manual physical actuation wrappers used to drive the toolhead carriage against the rear center tine. |
| `QUERY_PROBE` | Prints the active logical state of the toolhead line (`probe: open` = Deployed / `probe: TRIGGERED` = Retracted). |
| `JWP_PRINT_PREP` | Primary print-prep routing engine, executing watchdogs and scheduling automated calibration phases. |
| `TOGGLE_JWP_GANTRY_LEVELING` | Interface macro button to toggle gantry leveling routines within the print prep sequence. |
| `TOGGLE_JWP_BED_MESH` | Interface macro button to toggle automated bed mesh generation within the print prep sequence. |
| `TOGGLE_JWP_REPEAT_PRINT_FAST_PATH` | Controls the 15-minute quick-trust macro window, unlocking ultra-fast back-to-back print starts. |

---

## 📖 Complete Technical Reference Manual

<details>
<summary><strong>1. Physical Mechanics & Probe State Truth Table (Click to expand)</strong></summary>

### Mechanical Kinematics
The Jabberwocky Probe utilizes a kinematically actuated sliding armature with two physical detented states. It transitions mechanical positions by traveling directly against a single fixed actuation tine mounted at the rear center of the printer enclosure (`Y = bed_max_y`).

**The same physical X coordinate triggers both states, governed strictly by the toolhead's approach direction:**
* **Retract Sequence:** The toolhead parks on the higher-X side of the tine and sweeps in the **−X** direction, pushing the pin into its stowed, locked position.
* **Deploy Sequence:** The toolhead positions itself on the lower-X side of the tine and sweeps in the **+X** direction, pulling the armature out into its active state.

### Shared Pin Sense Model (Configured with Invert Flag: `^!nhk:gpio10`)

| True Physical State | Terminal Command `QUERY_PROBE` Reports | Jinja State `printer.probe.last_query` Evaluates To |
|---|---|---|
| **Probe Deployed** | `probe: open` / Untriggered State | `False` |
| **Probe Retracted** | `probe: TRIGGERED` / Seated Ground State | `True` |

To isolate macro execution loops from stale data or cached software bits, the core logic layer evaluates live continuity status using the physical pin state variable `live_deployed = not printer.probe.last_query`.
</details>

<details>
<summary><strong>2. Preflight Calibration Scrubber & Hygiene Engine</strong></summary>

The standalone configuration scanner (`tools/jwp_config_preflight.py`) runs independently from the Klipper daemon, identifying structural layout defects, numerical initialization drift, and legacy wrapper fragments.

### Operational Command Suite:
```bash
# Execute standard JWP framework integration scan:
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py ~/printer_data/config/printer.cfg

# Standalone configuration audit for general machine hygiene (supports any printer):
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene ~/printer_data/config/printer.cfg

# Map complete include trees, locate unreferenced orphan files, and print active macro registers:
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene --tree --find-orphans --macro-table ~/printer_data/config/printer.cfg

# Isolate unreferenced assets and execute safe review quarantining:
python3 ~/printer_data/config/jabberwockyprobe/tools/jwp_config_preflight.py --general-hygiene --find-orphans --quarantine-orphans --confirm ~/printer_data/config/printer.cfg
```

### Advanced Diagnostic Logic:
* **Orphan Analysis Engine:** `--find-orphans` scans your configuration tree, isolating unreferenced `.cfg` files while filtering out expected archival files (paths containing `archive` or filenames tracking structural indicators like `.bak`, `_old`, `_orig`, or `_copy`). It accurately flags `[DISABLED]` items (files referenced solely by a commented-out include line) and surfaces `[WARN] Dangling Commented-Out Include` flags if a commented line points to a missing file.
* **Storage Allocation Guard:** `--gcode-stats` and `--log-stats` track file distribution, tracking file sizes, identifying massive crash dumps, and mapping remaining disk space within your active data directories.
* **Bypass Command Detection:** The hygiene parser evaluates all macro blocks, flagging dangerous, low-level testing routines left over from structural bring-up. It surfaces warnings for untracked instances of `FORCE_MOVE`, `SET_KINEMATIC_POSITION`, `STEPPER_BUZZ`, `SET_STEPPER`, or cold-extrusion overrides (`M302 ... P1`).
* **Value-Level Sanity Scanning:** The engine reads numerical variables across live registers, flagging un-tuned default PID values (`Kp=1.0 Ki=0.5 Kd=2.0`), invalid driver currents caused by unit-pasting errors (e.g., entering raw mA values like `1500` instead of `1.5` Amps), and structural shadowing conflicts between active `[autotune_tmc]` loops and manual `run_current` limits.
* **Lifecycle Flow Audits:** Evaluates end-of-print, pause, and cancellation behaviors. The routine confirms that heaters and cooling arrays are properly structured to clear down, verifies that your `[idle_timeout]` is calibrated within a safe `1800s` window to maintain motor engagement between quick reprints, and flags dangerous pause routines that accidentally drop stepper torque, which destroys coordinate accuracy.
</details>

<details>
<summary><strong>3. Web UI Dashboard Interception (Mainsail & Fluidd)</strong></summary>

Web interface buttons call standard Klipper commands. The APPS installer owns
the generated QGL and bed-mesh includes in a uniquely marked block in
`printer.cfg`; do not add those wrapper includes to `jwprobe_entry.cfg`.
Z-tilt remains optional and is not automatically managed.

### Architectural Implementation Profiles:
JWP wrappers forward native command parameters with `{rawparams}`. The installer
checks for competing standard-command wrappers and stops without changing
`printer.cfg` if ownership is ambiguous.
</details>

<details>
<summary><strong>4. Workspace Mapping: Stored Constants vs Variable Locations</strong></summary>

| Safe Storage Registers (`~/printer_data/config/...`) | Volatile Framework Variables (`jabberwockyprobe/...`) |
|---|---|
| **`jwprobe_runtime_vars.cfg`**<br>• Live machine profiles<br>• Automated dock strike values<br>• Calibrated Auto-Z pin coordinates<br>• Stored nozzle-to-probe constants | **`jwprobe_globals.cfg`**<br>• System transit travel speeds<br>• Low-torque alignment currents<br>• Overshoot tolerances<br>• Fast-path time window limits |
| **`printer.cfg`**<br>• Native `[stepper_*]` travel bounds<br>• Physical driver MCU pin mappings<br>• Emitted structural replacement leveling blocks<br>• Slicer-facing custom `PRINT_START` scripts | **`jwprobe_hardware.cfg`**<br>• Active toolhead probe pin parameters (`^!nhk:gpio10`)<br>• Documented hardware offset dimensions |
</details>
