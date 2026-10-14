# Jabberwocky APPS — Project Context and Development Handoff

Prepared 2026-10-09 from a read-only reconciliation. **Sections 1–6.6 and 7–9 are static inspection. One isolated runtime test of `jws_core.py --sync` (two runs, fabricated fixture in `/tmp/jw_sync_fixture`) was executed afterward; its observed results are in section 6.7 and labeled [O]. Nothing else was run: no installer, no live config, no Klipper, no UI.**

## Claim labels used throughout

| Label | Meaning |
|---|---|
| **[V]** | Verified by current source inspection (static reading of the file at commit `0c6ce8d`) |
| **[R]** | Reported by a previous audit or historical session; not independently re-checked here |
| **[D]** | Historical design decision |
| **[H]** | Hypothesis requiring verification |
| **[N]** | Runtime behavior not yet tested |
| **[O]** | Directly observed in the isolated fixture test (section 6.7) |

Contradictory reports are kept side by side below. They are not merged into one account.

---

## 1. Purpose and current readiness

This file consolidates project context so development can resume without re-running broad audits.

**Readiness: not ready for new feature work (including Choice B).** The mapping, dashboard and synchronization path has been read but not run. Several defects below affect the exact path that Choice B depends on. The 10-Point System Protocol has not been located, and the original Google AI handoff text is not in the repository.

---

## 2. System architecture and boundaries

**Intended design [D]**
- **Macro Manager:** a plain-text dashboard, `jwt_macro_manager.conf`, with visible `[0]`/`[1]` checkbox values. It is meant to hold persistent user selections. It must not depend on Klipper macro variables or runtime caches. It is meant to stay outside Klipper's normal config parsing.
- **Scrubber:**
  - Reads the dashboard.
  - Follows the active include tree from `printer.cfg`.
  - Maps selections to targets.
  - Masks or unmasks rows with `#💤#`.
  - Uses directory scans only for secondary orphan diagnostics.
- **Klipper:** consumes the resulting configuration after a firmware restart.
- Macro Manager and Scrubber are two layers of one system.

**What the source actually implements (as of `0c6ce8d`)**

| Component | Implemented behavior | Label |
|---|---|---|
| `software/curses_ui.py` | Menu with four checkbox options and a "run" row. Pressing ENTER on the run row calls only `jws_installer.run_installation_pipeline()` (line 124). It never calls `jws_core`. The four selections are stored but never read. The "verification pass" screen prints a hard-coded `[  OK  ]` for each item and checks nothing | [V] |
| `software/jws_installer.py` | Backs up `printer.cfg`, walks the config directory with `os.walk`, generates `jwt_hardware.cfg` and `jwt_macro_manager.conf`, copies three dist files, and rewrites `printer.cfg` to include `jwt_clutch_logic.cfg`. Many `except Exception: pass` blocks hide failures | [V] |
| `scrubber/jws_observer.py` | `scan()` crawls includes depth-first from `printer.cfg`, honouring `#` and `#💤#`-muted includes. It runs a separate disk scan only to report orphans (Pass 3) | [V] |
| `scrubber/jws_core.py` | Parses dashboard checkboxes into a toggle map. With `--sync`, calls `scan()`, applies masking through `jws_operator`, then calls the installer's dashboard writer | [V] |
| `scrubber/jws_operator.py` | Rewrites include lines (file mode) or macro blocks (macro mode) in place | [V] |
| `jws_state_manager`, `jws_sterilizer`, `jws_reporter` | Lazily exported in `scrubber/__init__.py`. No callers found in `software/` or `scrubber/` | [V] for no callers; behavior not read in depth |

**Boundary gap [V]:** the dashboard's toggle list is built from the installer's directory-wide `os.walk` (`jws_installer.py` ~lines 52–90), not from the include tree. This contradicts the intended design for dashboard generation. Only `jws_core --sync` uses the include-tree crawler.

---

## 3. Historical decisions and rejected approaches [D]

- Persistent state lives in the text dashboard, not Klipper macro variables. The "Switch 3" macro-variable approach was **rejected**.
- State passed between modules uses primitive binary 0/1, not tuples or packed string records.
- The active-configuration crawler traverses includes sequentially from `printer.cfg`.
- File edits historically used descending line-number order. Current `jws_operator.py` rebuilds whole files line by line instead, so this convention is not visible in current code **[V]**.
- **Choice B (Extruder Hardware Isolation)** is future work. Do not begin it until the existing mapping and synchronization path is understood.
- **`JABBERWOCKY_SYNC_NOW` macro:** an unapproved proposal. Implementation and compatibility with the isolation boundary are not established. I did not search for it in source. The documented path is manual `python3 scrubber/jws_core.py --sync`.

### 3.1 Binary checkbox preservation: RESOLVED (design) [D]

**Status: RESOLVED as a confirmed architectural requirement (recorded 2026-10-09 on user instruction). Implementation compliance remains UNVERIFIED.**

BINARY CHECKBOX PRESERVATION — REQUIRED

1. Existing `[0]` and `[1]` dashboard selections must be preserved across installer reruns and synchronization.
2. Existing selections must never silently reset to defaults.
3. Defaults may be applied when creating a new dashboard or initializing a genuinely new entry.
4. Regenerating dashboard content must preserve existing user choices.
5. Any implementation that violates these rules is a defect.

Compliance notes:
- **Not runtime-verified [N].** No test or run has checked any code path against this requirement.
- **Current source, by static reading only:** the generators in `software/jws_installer.py` (lines 166, 184, 186, 151–152) write a literal `1` for every entry, and `scrubber/jws_core.py` lines 130–137 call the same writer at the end of `--sync`. Under rule 5 this reading, if confirmed, would be a defect (see section 6.3). It is reported here as an apparent violation, not a confirmed one.
- **Open design details this requirement does not settle:** how "genuinely new entry" is detected, and how entries whose source file or macro has disappeared are handled.

---

## 4. Chronology (uncertain parts labeled)

1. **Google AI v5.1.0 handoff.** The last reported major Google AI stage **[R]**. The handoff text is not in the repository. It reportedly flagged a filename-mapping mismatch in `jws_core.py` and asked for a fresh staging-truth-table review. This was not runtime-verified.
2. **ChatGPT work.** Architecture review and reconciliation, not application-code changes **[R]**.
3. **Later documents mention JWS v5.4.2 [R].** The source has no such label.
4. **Source version labels today [V]:**

   | File | Label |
   |---|---|
   | `scrubber/jws_core.py` line 3, `software/jws_installer.py` lines 3 and 13 | 5.7.5 |
   | `scrubber/jws_operator.py` line 3 | 5.2.0 |
   | `scrubber/jws_utils.py` | 5.2.1 |
   | `scrubber/jws_observer.py` line 3 | 5.2.1 |
   | `software/curses_ui.py` lines 3 and 30 | 1.9.6 |
   | `install.sh` | 4.5.0 |
   | `scrubber/__init__.py` | 3.0.0 |
   | `software/jw_toolhead/jwt_gear_diagnostic.py` | 3.8.6 |
   | `software/jw_toolhead/jwt_telemetry_poller.py` | 1.0.0 |
   | `jabberwocky_dist/jwt_macro_manager.cfg` | v4.8.6 |

   No unified sequence is asserted.
5. **Copilot reconciliation sessions (2026-10-09).** Phases labeled 1, 2, 4A, 4B and 5 appear in session history. Only the Phase 2, 4B (partial) and 5 reports were recoverable. Phases 1, 3 and 4A are unavailable.

---

## 5. Repository baseline and Git status

Last read-only inspection (2026-10-09). No fetch was performed.

