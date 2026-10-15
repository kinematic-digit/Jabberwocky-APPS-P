# Jabberwocky-APPS

# 🚨 ALPHA SOFTWARE — TESTING ONLY 🚨

# ⚠️ NOT FOR PRODUCTION USE ⚠️

**Jabberwocky-APPS IS EXPERIMENTAL SOFTWARE UNDER ACTIVE DEVELOPMENT.**

**THIS SOFTWARE IS PROVIDED STRICTLY FOR TESTING AND EVALUATION. IT IS NOT PRODUCTION-READY.**

Do not rely on this software to protect your printer, prevent mechanical damage, or guarantee safe operation.

Before testing:

- Back up your Klipper configuration.
- Make sure you can restore your printer if Klipper fails to start.
- Review configuration changes before restarting Klipper.
- Report unexpected behavior and test failures.
- Do not assume that a successful installation means every feature works.

**USE AT YOUR OWN RISK. TESTING ONLY.**

---

## 1. What Is Jabberwocky-APPS?

Jabberwocky-APPS is an experimental software project for Klipper-based 3D printers.

The project focuses on configuration discovery, diagnostic reporting, and tools for managing printer configuration files and macros.

The longer-term goal is to explore software-assisted observation of printer behavior and mechanical state.

These capabilities are under development. Planned features must not be interpreted as completed or proven functionality.

### Current Feature Overview

| Feature | Description | Status |
|---|---|---|
| Setup interface | Interactive access to the setup workflow | Alpha testing |
| Configuration discovery | Examines the printer configuration and its included files | Alpha testing |
| Dashboard | Presents discovered configuration items for management | Alpha testing |
| Diagnostic report | Displays findings to help investigate configuration problems | Alpha testing |
| Extruder tools | Intended for future development | Not available |
| Probe tools | Intended for future development | Not available |
| Advanced monitoring and control | Longer-term experimental development | Not production-ready |

Features may be incomplete or change between revisions. Verify results against your actual printer configuration.

---

## 2. Before You Install

You will need:

- A Klipper-based 3D printer.
- SSH access to the printer host.
- Access to your printer configuration directory.
- A backup of your existing configuration.
- Basic familiarity with restarting Klipper and recovering from configuration errors.

The standard Klipper configuration directory is:

`~/printer_data/config/`

Your installation may use a different location. Verify your configuration path before proceeding.

**Do not test this software on a printer that must remain operational.**

---

## 3. First Installation

Connect to your printer host using SSH.

Enter the following commands one at a time:

### Step 1 — Download Jabberwocky-APPS

```bash
cd ~
git clone https://github.com/kinematicdigit/Jabberwocky-APPS.git
```

### Step 2 — Enter the application directory

```bash
cd ~/Jabberwocky-APPS
```

### Step 3 — Start the installer

```bash
chmod +x install.sh
./install.sh
```

Follow the instructions displayed by the installer.

Do not restart Klipper until you have reviewed any configuration changes and confirmed that the configuration is valid.

---

## 4. Updating Jabberwocky-APPS

**The recommended update procedure is a clean replacement of the application directory.**

This avoids carrying old, untracked, or obsolete application files into the new checkout.

### Important Before Updating

The removal command below permanently deletes the existing `Jabberwocky-APPS` directory, including any local code changes.

Make sure you do not need anything stored in that directory before continuing.

Your Klipper configuration is stored separately and must not be deleted as part of an application update.

### Step 1 — Remove the old application

Connect to your printer host over SSH.

Enter:

```bash
rm -rf ~/Jabberwocky-APPS
```

Wait for the command to finish.

**Check that you have entered the path correctly before pressing Enter.**

### Step 2 — Download the clean application

Enter these commands one at a time:

```bash
cd ~
git clone https://github.com/kinematicdigit/Jabberwocky-APPS.git
cd ~/Jabberwocky-APPS
chmod +x install.sh
./install.sh
```

Follow the installer's instructions.

### What This Update Does

- Removes the old application checkout.
- Downloads a fresh copy from the public repository.
- Runs the installer from the new checkout.
- Leaves the separate Klipper configuration directory untouched by the removal command.

**Important:** The installer may subsequently modify managed configuration files. Review those changes before restarting Klipper.

This is a clean application update, not a factory reset of your printer configuration.

---

## 5. Using the Interactive Interface

Use the arrow keys to navigate the menu and press Enter to select an option.

### Setup

Runs the configuration setup workflow.

The workflow examines the printer configuration and its includes, discovers configuration items, and manages the project's dashboard and related files.

Configuration changes can affect whether Klipper starts successfully. Review the results and retain a recoverable backup.

