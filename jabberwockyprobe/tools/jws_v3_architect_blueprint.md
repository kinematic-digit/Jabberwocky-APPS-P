# Comprehensive Architecture & Design Document: JWS v3.0

## 1. Document Overview & Context
This document serves as the permanent engineering reference and design specification for the **Jabberwocky Scrubber (JWS v3.0)** system architecture. It codifies the complete technical recovery path, functional parameters, and interface strategies devised following the systematic failure analysis of the legacy JWS framework on September 20, 2026.

---

## 2. Core Philosophy: The In-Place Paradigm Shift
The foundational breakthrough of JWS v3.0 is the complete elimination of destructive file mutations. Legacy versions relied on file isolation and directory purging (`shutil.rmtree()`, `os.remove()`, or `unlink`), which introduced severe systemic vulnerabilities regarding untracked formats, manual stashes, and automated macro snapshots (e.g., Mainsail `.zip` backups).

### 2.1 Guiding Principles
1. **Absolute Data Preservation:** No file is ever moved, renamed, or unlinked by the automation engine.
2. **Reversibility by Default:** Every automated configuration modification must be explicitly legible to an amateur operator and instantly reversible by hand inside a standard text editor.
3. **No Hidden State Databases:** The system avoids secondary state registries (such as hidden JSON or SQLite files). The user-facing configuration workspace *is* the state database.

---

## 3. Bifurcated Workflow System Architecture
JWS v3.0 splits its operations cleanly into an analytical layer (**The Observer**) and an execution layer (**The Operator**). This allows power users to completely bypass automated intervention if they prefer purely manual file editing.

```
       [ Live Klipper Configs ]
                  │
                  ▼
   1. PASSIVE DISCOVERY: Scrubber reads directory
                  │
                  ▼
     ┌──────────────────────────┐
     │  jws_hygiene_report.txt  │ ◄─── Read-Only Analytical Log
     └──────────────────────────┘
                  │
                  ▼
   2. ACTIVE INTERVENTION MAP (Auto-Generated)
                  │
                  ▼
     ┌──────────────────────────┐
     │      jws_state.cfg       │ ◄─── Interaction Layer (0s and 1s)
     └──────────────────────────┘
```

### 3.1 Passive Discovery Layer (`jws_hygiene_report.txt`)
* **Mechanism:** A read-only analytical summary written to the configuration root directory (`~/printer_data/config/`).
* **UX Specification:** Features identical high-visibility callout panels bookended at the absolute top and bottom of the file layout buffer. This eliminates layout tracking navigation friction, ensuring users see the immediate action guidelines instantly upon opening the file inside the Mainsail or Fluidd sidebar dashboards.

### 3.2 Active Interaction Layer (`jws_state.cfg`)
* **Mechanism:** A native, human-editable Klipper configuration manifest file housing simple binary state flags mapped to macro variables.
* **UX Specification:** Designed for visual or novice operators. Changing a variable value from `1` (Active) to `0` (Hidden/Masked) registers a state shift that the scrubber synchronizes by inserting safe inline regex comment tokens.

```text
# ==============================================================================
# 🎛️ JWS COMPONENT TOGGLE CONTROL PANEL
# ==============================================================================
# Change a variable flag below to 0 (Disabled/Hidden) or 1 (Enabled/Visible).
# After saving changes, run the configuration scrubber to synchronize states.

[gcode_macro _JWS_TOGGLE_MANIFEST]
variable_file_bedfans_cfg: 1
variable_file_autotune_tmc_cfg: 0
variable_macro_purge_blob: 1
variable_macro_stalltest: 0
gcode:
    # Quiet container block for keeping system variables
```

---

## 4. Execution Mechanics & Edge-Case Reconciliation

### 4.1 The "Prune and Update" State Logic Loop
To handle mixed user workflows seamlessly (e.g., when a power user alternates between editing the `jws_state.cfg` control dashboard and manually deleting files or text blocks over SSH, FTP, or a browser), the python engine executes an authoritative sanity cross-reference before editing text arrays:

1. **Hardware Scan Verification:** The script pulls a ground-truth map of files physically present on the metal before reading the control panel block variables.
2. **Ghost Variable Purging:** If a power user manually deletes a file or cuts a macro block out via Mainsail, the script detects the missing dependency, bypasses string processing for that item, and **instantly purges the obsolete tracking variable** out of `jws_state.cfg`.
3. **User Override Priority:** If a block is already manual plain-text comment data, the parser skips it entirely, ensuring human interventions always take priority over automated states.

### 4.2 In-File Comment Mask Structures
When a component state is toggled to `0` (Hidden), the script writes an explicit comment block signature right above the component target location using a standardized `#-hidden-##` tag configuration. This bracket embeds clear inline instructions explaining why the change happened and how to revert it manually.

#### 4.2.1 File-Level Inclusion Hiding (`printer.cfg`)
```text
# ------------------------------------------------------------------------------
# ⚠️ JWS ISOLATION: This inclusion link has been safely masked out by the system.
# 👉 TO UNDO: Change 'variable_file_autotune_tmc_cfg: 1' inside jws_state.cfg
#    and run a Sync pass, OR delete the '#' comment symbol on the include line.
# ------------------------------------------------------------------------------
#-hidden-##
#[include autotune_tmc.cfg]
```

#### 4.2.2 Macro-Level Block Masking (`macros.cfg`)
```text
# ------------------------------------------------------------------------------
# ⚠️ JWS ISOLATION: This macro has been temporarily commented out in place.
# 👉 TO UNDO: Change 'variable_macro_stalltest: 1' inside jws_state.cfg
#    and run a Sync pass, OR manually delete the '#' prefix from every line below.
# ------------------------------------------------------------------------------
#-hidden-##-start- stalltest
#[gcode_macro stalltest]
#gcode:
#    RESPOND MSG="Running motor stall validation test cycle..."
#    G28 X0
#-hidden-##-end- stalltest
```

---

## 5. Deployment & Automated Installation Infrastructure
To avoid complex dependency issues or manual installation errors, JWS v3.0 introduces a standardized one-line shell script installer hook.

### 5.1 One-Line Terminal Execution String
```bash
curl -sSL https://raw.githubusercontent.com/kinematicdigit/jws-scrubber/main/install.sh | bash
```

### 5.2 Automated Installer Action Sequence
1. **Dependency Injection:** Audits the host Linux environment for the `gcode_shell_command.py` extension dependency. If missing, it installs the plugin straight into the user's active Klipper ecosystem extension directory (`~/klipper/klippy/extras/`) automatically.
2. **Workspace Provisioning:** Populates the core tool repository (`~/printer_data/config/jabberwockyprobe/tools/`) with appropriate execution bounds (`chmod +x`).
3. **Template Mounting:** Drops the default `jws_state.cfg` manifest block into place and appends an active `[include jws_state.cfg]` string link to the bottom of the user's root `printer.cfg` to spin up the UI buttons seamlessly.

---