- Root: `/Volumes/Mobile-SSD - Data/3D/GitHub/KD/Jabberwocky-APPS`
- Branch `main`, `HEAD` `0c6ce8d791270daa6387b82619f8b241884e14b1` ("Update repository to current APPS development state"), 61 commits.
- Tracked files clean. Untracked: `MASTER_DOC_REVIEW.md`, `PROJECT_CONTEXT_AND_HANDOFF.md`.
- Upstream (`origin/main`) status: **unknown**.
- Re-check `git rev-parse HEAD` and `git status` before relying on any line number here.
- Separate older copy at `/Volumes/Mobile-SSD - Data/3D/JWP/jabberwocky-05/Jabberwocky-APPS/` (files dated Sep 26) is not the current baseline.
- Documentation and historical reference location: `/Volumes/Mobile-SSD - Data/3D/JWP/jabberwocky-05/` (`Master_Doc_3.md` and `docs/`).

---

## 6. Findings by subsystem

### 6.1 Filename mapping and normalization — `scrubber/jws_core.py`, `scrubber/jws_operator.py`

| # | Finding | Label |
|---|---|---|
| 1 | `normalize_component_key` lowercases and replaces `/`, `\`, space, `-`, `.` with `_` (`jws_core.py` ~lines 24–29). The mapping is many-to-one | [V] |
| 2 | The sync loop reverses that mapping only for a trailing `_cfg` or `_conf`, giving `.cfg` or `.conf` (lines 105–108). Underscore-only names such as `jwt_clutch_logic_cfg` round-trip correctly | [V] |
| 3 | Hyphenated names are lossy: `nitehawk-36.cfg` becomes `nitehawk_36.cfg`, which will not match. The same applies to dots or spaces inside a name | [V] by reading; [N] |
| 4 | The earlier claim that `jwt_macro_manager_conf` necessarily fails suffix conversion is logically unsupported. The `_conf` branch gives `jwt_macro_manager.conf` | [V] |
| 5 | The dashboard writer excludes the manager file from its own file list (installer `os.walk` filter), so that key is never generated by a fresh install | [V] |
| 6 | `jws_operator.py` line 49 compares the full include target text (for example `jabberwocky_dist/jwt_clutch_logic.cfg`) with the bare filename from the dashboard. A path-qualified include would not match. A bare `[include jwt_clutch_logic.cfg]` would | [V] by reading; [N] |
| 7 | A missing key silently defaults to `1` (`jws_operator.py` line 33), which means "unmask" | [V] |
| 8 | The original Google AI "mapping mismatch" report | [R]; not confirmed or refuted by runtime evidence |

### 6.2 Dashboard generation and installer — `software/jws_installer.py`

- **Write target:** `MANAGER_PATH` is `~/printer_data/config/jwt_macro_manager.conf` (line 23). It is built from `HOME`, not from `PRINTER_CONFIG_DIR` **[V]**.
- **Hardware file:** `jwt_hardware.cfg` is written under `jabberwocky_dist/` using scraped or default values (`0.55`, `7.0`, `35.13664`) **[V]**.
- **Dist copy:** `_inject_and_link` (line 236) copies only `jwt_clutch_logic.cfg`, `jwt_factory_blueprints.cfg` and `macromanager.cfg` (line 237) **[V]**.
- **`jabberwocky_dist/jwt_macro_manager.cfg`:** exists in the repo (v4.8.6, comment-only format) but is not in the copy list **[V]**. It is not deployed.
- **`printer.cfg` include:** the pipeline then rewrites `printer.cfg` and inserts one include, `[include jabberwocky_dist/jwt_clutch_logic.cfg]` (line 245 onward) **[V]**. It also removes lines containing `jwt_clutch_logic.cfg`, `jwt_macro_proxies.cfg` or `Jabberwocky-APPS`.
- **Include ownership:** no include of `macromanager.cfg` or `jwt_factory_blueprints.cfg` appears in the installer or in `jabberwocky_dist/*.cfg`. The only include found in the dist files is `jwt_hardware.cfg` from `jwt_clutch_logic.cfg` **[V]**. Whether anything loads them is unresolved.
- **Dashboard instructions:** the dashboard header tells the user to save the file and run `FIRMWARE_RESTART` "to apply updates" (~lines 142–147). Nothing in the pipeline reads the edited dashboard before restart **[V]**.

### 6.3 Preservation of user checkbox selections

- **Entry values:** file entries (line 166) and macro rows (lines 184, 186) are generated with a literal `1`. Edited values are not read back **[V]**.
- **Which values survive:** the only value read back is the quarantine flag.
- **Installer reruns reset all dashboard selections [V].** Rerunning `run_installation_pipeline` rewrites the dashboard.
- **Sync also resets them [V].** `jws_core.py --sync` ends by calling `_write_hardware_and_manager` (lines 130–137). That call rewrites the dashboard from scratch.
- **Placeholder hardware values:** the same call passes placeholder hardware values (`run_current="1.1"`, `stealthchop="1"`, `rotation_dist="32"`, `extruder_blocks=1`, `tmc_blocks=1`) (lines 132–137). It therefore also overwrites `jwt_hardware.cfg` with them **[V]**.
- **Sync call path:** I traced it by reading, so it has not been run **[N]**.
- **Requirement status:** the preservation requirement in section 3.1 is confirmed. Under it, the resets above would be defects if they behave as read. Runtime confirmation is still needed **[N]**.
- **Path inconsistency [V]:** `jws_core` resolves its config directory from `PRINTER_CONFIG_DIR` or the home default (`main()`). The installer's writer uses fixed `HOME` paths. With `PRINTER_CONFIG_DIR` set, the two modules could read and write different directories **[H]**.

### 6.4 File targets versus system-action targets

- **Checkbox rows:** the parser regex (`jws_core.py` line 48) requires a 📂 or ⚙️ icon followed by a word, and captures only one token **[V]**.
- **Action key collapse:** all three ⚙️ lines (`SYSTEM ACTION: SNAPSHOT BACKUP`, `SNAPSHOT RESTORE`, `SWEEP TO QUARANTINE`; installer lines 151–153) have `SYSTEM` as the first token. They all normalize to `action_system`, so later lines overwrite earlier ones **[V]**.
- **Macro rows:** macro rows begin with `├──` and `▶` and have neither icon, so they never enter the toggle map **[V]**.
- **Sync loop:** it processes only keys starting with `file_` (line 96). Action keys are discarded **[V]**.
- **Macro masking in sync:** the macro-mask loop (line 119) runs inside the file-key loop, so it repeats once per file key. Its lookup keys (`macro_*`) are never produced, so it only ever sees the default `1` **[V]**.
- **Quarantine flag read:** the regex at `jws_installer.py` line 111, `\[\s*()\s*\]`, has an empty capture group. It matches only brackets containing nothing but whitespace, not `[ 1 ]` **[V]**. If it ever matched, `int('')` would raise inside a swallowed `except`. The flag therefore stays `0`, and the quarantine sweep (line 117) does not run from a user toggle.
- **If the regex were fixed:** the sweep moves `.cfg` and `.conf` files that are not in `all_config_files`. Under `--sync`, that set comes from the include tree only, so the sweep could move files unrelated to the user's intent **[H]**.
- **Snapshot backup and restore:** no implementation traced. Status unknown.

### 6.5 Actual synchronization and masking path

Verified chain by reading, **never executed [N]**:

1. The user runs `python3 scrubber/jws_core.py --sync` manually.
2. `main()` reads `printer.cfg` and `jwt_macro_manager.conf`, and builds the toggle map.
3. `scan()` returns the include-tree registry.
4. Per `file_` key, `apply_in_place_masking` is called for every file in the registry (line 112).
5. The macro pass runs (line 119).
6. The sync then calls `jws_installer._write_hardware_and_manager` (lines 130–137), which rewrites the dashboard.

- No automatic trigger exists in the UI, installer or any Klipper macro **[V]**.
- **Missing prerequisites:** there is no backup before masking, and no dry-run mode.
- **Operator rewrite behavior:** the operator rewrites whole files. When it keeps an include active, it normalizes the line to `[include X]` and drops any trailing comment **[V]**.
- Whether masking followed by a restart produces the intended Klipper configuration is **[N]**.

### 6.6 Probe and toolhead components

- **Probe preflight:** `software/jw_probe/docs/jwp_config_preflight.py` (about 2,400 lines, revision r29, 2026-09-19) is not called by the installer or UI. Its own help text and the probe READMEs refer to `jabberwockyprobe/tools/…` paths that do not exist here **[V]**.
- **Event tracker:** `scrubber/jwp_event_tracker.py` and `scrubber/jwp_build.py` sit in `scrubber/` while their headers say `tools/`. The Master document places the tracker in `software/jw_probe/` **[V]**. Their behavior was not read.
- **UI option 3 ("Link … Probe …"):** no implementation behind it **[V]**.
- **Toolhead modules:** `jwt_gear_diagnostic.py` and `jwt_telemetry_poller.py` exist. Not read in depth.

### 6.7 Isolated `--sync` test results (2026-10-09)

**Requirement under test:** existing `[0]`/`[1]` selections must survive synchronization and installer reruns. Defaults apply only to genuinely new entries or a new dashboard (section 3.1).

**Test setup [O].** Code copies of `scrubber/` and `software/jws_installer.py` ran from `/tmp/jw_sync_fixture/repo`. `HOME` and `PRINTER_CONFIG_DIR` both pointed inside `/tmp/jw_sync_fixture/home`. All resolved write targets (config dir, dashboard, hardware file, quarantine dir, `printer.cfg`) were checked to resolve inside the fixture before the first run. The fixture had:
- A fabricated `printer.cfg` with includes for `alpha.cfg`, `beta.cfg`, `new-gamma.cfg`, `jabberwocky_dist/delta.cfg`, a commented `# [include epsilon.cfg]`, and `[include zeta.cfg] # keep`.
- A dashboard with `[0]` for alpha and epsilon, `[1]` for beta, delta and zeta, system actions `1/0/0`, and no row for `new-gamma.cfg`.
- A hardware file with sentinels `0.77`, `5.0`, `33.3`.
- Decoys `orphan.cfg` and `old.bak`.

Run 1 and run 2 both exited 0. Logs are in `/tmp/jw_sync_fixture/logs/` (temporary; not part of the repo). No application code or live printer configuration was changed, and the live directory was not read during the test. (Before the test, an earlier baseline step had hashed the live `printer_data` files; this was disclosed to the user and not repeated.)

**Confirmed observed findings [O]:**

| # | Observed behavior |
|---|---|
| 1 | Both `[ 0 ]` file selections (alpha, epsilon) were rewritten as `[ 1 ]`. |
| 2 | `jwt_hardware.cfg` values `0.77`, `5.0`, `33.3` were overwritten with `1.1`, `1`, `32`; the file's sentinel gcode line was replaced and a header added. |
| 3 | Dashboard file rows were regenerated keyed by macro name (`ALPHA_M`, `BETA_M`, …) with the absolute file path as the child row, instead of one row per file. The dashboard grew from 27 to 76 lines. |
| 4 | System-action rows changed from `1/0/0` to `1/1/0` (SNAPSHOT RESTORE went 0 → 1). |
| 5 | `[include zeta.cfg] # keep` became `[include zeta.cfg]` (trailing comment lost). |
| 6 | Dashboard and masked state disagreed. `printer.cfg` had `#💤#[include alpha.cfg]` and `#💤#[include epsilon.cfg]`, while the dashboard showed both as `[ 1 ]`. |
| 7 | Run 2 exited 0 and changed nothing: all checksums and the file listing were identical to after run 1. |
| 8 | No files were created, removed or moved. No quarantine sweep occurred. `alpha`, `beta`, `new-gamma`, `epsilon`, `zeta`, `delta`, `orphan.cfg` and `old.bak` were byte-identical to baseline. |

Further observed details [O]:
- Run 1's toggle map was read correctly from the `[0]`/`[1]` file rows: `file_alpha_cfg:0, file_beta_cfg:1, file_delta_cfg:1, file_epsilon_cfg:0, file_zeta_cfg:1`.
- `action_system` was `0` in the map even though the actions were `1/0/0` (key collapse).
- The commented `# [include epsilon.cfg]` was converted to a masked include. The observer followed commented and masked includes, so epsilon and alpha were still in the scanner tree on run 2.
- The new entry `new-gamma.cfg` received a row, `[ 1 ]`, and no masking change.
- Run 2's toggle map was keyed by macro names (`file_alpha_m`, `file_beta_m`, …), all `1`.

**Causes, traced in current source [V] (static trace consistent with the observations):**

| Failure | Function and lines | Mechanism |
|---|---|---|
| `[0]` → `[1]`, rows regenerated (1, 3, 6) | `jws_installer._write_hardware_and_manager`, writer at 97; row template at 164–189 (`_render_file_tree_block`, literal `[ 1 ]` at 166, 184, 186); write at 233 | The writer never reads the existing dashboard's file or macro rows and always emits `1`. |
| Rows keyed by macro name with absolute paths (3) | `jws_core.main` 132–139 passes `registry_map.get("macros", {})`; `jws_observer.scan` line 91 stores `macros[macro_name] = path`; writer iterates `discovered_macros.items()` as `{filename: macros}` | Type mismatch. The writer expects `{filename: [macros]}`. It receives `{macro: path}`. Keys become headers and path strings become child rows (via the `isinstance(macros, str)` branch at 168). |
| Hardware overwritten (2) | `jws_installer.py` 99–102 (unconditional `open(…, "w")`); `jws_core.py` 132–139 (placeholder arguments) | `--sync` reuses the installer's full-regeneration routine and passes hardcoded `run_current="1.1"`, `stealthchop="1"`, `rotation_dist="32"`. Nothing reads existing values. |
| System actions changed (4) | `jws_installer.py` 151–153 | Backup and restore are literal `1`. Only the quarantine value is variable, and its read regex (line 111) always yields `0`. |
| Action key collapse (observed `action_system`) | `jws_core.parse_visual_checkboxes` 48–53 | The regex captures only the first token (`SYSTEM`) after ⚙️, so all three actions share one key. The sync loop ignores non-`file_` keys (96). |
| Trailing comment lost (5) | `jws_operator.apply_in_place_masking` 51, 63–66; `jws_utils.INCLUDE_RE` line 18 | The active branch rewrites any non-identical line to the bare `[include X]`. The regex accepts trailing comments, but they are not preserved. |
| Commented include became masked (observed) | `jws_utils.INCLUDE_RE` 18; `jws_operator` 55–58 | The regex accepts a plain `#` prefix as well as `#💤#`, so a user's ordinary commented include is treated as a managed include. |
| Run 2 does not reconcile (7) | `jws_core.main` 95–108, 110–121 | See below. |

**Why run 2 does not reconcile the masked includes [V from source, consistent with observation; the mechanism was not itself instrumented]:**
1. After run 1 the dashboard has no `file_alpha_cfg` rows. The `📂` rows now name macros (`ALPHA_M`), so the parser produces `file_alpha_m`.
2. The suffix reversal (105–108) only maps `_cfg`/`_conf`. `alpha_m` stays `alpha_m`.
3. `apply_in_place_masking` (line 49) compares the include target with `alpha_m`, which never matches any include line.
4. The macro pass (116–121) looks up `macro_*` keys, which no parser produces. It gets the default `1` (operator line 33) and, with no mask markers present, changes nothing.
5. The writer then regenerates the same output from the same placeholders, so files are byte-identical.

The masked state of `printer.cfg` therefore persists but no longer corresponds to any dashboard row. The first run's damage is not undone by the second.

**Suspected causes and untested points [H]/[N]:**
- Whether the intended dashboard format is file-keyed or macro-keyed is a design question, not established (section 8).
- Whether `--sync` was ever meant to call the writer, or only the sweeper (the inline comment at `jws_core.py` line 125 says "chain-load sweeper loops") is unknown.
- Behavior with hyphenated filenames was not exercised as a failure: `new-gamma.cfg` is not masked by `[0]` because it had no row. The hyphen-lossy normalization (`jws_core.py` 28–30) is still [V] by reading only.
- The installer rerun path was **not** tested. Its checkbox behavior is unknown [N] (statically it also writes literal `1`, lines 166, 184, 186).
- Real Klipper parsing of the resulting files was not tested [N].

**Conclusion.** At commit `0c6ce8d`, `--sync` violates the confirmed checkbox-preservation requirement [O], overwrites hardware settings [O], and corrupts the dashboard's structure [O]. It should not be run against a live configuration.

**Proposed minimal corrections (for review; none implemented):**

| Issue | Smallest correction |
|---|---|
| Dashboard reset and regeneration on `--sync` | Remove the `_write_hardware_and_manager` call from `jws_core.main` (lines 125–141), so `--sync` only reads the dashboard and masks. Any sweeper hand-off must be a separate, explicit function that does not write the dashboard or hardware file. |
| Same defect on installer reruns | In the writer, read the existing dashboard first (reuse the `[ 0 ]`/`[ 1 ]` regex) into a `{file_or_macro_key: 0/1}` map. Use that value in place of the literal `1` at 151–153, 166, 184 and 186, falling back to `1` only for keys absent from the map. |
| Hardware overwrite | Write `jwt_hardware.cfg` only when it does not exist, or only when the installer is run explicitly with new values. Never write it from `--sync`. |
| Macro-name rows | Resolved by removing the call. If the call is kept, pass `{filename: [macros]}` built from `registry_map["files"]`, not `registry_map["macros"]`. |
| System-action changes and key collapse | Key actions by their full label (for example, capture everything after `SYSTEM ACTION:`) at `jws_core.py` line 48, and give the action rows persisted values as above. Wire actions only after intent is decided. |
| Quarantine flag | Fix the capture group at `jws_installer.py` line 111 to `\[\s*([01])\s*\]`, but only after deciding to keep the sweep, since it can move files. |
| Lost trailing comment | In `jws_operator.py` 62–68, when the line is already an active include (`desired_state == 1` and not masked), leave it unchanged. Only strip the mask tag when the line is masked. |
| Commented includes treated as managed | Narrow `INCLUDE_RE` handling in the operator to `#💤#`-masked lines only, or confirm that treating plain `#` as managed is intended. |
| Masked state versus dashboard disagreement | Becomes moot once the dashboard is never regenerated from defaults. Add a read-only check that reports mismatches before any masking. |
| Hyphen-lossy names | Make `normalize_component_key` and the include comparison use the same normalization on both sides (operator line 49), and compare against normalized names rather than the suffix-restored string. |

**Suggested fix order and verification.** Fix the `--sync` call and the writer's persistence first. Re-run the same fixture test, plus an installer-rerun test on a fixture, to confirm: `[0]`/`[1]` unchanged across both runs, hardware sentinels intact, `new-gamma.cfg` (a new entry) defaulted, and the include comments preserved. This is a plan only; it has not been approved or executed.

---

## 7. Contradictions between historical reports and current source

| Historical claim | Current source |
|---|---|
| Phase 2: the installer copies `jwt_macro_manager.cfg` as a template | Contradicted. It is not in `legal_includes` (installer line 237) |
| Phase 2: `macromanager.cfg` and the blueprints file are "implicitly included" by Klipper | Not supported. No include found. Unresolved |
| "No code constructs `toggle_manifest`" | Contradicted. `parse_visual_checkboxes` does (`jws_core.py`), though the identifier `toggle_manifest` is also used in `jws_operator.py` |
| Phase 5: the quarantine flag "only sets initial UI state" | Imprecise. A sweep exists but its flag-read regex cannot match a digit |
| Master doc M8 "MD5 token generator/handshake" in `jws_core` | Contradicted. No MD5 logic in `jws_core.py` |
| Master doc M4 "`scrubber/` calls block faulty installs" | Not supported. The installer imports `scan`/`apply_in_place_masking` but does not call them |
| Master doc: `software/jw_probe/jwp_event_tracker.py` | Contradicted. The file is at `scrubber/jwp_event_tracker.py` |
| Master doc milestones M1–M9 "✅ VALID" | No test logs found for any |
| `roadmap.md` M8 "Cross-Domain ADXL Fusion — Planned" vs Master doc M8 "Developer APIs — VALID" | Two different milestone lists. Authority undetermined |
| `docs/dependency.md` and `scope.md` describe `jws_core.py` as a preflight and version-header scanner | The code is a dashboard sync and masking orchestrator |
| Repo `README.md`: run `python3 curses_ui.py` from the repo root; `docs/` folder exists | `curses_ui.py` is at `software/`; the repo has no `docs/`. `install.sh` uses the correct path |
| Design intent: toggle list from the include tree | The installer builds it with a directory-wide `os.walk` |

---

## 8. Unresolved questions and missing evidence

1. **Contents of the 10-Point System Protocol.** Not located. Searched the repo, `jabberwocky-05/docs`, `Master_Doc_3.md` and session history for "10-point"; no matches.
2. **Original Google AI v5.1.0 handoff and truth table:** not available.
3. **Checkbox persistence:** RESOLVED as a requirement (section 3.1). Still open: whether the current code complies (it appears not to, by static reading), how a "genuinely new entry" is detected, and how stale entries are treated.
4. **Include ownership** of `macromanager.cfg` and `jwt_factory_blueprints.cfg`.
5. **`jwt_macro_manager.cfg` in `jabberwocky_dist/`:** obsolete, a template, or undeployed by mistake?
6. **Authoritative milestone list** and the test-log evidence behind any "VALID" claim.
7. **Correct home** of `jwp_event_tracker.py`, `jwp_build.py` and `jwp_config_preflight.py`.
8. **Which documents are current** (`architecture.md` v3.6.0 describes an older layout).
9. **Whether `origin/main` has moved.**
10. **How action rows were meant to be keyed** (one key per action versus the shared `action_system`).
11. **Snapshot backup, restore and quarantine behavior:** untraced for backup and restore.
12. **Runtime effects of everything above.** No test runs exist.
13. **Recovered phase gaps:** Phases 1, 3, 4A unavailable; 4B partial.

---

## 9. Audit coverage and limitations

**Read in full:** `software/curses_ui.py`, `software/jws_installer.py`, `scrubber/jws_core.py`, `scrubber/jws_operator.py`, `scrubber/jws_observer.py`, `scrubber/jws_utils.py`, `scrubber/__init__.py`, `install.sh`, `MASTER_DOC_REVIEW.md`, `Master_Doc_3.md`, and `docs/roadmap.md`.

**Read partially:**
- Repo `README.md` (first 40 lines, truncated at 200 characters per line).
- `jabberwocky_dist/jwt_macro_manager.cfg` (first 1,500 bytes).
- `jabberwocky_dist/macromanager.cfg` (first 700 bytes).
- `docs/architecture.md` (35 lines).
- `docs/dependency.md` (44 lines).
- `docs/scope.md` (22 lines).
- `docs/tracking.md` (33 lines).
- `docs/testing_game_plan.md` (first 50 lines plus a keyword scan).
- `docs/safety.md` (first 29 lines, long lines truncated).

**Not reviewed:**
- The `docs/` files: `apps_api_specs`, `integrations`, `context_objects`, `design_rules`, `contributing`, `competitive_analysis`, `collision_calibration`, `adxl_evidence_and_math`, `extruder_telemetry_profile`, `apps_announcement`, and the 1,517-line TMC bench-test handoff.
- `scrubber/jws_reporter.py`, `scrubber/jws_state_manager.py`, `scrubber/jws_sterilizer.py`.
- `scrubber/jwp_build.py`, `scrubber/jwp_event_tracker.py`.
- The toolhead modules, the probe cfgs and `jwp_config_preflight.py`.
- The repo's `.gitattributes`, `.gitignore`.

**Evidence type:**
- **Static inspection** for everything marked [V].
- **One runtime test:** `--sync` ran twice on a fabricated fixture in `/tmp/jw_sync_fixture` (section 6.7, [O]). It covers one tree layout and no hyphenated `[0]` entry.
- **Not run:** the installer, the UI, any live config, Klipper, and any repo test suite.
- **Recovered phases:** Phases 2, 4B and 5 were recovered from stored conversation turns, not from files. Their original line numbers are stale. The numbers in this document were re-checked against the current source.
- **Handoff file:** `PROJECT_CONTEXT_AND_HANDOFF.md` was empty when I began. Its original content, if any, is not recoverable.

---

## 10. Prioritized next steps to resume development

1. **Confirm the baseline.** Re-run `git rev-parse HEAD` and `git status`. Decide whether to fetch `origin/main` (needs approval).
2. **Supply missing history.** Provide the 10-Point System Protocol and the Google AI v5.1.0 handoff, or confirm they do not exist.
3. **Decide the intended behavior** for items 4 and 10 in section 8 before touching code. Item 3 (checkbox persistence) is settled by section 3.1; only its edge cases remain.
4. **Done (fixture, not a copy of a real config):** an isolated `--sync` test was run on 2026-10-09 (section 6.7). Set both `HOME` and `PRINTER_CONFIG_DIR` for any further test.
5. **Next test:** an installer-rerun test on a fixture (not yet run), then review the correction plan in 6.7. Do not run `--sync` on a live configuration.
6. **Only then plan fixes**, in this order: filename mapping, dashboard persistence, file-versus-action keying, the quarantine regex, then documentation and version alignment.
7. **Choice B stays on hold** until steps 1 to 5 are complete and the mapping and sync behavior is understood.

---

## 11. Safety rules for the next session

- Do not modify application code, configuration, the installer or existing project documents without explicit approval.
- Do not run the installer or `jws_core.py --sync` against a live config directory.
- Do not mask or unmask configuration files.
- Do not restart Klipper.
- Do not fetch, reset, switch branches or commit without approval.
- Do not start Choice B.
- Do not treat any [R] item as fact; recheck against current source first.
- Do not claim a test passed without recorded test evidence.
- Do not treat `JABBERWOCKY_SYNC_NOW` as approved.
- Do not use the nested `jabberwocky-05/Jabberwocky-APPS` copy as the current baseline.
- Keep the `.git` directory untouched unless explicitly directed.

---

## 12. Source references

Line numbers apply to commit `0c6ce8d`. Lines marked "~" are approximate.

| Topic | Location |
|---|---|
| UI calls installer only | `software/curses_ui.py` lines 13, 124 |
| UI version labels | `software/curses_ui.py` lines 3, 30 |
| Installer pipeline, writer, injector | `software/jws_installer.py` lines 34, 90–91, 97, 236 |
| Manager path (`HOME`-based) | `software/jws_installer.py` line 23 |
| Quarantine flag regex | `software/jws_installer.py` lines 110–111; sweep at 117 |
| System-action rows | `software/jws_installer.py` lines 151–153 |
| Literal-`1` entries | `software/jws_installer.py` lines 166, 184, 186 |
| Dist copy list | `software/jws_installer.py` line 237 |
| `printer.cfg` rewrite | `software/jws_installer.py` line 245 onward |
| Checkbox regex | `scrubber/jws_core.py` lines 48, 51 |
| `file_` filter, suffix reversal | `scrubber/jws_core.py` lines 96, 99, 105–108 |
| Masking calls | `scrubber/jws_core.py` lines 112, 119 |
| Installer bridge with placeholders | `scrubber/jws_core.py` lines 130–137 |
| Include-compare and default-1 | `scrubber/jws_operator.py` lines 33, 49 |
| Active-include rewrite (drops comment) | `scrubber/jws_operator.py` lines 51, 63–66 |
| Include regex (accepts `#` and `#💤#`) | `scrubber/jws_utils.py` line 18 |
| Macro registry type (`{name: path}`) | `scrubber/jws_observer.py` line 91 |
| Hardware file overwrite | `software/jws_installer.py` lines 99–102 |
| `--sync` test results | Section 6.7 (fixture `/tmp/jw_sync_fixture`, temporary) |
| Include-tree crawl and orphan pass | `scrubber/jws_observer.py` (Passes 1–3) |
| Lazy exports | `scrubber/__init__.py` |
| Probe preflight script | `software/jw_probe/docs/jwp_config_preflight.py` |
| Master document | `/Volumes/Mobile-SSD - Data/3D/JWP/jabberwocky-05/Master_Doc_3.md` |
| Review brief | `MASTER_DOC_REVIEW.md` |
| Roadmap, architecture, dependency, scope | `/Volumes/Mobile-SSD - Data/3D/JWP/jabberwocky-05/docs/` |

---

## 13. Stabilization review and direction (added 2026-10-09, static; no code run)

Labels: **Fact** = verified in current source or observed in the section 6.7 test. **Decision** = documented or user-confirmed. **Rec** = recommendation, not approved. **Open** = needs a decision.

### 13.1 Additional facts found in this review

- **Fact:** `jws_core.py` has only one flag, `--sync` (line 64). Run without it, `main()` parses the dashboard and prints the toggle map and writes nothing (the `else` at line 143). That is a de facto read-only inspection, though it is not a real report. No `--report`, `--dry-run` or `--sterilize` flag exists.
- **Fact:** `scrubber/jws_state_manager.py` (`sync_manifest_state`) is a legacy v3.0 module. It reads a `[manifest]`-style section of a Klipper `.cfg` using `MANIFEST_SECTION_RE` and `MANIFEST_VAR_RE`, and prunes "ghost" keys. Those two names are imported at line 10 but **defined nowhere** in the repo (`jws_utils.py` has none), so the module cannot import. Nothing calls it. It is lazily exported from `scrubber/__init__.py` (line 43) and is the closest thing in the code to the old variable-based state approach.
- **Fact:** `scrubber/jws_sterilizer.py` (`execute_workspace_sterilization`) permanently deletes files (`unlink`, line 57) after a rollback copy, but only when `live_run` and `cache_confirmed` are both true (line 33). Its safety text names `jws_core.py --sterilize --confirm-reboot-cache-clear` (line 77), which does not exist. Nothing calls it.
- **Fact:** `scrubber/jws_reporter.py` (`Reporter`) is a plain-text formatter used by `jwp_config_preflight.py` (lines 1490, 2201), not by `jws_core.py`. It is reusable for a report mode.
- **Fact:** the installer's discovery pass (`jws_installer.py` lines 56–86) reads real `[extruder]` values for `run_current`, `stealthchop_threshold` and `rotation_distance`, so the installer path derives hardware values from the user's config. Its initial defaults are `0.55`, `7.0`, `35.13664` (lines 48–50). `--sync` passes unrelated placeholders (`1.1`, `1`, `32`), so the two entry points disagree on the defaults too.
- **Fact:** the installer's "conflict" badges (`[D!]` active override, `[D?]` overwritten, lines 150–189) are duplicate-macro detection, built from `macro_counts_map`. `--sync` passes `macro_counts_map={}`, so after a sync the badges disappear.
- **Fact:** `scrubber/jwp_event_tracker.py` (header v3.4.0) is a Klipper extras module, and is not part of the sync path. It reads collision thresholds and pin offsets from the variables of a macro named `_JWS_TOGGLE_MANIFEST` (lines 49, 103), which is **not defined anywhere in this repo**. When absent it uses built-in defaults. On a confirmed impact it can `EXCLUDE_OBJECT`, raise Z, or `PAUSE` (lines 100–126). It appends rows to a hardcoded `/home/pi/printer_data/config/jwp_calibration_profile.csv` and silently does nothing if that directory is missing (lines 128–138). Nothing in the installer deploys or enables it.
- **Fact (static):** `_JWS_TOGGLE_MANIFEST` reads a macro-variable store, which is the pattern the Decision in section 3 rejects ("Switch 3"). Whether event tracking is meant to be exempt is **Open**.
- **Fact:** the installer writes `printer_<timestamp>.bak` into the config directory (lines 36–39). If the quarantine flag were ever made to work, the sweep (lines 115–121) would move those backups, which is probably not intended.
- **Fact:** `Master_Doc_3.md` (60 lines, v3.9.0) mentions the event tracker only in its tree (line 35) and says nothing about collision detection, persistent state, reports or a novice workflow. It lists `jws_state_manager.py` as "Dashboard Toggle State Syncer" and `jws_sterilizer.py` as "Destructive Purge & Rollback Anchoring Engine".
- **Fact:** `docs/tracking.md` calls the event tracker an "asynchronous persistent framework" and says the persistent state model is verified on mainline Klipper and Kalico. No test log accompanies that claim. **Not independently verified.**
- **Not reviewed:** the unread `docs/` files and the toolhead modules (section 9) may hold more on collision detection. Persistent collision detection beyond what is above could not be confirmed from the files read.

### 13.2 What the current implementation actually does

- **Fact [O]:** `--sync` masks correctly from `[0]`/`[1]` file rows in the first pass, then overwrites the dashboard, the hardware file and the include comments (section 6.7).
- **Fact:** installer reruns rebuild the dashboard with `1` everywhere (statically; not run).
- **Fact:** a read-only report, a "review before apply" step and a post-apply verification do not exist. The UI "verification" screen is hard-coded `[ OK ]`.

### 13.3 Documented intent versus code

| Intent | Code |
|---|---|
| Selections persist in the text dashboard | Regenerated as `1` |
| The dashboard hardware values are the user's | Overwritten with placeholders by sync |
| Toggle list built from the include tree | Built by a directory-wide `os.walk` in the installer |
| Include comments preserved | Dropped when an include is rewritten active |
| Repeated sync is consistent | Run 2 is a no-op only because run 1 broke the dashboard |
| Read-only inspection | Only an accidental no-flag run |
| Master doc: state syncer, sterilizer exist | Present but unreachable or non-importable |

### 13.4 Established requirements (Decision, user-confirmed)

1. Existing `[0]`/`[1]` selections survive sync and installer reruns.
2. Defaults apply only to genuinely new entries or a newly created dashboard.
3. Sync must not unexpectedly overwrite existing hardware settings.
4. Include masking preserves unrelated comments and configuration.
5. Repeated sync behaves consistently (idempotent).
6. Report-only mode inspects and reports without modifying files.

### 13.5 Decisions that are genuinely open

1. **Dashboard key identity (Open, blocks Phase 1):** one row per file (current parser and operator model) or per macro. Rec: file-keyed, with macro rows informational only in the first release.
2. **Do macro rows toggle anything (Open)?** The parser ignores them today. Rec: treat them as read-only labels until file-level behavior is stable.
3. **Plain `#` comments (Open):** may Scrubber treat an ordinary `# [include x]` as a managed include? Rec: no. Manage only `#💤#`.
4. **Hardware file ownership (Open):** the installer derives values from `[extruder]`; the dashboard is meant to hold user selections. Rec: write `jwt_hardware.cfg` only if missing or when the installer is run explicitly.
5. **Event-tracker state (Open):** is the `_JWS_TOGGLE_MANIFEST` macro-variable read an accepted exception to the "no macro variables" decision? Where should tracker settings and the CSV live (the path is hardcoded to `/home/pi`)?
6. **Fate of the quarantine and sterilizer features (Open):** keep, gate behind explicit confirmation, or remove. They can move or delete files.
7. **Action rows (Open):** which system actions are real, and are they one key each?
8. **Include ownership** of `macromanager.cfg` and `jwt_factory_blueprints.cfg`, and which milestone list is authoritative (section 8).

### 13.6 Alternatives for the Macro Manager experience

| Option | Fits existing architecture | Cost | Notes |
|---|---|---|---|
| A. Keep a plain checkbox dashboard | Fully. Parser, operator and dashboard text already exist | Lowest | Novices get no explanation or safety net |
| B. Fully guided wizard | Poorly. The curses UI never calls Scrubber and the dashboard is the persistent store | High, and splits state between wizard and file | Risk of a second source of truth |
| C. Dashboard plus report, review and verify (Rec) | Reuses the dashboard as the state, `scan()` for findings, `Reporter`, and the operator for apply | Moderate | Adds read-only layers around the existing engine |

**Rec:** option C. Do not replace the checkbox dashboard. Add, in order: (1) a report-only mode that prints plain-language findings, with an advanced detail section for power users; (2) a review step that lists exactly which lines would change; (3) an apply step that backs up first; and (4) a verify step that re-scans and confirms the dashboard and config agree. Redesign is not required. **Reusable as is:** `parse_visual_checkboxes` (with fixes), `scan()`, `apply_in_place_masking`, `Reporter`, the dashboard text format, and the installer's conflict badges.

### 13.7 Recommended phased plan (Rec, not approved)

| Phase | Scope | Tests and acceptance |
|---|---|---|
| 0. Decide | Items 1–5 in 13.5 | Written decisions recorded in this document |
| 1. Make sync safe | Remove the dashboard and hardware write from `--sync`; leave an already-active include unchanged; manage only `#💤#`; one normalization on both sides of the include comparison | Re-run the section 6.7 fixture: `[0]`/`[1]` unchanged, hardware sentinels `0.77/5.0/33.3` intact, `# keep` preserved, run 2 identical to run 1, no files created or moved |
| 2. Persist installer reruns | Writer reads the existing dashboard and keeps values; defaults only for absent keys; hardware only if missing | Fixture installer-rerun test: existing `[0]`/`[1]` survive; a new file gets the default `1`; stale entries handled per decision; hardware preserved |
| 3. Report-only mode | New flag that never opens a file for write | Checksums of the whole fixture identical before and after; report lists findings, orphans, mismatches between the dashboard and the actual masked state |
| 4. Review, apply and verify | Diff preview, pre-change backup, post-apply verification | Preview matches the actual diff; restore from backup is byte-identical; verification detects an injected mismatch |
| 5. Novice UX layer | Plain-language wording and recommended actions in the report and the UI | Usability walk-through with a non-expert; every action explains its effect |
| 6. Event tracking and collision | Resolve the open item 5, deploy path, remove the hardcoded `/home/pi` path | Tracker loads under Klipper in a bench test; no write outside the configured directory |
| 7. Documentation | See 13.8 | Each doc claim traceable to a test or labeled unverified |

Choice B remains on hold until Phases 1 and 2 pass.

### 13.8 Documentation to preserve, reconcile or update

- **Preserve unchanged:** `Master_Doc_3.md` (history and rationale; it is not rewritten here), and the original `docs/` set.
- **Reconcile, as annotations in a separate file rather than rewriting the Master doc:** the M1–M9 "VALID" claims against test evidence, the M8 conflict with `roadmap.md`, the MD5 claim, the file locations, and the descriptions of `jws_state_manager.py` and `jws_sterilizer.py`.
- **Update after code changes:** `README.md` run paths, version labels (no unified sequence is invented), `architecture.md`, `dependency.md` and `scope.md` descriptions of `jws_core.py`, and the UI verification screen text.
- **Add after Phase 3:** a short user guide for report mode.

### 13.9 What remains unresolved

The items in 13.5, plus: real Klipper parsing of masked output; live installer behavior (only fixture regeneration is tested in section 14); whether persistent collision detection exists beyond the tracker (unread docs); the 10-Point System Protocol; the Google AI v5.1.0 handoff; and Phases 1, 3, 4A and 4B-remainder.

## 14. MacroManager state contract implementation (2026-10-10)

This records the bounded implementation performed against the current working tree at `c591ccc`; it does not replace the prior fixture results in section 6.7, which exercised the earlier committed code. No live printer configuration was read or changed.

### 14.1 Contract established from current formats

- The plain-text `jwt_macro_manager.conf` dashboard is the source of truth for checkbox state. File rows use `📂 <filename> (MASTER INCLUDE MAP)`, macro rows use the `▶ <macro-name>` child form, and system-action rows use `⚙️ SYSTEM ACTION: <action label>`.
- State identities are separate `file_`, `macro_`, and `action_` keys. File extensions map to `_cfg`/`_conf`; filename hyphens and dots remain distinct, and path separators are percent-encoded. System actions use their complete label rather than collapsing to the word `SYSTEM`.
- Synchronization reads the dashboard and applies file/macro state to the include tree. It does not regenerate the dashboard or write hardware settings.
- System-action values are parsed and preserved as distinct states. Their operations remain unimplemented or unsafe to infer; this work did not enable snapshot, restore, or quarantine behavior.

### 14.2 Changes and evidence

- `scrubber/macro_manager.py`: shared parser/key normalization; binary validation; explicit `persist()` updates only existing recognized checkbox rows, retaining other dashboard text; unknown requested rows raise rather than being silently dropped.
- `scrubber/jws_core.py`: uses the shared parser and reversibly decodes target identities; applies macro states independently of file-row iteration, including to macros inside previously managed masked includes. The installer regeneration bridge remains removed.
- `scrubber/jws_operator.py`: masks/unmasks only active includes or JWS-managed `#💤#` includes, preserving trailing comments and ordinary commented includes; macro masking stops at the next section and can restore its block. State values outside primitive 0/1 raise an error.
- `scrubber/jws_observer.py`: excludes ordinary commented includes from the actionable traversal while continuing to follow JWS-managed masked includes.
- `software/jws_installer.py`: installer regeneration preserves existing parsed states, preserves entries absent from the regenerated scan, and defaults only newly generated rows to `1`. Existing hardware configuration is not overwritten. Dashboard-generation and printer-config write errors are surfaced.
- `tests/test_macro_manager_sync.py`: seven isolated tests exercise parser identities, explicit persistence, file and macro mask/restore, comments, include traversal, repeated `--sync`, and two installer regeneration passes.

### 14.3 Validation and limitations

- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v`: **7 tests passed**. The sync and installer tests used temporary trees; installer writes and backups were confined to the fixture.
- Python AST parsing passed for the six changed/new Python files; `bash -n install.sh` passed; the unstaged `git diff --check` passed; editor Problems reported no errors for changed files.
- The staged diff already present before this task still has whitespace warnings (`git diff --cached --check`); those staged changes were not edited.
- No live Klipper parsing, firmware restart, UI interaction, report-only workflow, or physical behavior was tested. The curses UI still does not edit dashboard state or invoke Scrubber, and the installer still rewrites `printer.cfg` as part of its installation pipeline.
- Generated file rows remain basename-based, so same-named files in different directories are ambiguous. Duplicate macro names share a global macro identity. These cases require a separate target-identity decision before relying on them.
- The implementation establishes the state/sync contract in fixtures; it does not complete the broader Pre-Flight report foundation or system-action lifecycle. Do not treat it as authorization to run the installer or synchronizer against a live printer.

**Update (v5.8.0, after printer test):** the user confirmed manual `jws_core.py --sync` toggles `[include]` lines on the printer; individual macro toggles did not apply.
- **Macro fix (fixture-tested):** macro keys are now file-scoped (`macro_<name>@<file>`) from the dashboard file section the row sits under (`iter_dashboard_rows`, `macro_key_scope`). Previously duplicate macros in `mainsail.cfg` / `mainsail_edit.cfg` shared one key and the last row won, so toggling the first copy was overridden. Installer adopts a legacy unscoped state once on upgrade.
- **Trigger (new, NOT runtime-verified):** `jabberwocky_dist/jwt_sync_bridge.cfg` (placeholders filled by the installer: config dir, python, core path, Moonraker port) defines `jws_sync_core` + `JABBERWOCKY_SYNC_NOW`, which runs `--sync && curl .../printer/firmware_restart`. The installer installs `gcode_shell_command.py` (KIAUH source) into `~/klipper/klippy/extras` (override `JWS_KLIPPER_DIR`) and includes the bridge only if the extension is present. Removed the hardcoded `/home/tlam` bridge and the dead `_JWS_DASHBOARD_WATCHER` from `jwt_clutch_logic.cfg`.
- **Tests:** 9/9 pass. Still unverified: extension download, shell command quoting, Moonraker localhost restart permission, on a real printer.
- Open: directory-qualified include targets still match by basename only.

### 14.4 Closeout — NOT accepted: printer test failed (v5.8.0 update)

**Superseded claim:** the earlier "accepted working baseline" was wrong. Rsync'd to a real printer, dashboard toggles produced no change in `printer.cfg` after FIRMWARE_RESTART.

**Diagnosis (static, not yet runtime-verified):** FIRMWARE_RESTART does not run `jws_core.py --sync`. The only automatic trigger is `jws_sync_core` / `JABBERWOCKY_SYNC_NOW` in `jabberwocky_dist/jwt_clutch_logic.cfg`; it hardcodes `/home/tlam/...`, needs the third-party `gcode_shell_command` extension (not installed by the installer), and its watcher reads a macro variable, not the dashboard file. Fixture tests passed because they call `main()` with `--sync` directly.

**Changed in v5.8.0:** version bumped in core (`BUILD_VERSION`, printed in the run banner), operator, observer and installer (`VERSION_STRING`, shown in the dashboard header); dashboard step 4 now says to run `python3 ~/Jabberwocky-APPS/scrubber/jws_core.py --sync` before restart.

**Open / unverified:** (a) printer-side result of manual `--sync`; (b) duplicate basenames collapse to one `file_` key and macro keys are not file-scoped, so duplicate-file macro rows (`[D?]` vs `[D!]`) share state; (c) directory-qualified includes do not match basename rows; (d) an automatic restart-time trigger needs a design decision.

The MacroManager state-management and synchronization baseline is accepted. The seven focused fixture tests pass, including distinct file/macro/action identities, persistence through two installer regenerations, file and macro enable/disable, preservation of comments and hardware settings, and repeat-sync consistency. Python AST checks, `bash -n install.sh`, and the unstaged `git diff --check` also pass.

No demonstrated defect remains that blocks this bounded contract. Known limitations above—basename collisions, duplicate macro-name identity, unimplemented system-action effects, absent report-only/UI workflow, and lack of live Klipper verification—do not block acceptance of the tested baseline. No live printer configuration was accessed, no firmware was restarted, and no Probe or ASC work was started. Keep the existing staged, unstaged, and untracked work intact. The next bounded development task is Jabberwocky Probe; MacroManager should not be reopened unless subsequent work demonstrates a concrete defect.

### 14.5 v5.9.0 scanner / dashboard / sync rework (2026-10)

**Changed:** `scrubber/jws_observer.py` (Klipper-order include crawl, inventory with live/masked/commented origin), `scrubber/jws_analyzers.py` (new plugin registry of findings: blockers, duplicates, hardware duplicates, disarmed/unloaded/orphan files, backups), `scrubber/jws_dashboard.py` (new: StateBook, adoption plan, render with hardware section on top and report), `scrubber/jws_operator.py` (resolved-path include matching, plain-`#` adoption, safe block ends), `scrubber/jws_core.py` (`--config-dir --report --sync --restart-if-changed --moonraker-url`, lock/cooldown), `software/jws_installer.py` (paced pipeline with progress callback, adoption backups, guarded sweep to quarantine), `jabberwocky_dist/jwt_sync_bridge.cfg` (relative paths from installer, `_JWS_STARTUP_SYNC` delayed gcode), `software/curses_ui.py` (plain-language UI, paced), README (clone steps restored, Klipper-won't-start section).

**Truth table:** plain `#` entry new to dashboard -> seeded `[0]` and rewritten to managed mask (backup first); existing dashboard value always wins; hardware blocks and orphans are report-only; sweep is a one-shot action row, moves never deletes.

**Tests:** `tests/test_macro_manager_sync.py` + `tests/test_scanner_v59.py`: 18 pass, temp fixtures only. `config/` untouched.

**Unverified on a real printer:** gcode_shell_command quoting, Moonraker restart permission from the sync script, startup hook timing (expect double restart when changes applied), extension download.

**Clean build:** remove/gitignore repo-root `config/`; on the printer clear stale `__pycache__`, old `printer_*.bak`, old `jabberwocky_quarantine/` and any previously stacked banner blocks.

### 14.6 Final MacroManager baseline result (v5.9.0)

**Decision:** MacroManager (state contract, scanner, dashboard, sync, pre-flight report) is **complete at baseline**. Do not reopen it unless a concrete defect emerges during later work. Next work: Jabberwocky Probe, then ASC Stage 1.

**On-printer validation (successful):** installer via `install.sh` / curses option 1; scan and report; include toggles; macro toggles; restart-triggered sync.

**Automated tests:** 20 passing (`tests/test_macro_manager_sync.py`, `tests/test_scanner_v59.py`), temp fixtures only. Repo-root `config/` verified unmodified (hash unchanged).

**Final polish included:** masked macro blocks get one blank spacer line (removed on unmask; mask/unmask round-trips byte-identically); disabled `#[include]` lines with no file are a WARNING (`COMMENTED_MISSING`) with remedy; curses verification/summary screens slowed.

**Remaining unvalidated items:**
- System-action rows (SNAPSHOT BACKUP / RESTORE hold persistent state only, actions unimplemented; SWEEP TO QUARANTINE is unit-tested in temp trees only, not on the printer).
- `gcode_shell_command` extension download.
- Moonraker restart permissions for the sync script.

**Clean build:** remove or `.gitignore` repo-root `config/`; on the printer clear stale `__pycache__`, old `printer_*.bak`, and old `jabberwocky_quarantine/`.

## 15. Probe release implementation — budget-mode handoff (2026-10-10)

### 15.1 Current status
- MacroManager baseline: **achieved and user-validated on the printer** (section 14.6). Do not reopen unless a concrete defect emerges.
- Jabberwocky Probe: **report-only audit complete**. No Probe code, config, tests or docs were changed by the audit.

### 15.2 Audit findings — CONFIRMED (read from files; no probe macro was executed)
- `software/jw_probe/` holds 12 `jwprobe_*.cfg` files (~3,200 lines, 35 `JWP_*` macros). `jwprobe_entry.cfg` includes globals, profile, hardware, logic, homing, onboarding and autoz; QGL / bed-mesh / Z-tilt wrappers are optional and commented out.
- Collision detection exists as G-code macros in `jwprobe_logic.cfg`: `JWP_COLLISION_WATCHDOG` (delayed_gcode, line 188), `_JWP_CONFIRM_COLLISION_AT`, `_JWP_RUN_SCHEDULED_COLLISION_CHECK`, `_JWP_CONFIRM_COLLISION_PASSBY`; variables in `jwprobe_globals.cfg` lines 47–85; Low/Medium/High sensitivity; reactive capture with 2-of-3 confirmation plus scheduled pass-by check.
- `scrubber/jwp_event_tracker.py` (154 lines) is a separate Klipper extras module: impact mitigation (`EXCLUDE_OBJECT`, Z+5, `PAUSE`) and blob-fault `invoke_shutdown`. No `.cfg` or installer references it.
- Tracker reads `_JWS_TOGGLE_MANIFEST` (not defined anywhere in the repo) and writes to a hardcoded `/home/pi/printer_data/config/jwp_calibration_profile.csv`, silently skipping if missing.
- Runtime variables live outside the deployable folder: `~/printer_data/config/jwprobe_runtime_vars.cfg`.
- `software/jw_probe/docs/jwp_config_preflight.py` (~2,400 lines) compiles; it was not run.
- Probe README, preflight script and `testing_game_plan.md` use `jabberwockyprobe/…` paths that do not exist in the repo (`software/jw_probe/tools/` holds only a README).
- Curses option 3 and the installer have no Probe install path.
- No automated tests exist for Probe code. Evidence docs: `jabberwocky-05/docs/{collision_calibration,testing_game_plan,roadmap}.md`.

### 15.3 SUSPECTED (unverified; must be confirmed before acting)
1. `JWP_COLLISION_WATCHDOG` has `initial_duration: 0`, and the only `UPDATE_DELAYED_GCODE` for it found by grep is its own re-arm (`jwprobe_logic.cfg:255`). It may never start. Something outside the grepped files might arm it.
2. The macro watchdog and the Python tracker overlap, and which is authoritative is undecided.
3. `jwprobe_vars.cfg` and `scrubber/jwp_build.py` may be unused leftovers.
4. Probe macros may need exclusion from casual dashboard toggling (not checked).

### 15.4 NEXT TASK — bounded Probe release implementation (in order)
1. **Verify watchdog startup and re-arming.** Trace every path that arms `JWP_COLLISION_WATCHDOG` and its re-arm on all branches of its body (including early exits). Fix only if the gap is demonstrated; gate by `collision_check_enabled`. Add a static test that every `delayed_gcode` is armed by `initial_duration` or by a caller.
2. **Establish the macro-vs-tracker relationship from existing evidence** (roadmap M4 says the tracking loops were ported to Python daemons; `tracking.md`; `testing_game_plan.md` symlinks the tracker by hand; the cfg header comments). Do not guess. If evidence is inconclusive, stop and ask the user the single specific question. Only then fix the tracker's hardcoded path and the `_JWS_TOGGLE_MANIFEST` dependency, if the tracker is kept.
3. **Focused tests** using temp fixtures and the existing `build_inventory` on `software/jw_probe/`: includes resolve, no duplicate macros, referenced macros exist, collision macros present, watchdog arming.
4. **Safe, idempotent install path:** copy to the config folder (or settle the layout, then make docs match), add one guarded `[include]`, never overwrite `jwprobe_runtime_vars.cfg`, never touch the user's other config, back up `printer.cfg` first, re-running changes nothing. Test only in temp trees.
5. **Consistent documentation:** correct the `jabberwockyprobe/…` paths in the Probe README, preflight help text and test plan to match the chosen layout; update this handoff (no second handoff doc).

### 15.5 Strict constraints
- Preserve all existing staged, unstaged and untracked work. HEAD is `c591ccc`; nothing is committed.
- No broad research or redesign, no MacroManager rework, no ASC work.
- No live printer deployment, no live config changes, no firmware restart; never touch repo-root `config/`.
- Smallest justified changes; fix only demonstrated defects.
- Version codes must be bumped on any revised file so builds are identifiable.

### 15.6 Required finish line
Report: files changed, tests run and actual results, remaining limitations, and a concise physical validation checklist (from `testing_game_plan.md` Stages 1–5: config loads, dock alignment, Auto-Z, collision pin clearance, forced-crash watchdog test, false-trigger check during a print). Then stop and wait for review. Do not continue to ASC.