### Extruder Tools

Reserved for future development.

### Probe Tools

Reserved for future development.

### Report

Opens the diagnostic report interface.

The report is intended to help you investigate configuration findings without applying dashboard changes.

To test the Report feature:

1. Launch the application.
2. Navigate to **Report**.
3. Press Enter.
4. Review the displayed findings.
5. Use the available navigation keys to inspect the report.
6. Press Q to return to the menu.
7. Exit without running the setup workflow.

**You do not need to run Setup merely to test Report.**

If the report interface offers a save option, follow its on-screen instructions to save a copy for investigation.

### START

Starts the setup workflow.

Do not select START when your only goal is to test the Report feature.

### Exit

Press Q to leave the interface.

---

## 6. Understanding Configuration Findings

Jabberwocky-APPS is intended to help users inspect their configuration structure.

Depending on the findings displayed by the current version, the report may identify issues involving included files, duplicate definitions, or files that appear disconnected from the active configuration tree.

These findings require human review.

### Duplicate Definitions

A duplicate definition may indicate that multiple configuration files define the same item.

Do not delete a definition solely because it is flagged. Determine which definition is intended to be active and whether the duplicate is deliberate.

### Unreferenced or Orphaned Files

A file that is not reached through the recognized include tree is not necessarily safe to delete.

It may be retained for future use or loaded through a mechanism the application does not recognize.

Review its contents and purpose before taking action.

### Configuration Errors

Use the report to locate and investigate potential problems.

The report is a diagnostic aid, not an automatic repair mechanism. A clean report does not guarantee that every aspect of the printer configuration is correct.

---

## 7. If Klipper Will Not Start

If Klipper fails to start after testing:

1. Stop making additional configuration changes.
2. Review the Klipper error message.
3. Inspect the affected configuration file and line reference.
4. Check the Jabberwocky-APPS report, if available.
5. Compare the affected files with your backup.
6. Restore or correct the affected configuration.
7. Verify the configuration before restarting Klipper.

Do not repeatedly run the installer or synchronization commands in an attempt to fix an unknown problem.

Keep your original configuration available until testing is complete.

---

## 8. Reporting Problems

Useful bug reports include:

- The application version or Git commit being tested.
- The operation you were performing.
- The exact command you entered, if applicable.
- The complete error message.
- The relevant diagnostic report output.
- Whether Klipper was running at the time.
- Whether the problem can be reproduced.

Remove passwords, tokens, API keys, and other private information before sharing logs or configuration files.

When possible, describe what actually happened separately from what you think caused it.

This helps distinguish observed behavior from assumptions.

---

## 9. Development Status

Jabberwocky-APPS is under active development.

Configuration handling, report content, interface behavior, and installation procedures may change between revisions.

Some features may be incomplete, unavailable, or subject to substantial redesign.

Successful installation does not establish that every feature is reliable.

**This project is intended for development, evaluation, and testing only.**

Do not use it as a substitute for printer maintenance, configuration backups, or established safety procedures.

### Source Layout

- `software/macro_manager/` contains Macro Manager state, scanning,
  reporting, and synchronization modules; `jws_core.py` is its CLI entry.
- `software/jw_probe/` contains JWP source and the Klipper-loadable
  `jwp_event_tracker.py`.
- JWP calibration persists at `~/printer_data/config/jwprobe_runtime_vars.cfg`;
  the APPS Curses installer owns JWP package deployment and the generated
  QGL/bed-mesh integration block. Existing hardware bindings and user globals
  are preserved on updates.
- The installer initializes an empty variable store only for a fresh install,
  preserves existing data on updates, and stops automatic path migration when
  both legacy and canonical files exist without a verified migration marker.
- `software/jws_installer.py` and `software/curses_ui.py` provide the setup
  workflow and interactive entry point.
- `software/jwp_build.py` is the shared release builder.
- `config/` contains the checked-in printer configuration; `jabberwocky_dist/`
  contains installer distribution assets.

Run the focused local regression suites from the repository root:

```bash
python3 -m unittest discover -s tests -p 'test_macro_manager_sync.py' -v
python3 -m unittest discover -s tests -p 'test_jwp_event_tracker.py' -v
python3 -m unittest discover -s tests -p 'test_jwp_persistence.py' -v
```

---

## 10. Project Repository

Source code and project updates:

https://github.com/kinematicdigit/Jabberwocky-APPS

Please report reproducible issues and provide the information needed to investigate them.

**ALPHA SOFTWARE. TESTING ONLY. NOT FOR PRODUCTION USE.**

---

# EOF
