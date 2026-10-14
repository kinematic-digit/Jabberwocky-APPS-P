# JWS v3.0 System Overview & Operations Guide

This document provides a comprehensive operational overview and usage instructions for the **Jabberwocky Scrubber (JWS v3.0)** system architecture.

**Note:** The package now uses *lazy imports* in `__init__.py` so that heavy modules are only loaded when accessed. This keeps the bootstrap lightweight and improves import times.

---

## 1. System Architecture & Components
The JWS v3.0 ecosystem isolates file parsing from code state manipulation. The package consists of the following components inside your `~/printer_data/config/` structure:

```text
~/printer_data/config/
├── printer.cfg                         # Primary Klipper entry configuration
├── jws_state.cfg                       # Web Dashboard interaction layer
└── jabberwockyprobe/tools/
    ├── __init__.py                     # Package namespace initialization anchor
    ├── jws_utils.py                    # Regular expression patterns and boundaries
    ├── jws_observer.py                 # The Observer: Passive read-only tree crawler
    ├── jws_state_manager.py            # Ground-Truth: State variable verification engine
    ├── jws_operator.py                 # The Operator: In-place text masking utility
    └── jws_core.py                     # Central operational run-loop orchestrator
```

---

## 2. Core Operational Modes

The central orchestrator hub (`jws_core.py`) executes two discrete modes based on your requirements.

### 2.1 Mode 1: Passive Discovery Pass (Default)
Running the script without arguments executes a pure, read-only analysis of your active configuration files. It evaluates the ground-truth map of files currently loaded by Klipper, checks for syntax anomalies, and profiles active components.

**SSH Execution Command:**
```bash
python3 ~/printer_data/config/jabberwockyprobe/tools/jws_core.py
```

### 2.2 Mode 2: Active Component Synchronization
Running the script with the `--sync` argument tells **The Operator** to cross-reference the physical asset tree with the states defined in your `jws_state.cfg` control dashboard. It dynamically masks out disabled items or reveals active ones.

**SSH Execution Command:**
```bash
python3 ~/printer_data/config/jabberwockyprobe/tools/jws_core.py --sync
```

---

## 3. Using the Web Control Dashboard (`jws_state.cfg`)

The active interaction layer relies entirely on a human-editable Klipper macro block. You do not need to touch raw python configurations to hide or show subcomponents. 

### 3.1 Flipping Flags
Open `jws_state.cfg` inside your Mainsail or Fluidd sidebar file manager. Adjust the binary toggle states (`0` for Hidden/Disabled, `1` for Visible/Enabled) matching your intended hardware profile:

```text
[gcode_macro _JWS_TOGGLE_MANIFEST]
variable_file_bedfans_cfg: 1
variable_file_autotune_tmc_cfg: 0       # Set to 0: This file inclusion will be masked out
variable_macro_purge_blob: 1
variable_macro_stalltest: 0              # Set to 0: This specific macro block will be masked out
gcode:
```

Save your changes, then execute a **Sync Pass** to align your configurations.

### 3.2 Ghost Variable Purging
If you manually delete an inclusion file or strip a macro out of your configuration files over SSH, the ground-truth manager will instantly recognize the missing physical file during the next pass. It automatically prunes the dead tracking parameter completely out of your `jws_state.cfg` control dashboard to keep your dashboard clean.

---

## 4. In-File Masking Mechanics

When a component is toggled to `0` (Disabled), the engine inserts structured, non-destructive comment blocks inside your configuration scripts. This allows you to safely toggle components on and off without deleting files or losing local notes.

### 4.1 Inclusion Level Masking Example
```text
# ------------------------------------------------------------------------------
# ⚠️ JWS ISOLATION: Masked by System.
# 👉 TO UNDO: Switch 'file_autotune_tmc_cfg: 1' inside jws_state.cfg.
# ------------------------------------------------------------------------------
#-hidden-##
#[include autotune_tmc.cfg]
```

### 4.2 Macro Level Block Masking Example
```text
# ------------------------------------------------------------------------------
# ⚠️ JWS ISOLATION: Temporarily Commented Out.
# ------------------------------------------------------------------------------
#-hidden-##-start- stalltest
#[gcode_macro stalltest]
#gcode:
#    RESPOND MSG="Running motor stall validation test cycle..."
#    G28 X0
#-hidden-##-end- stalltest
```

---

## 5. UI Dashboard Integration (Optional)

To trigger synchronization passes directly from the web interface without logging into an SSH terminal session, add a `[gcode_shell_command]` hook to your setup:

```text
[gcode_shell_command jws_sync]
command: python3 /home/pi/printer_data/config/jabberwockyprobe/tools/jws_core.py --sync
timeout: 30.0
verbose: True

[gcode_macro JWS_SYNC_HARDWARE]
gcode:
    RUN_SHELL_COMMAND CMD=jws_sync
    RESPOND MSG="JWS Ecosystem hardware synchronization pass executed."
