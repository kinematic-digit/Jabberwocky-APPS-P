# Jabberwocky-APPS — Development Workflow: Path to Completion

**Document:** `JW-APPS_development_handoff.md`  
**Purpose:** Establish a development handoff that allows a coding agent to inspect, implement, test, and report on the remaining work while preserving the project's intended behavior.

## 1. Overall objective

Bring Jabberwocky-APPS to a completed or substantially completed state through a series of bounded development tasks.

The remaining work falls into three workstreams:

1. **Macro Manager** — finish backups, quarantine handling, include reporting, and the power-user report.
2. **Jabberwocky Probe (KANE)** — verify and complete collision detection, persistent event handling, and installation.
3. **Jabberwocky Toolhead (ASC)** — move from demonstrated telemetry measurement into guided calibration, persistent monitoring, and eventually confidence-aware inference and intervention.

The goal is to complete these components systematically, not to redesign working systems unnecessarily or expand the scope of each task.

### 1.1 Development principles

The following principles apply to every workstream.

**Treat the existing implementation as unverified.**

The current code is evidence of what has been implemented, not proof of what the software is supposed to do. Compare it against the intended workflow and acceptance criteria. Do not redefine the requirements to match existing behavior.

**Establish intent before implementation.**

For each task, determine:
- What the user expects to happen.
- What the software currently does.
- Which parts of the current implementation are correct and should be preserved.
- What is missing, incorrect, or insufficiently tested.
- What observable result will demonstrate completion.

**Preserve existing data.**

Backups, quarantined files, profiles, and other recovery information must not be silently overwritten or discarded. If a destination already exists, handle the collision explicitly and preserve both the existing data and the ability to recover from failure.

**Distinguish evidence from assumptions.**

Reports and test results must distinguish verified behavior from inferred behavior, untested cases, and unresolved questions.

**Test the intended behavior, not merely the existing behavior.**

Tests can reproduce an existing defect if they encode the wrong expectation. Review test assumptions against the intended workflow before treating passing tests as proof of correctness.

**Keep tasks bounded.**

The agent should work autonomously through implementation, testing, and corrections within the agreed scope. If it encounters an architectural ambiguity that could materially change the intended behavior, it should stop and report the issue rather than inventing a solution.

**Require evidence of completion.**

At the end of each task, the agent must report what changed, what was tested, which acceptance criteria passed, and what remains uncertain or incomplete.

---

# 2. Workstream A — Macro Manager

## Objective

Complete the remaining Macro Manager functionality, including backup reliability, quarantine safety, include reporting, and the Curses menu's power-user report.

The dashboard and reporting functionality are substantially developed. The remaining work should focus on identifying gaps, implementing the required behavior, and verifying that existing functionality remains intact.

### A1. Profile backup and recovery

**Objective:** Ensure backups are reliable, predictable, collision-safe, and usable for recovery.

The agent must inspect the existing backup workflow and establish how it behaves under normal operation and failure.

Required outcomes:

- Backups are created reliably when required.
- Backup names are predictable and sufficiently unique.
- An existing backup is never silently overwritten.
- Destination collisions are handled explicitly.
- Failed backup operations do not leave the user without the original or recovery data.
- Existing backup files remain intact.
- The system provides useful diagnostics when a backup cannot be completed.

Testing must include:
- Normal backup creation.
- Multiple backups created close together.
- A pre-existing destination with the same proposed name.
- A failed or interrupted operation where practical.
- Verification that the original file and existing backups remain recoverable.

The agent must inspect the actual implementation before deciding whether filename generation, collision handling, or the recovery workflow needs to change.

### A2. Quarantine of orphaned files and backups

**Objective:** Ensure the quarantine process identifies eligible files and handles them safely without destroying existing data.

Required outcomes:

- Files eligible for quarantine are identified consistently.
- Files that should be retained are not incorrectly classified as orphans.
- Quarantine destinations are predictable.
- Existing quarantine contents are preserved.
- A destination collision never results in a silent overwrite.
- The process reports which files were moved, retained, skipped, or could not be processed.
- Recovery remains possible after the operation.

The agent must first audit the eligibility rules. It must not assume that every file without an obvious association is disposable.

Testing must cover:
- Normal quarantine operations.
- Existing destination files.
- Repeated runs.
- Mixed sets of eligible and ineligible files.
- Failure handling and preservation of recovery data.

If the intended treatment of a particular file category is unclear, document the ambiguity before implementing a potentially destructive rule.

### A3. Commented includes with no associated child

**Objective:** Identify and report commented include directives that no longer have an associated child file or macro relationship.

The report should help the user determine whether an include needs to be reconnected, whether a child file is missing, or whether the entry is intentionally retained.

Required outcomes:

- Commented includes are recognized reliably.
- Active includes and commented includes are distinguished.
- Missing targets are distinguished from valid targets.
- The presence or absence of an associated child is reported accurately.
- Commented include entries follow the same standard masking convention used elsewhere in Macro Manager.
- The report provides actionable information rather than a generic warning.

An include without a macro child must not automatically be classified as an orphan. The agent must inspect the project’s actual association rules and determine which relationships are expected.

Testing should include:
- Active includes with valid targets.
- Commented includes with valid targets.
- Commented includes whose targets are missing.
- Commented includes with no associated child.
- Relevant variations in formatting and trailing comments.
- Cases involving ambiguous or duplicate include relationships.

The implementation must preserve the original configuration and its intended meaning.

### A4. Curses menu item 4 — Power-user report

**Objective:** Complete the existing Curses menu's item 4 as a report-only power-user function.

This function is essentially Macro Manager stripped of its interactive components. It should reuse existing reporting and data-processing logic where practical rather than duplicate the entire implementation.

This is part of the Macro Manager workstream, not a separate project.

Required outcomes:

- Item 4 is accessible through the Curses menu.
- It produces a useful, accurate report of the current configuration and relevant files.
- It reuses existing Macro Manager reporting logic where appropriate.
- It does not expose interactive controls or initiate state-changing actions.
- It does not modify configuration files, profiles, backups, quarantine contents, or application state.
- It reports relevant findings clearly enough for a power user to understand the current situation.

The agent should inspect the existing menu implementation and its dependencies during the initial Macro Manager audit. If, as expected, this is a straightforward addition, implement it alongside the other Macro Manager changes.

Testing must verify:
- The menu item works as intended.
- The report contains the expected information.
- Relevant existing report data is represented correctly.
- The operation is read-only and has no unintended side effects.
- Existing menu functions continue to work.

### Macro Manager acceptance criteria

The workstream is complete when:

1. Backup creation and recovery behavior is reliable and tested.
2. Existing backup files cannot be silently overwritten.
3. Quarantine operations preserve existing data and handle collisions safely.
4. Include reporting correctly distinguishes the relevant states.
5. Curses menu item 4 produces the intended power-user report without modifying application or user data.
6. Existing dashboard and reporting behavior remains intact.
7. Relevant tests pass, including regression tests.
8. The agent provides a concise implementation summary and evidence supporting each acceptance criterion.

---

# 3. Workstream B — Jabberwocky Probe (KANE)

## Objective

Finish verification and installation of the Jabberwocky Probe's collision detection and event-handling functionality.

Collision detection is already substantially implemented. The task is to establish what remains, verify the real behavior, and complete the bounded work without unnecessarily redesigning the system.

The agent must inspect the current implementation before deciding what changes are needed.

## B1. Finalize collision detection

Required outcomes:

- Collision detection behaves as intended.
- Normal probing and deployment do not generate unintended collision events.
- Bed contact during normal operation does not produce inappropriate collision triggers.
- Deployed and stowed states are handled correctly.
- Expected probing behavior remains intact.
- Faults and unexpected states are handled safely.
- Collision events are distinguishable from ordinary probe activity.

Testing should exercise the actual state transitions and failure cases rather than relying only on static inspection or simulated success paths.

The agent must identify any behavior that cannot be verified in software tests and explicitly mark it for physical testing.

## B2. Verify persistent event handling

**Objective:** Ensure KANE's event handling remains consistent across relevant probing, deployment, and collision states.

Required outcomes:

- Relevant state transitions are handled consistently.
- Collision activity is distinguished from normal probe activity.
- Persistent event handling does not depend on fragile timing assumptions.
- Where event-driven behavior is required, it is not inadvertently replaced with unreliable polling.
- Recovery and error states are handled predictably.
- Klipper timing constraints are respected, including avoiding fragile scheduling that could produce timer-too-close errors.

The agent should inspect the current event model, macro interactions, and any supporting code before proposing changes.

Testing must cover ordinary operation, relevant transitions, collision conditions, and failure/recovery behavior.

## B3. Finish the installation wizard

**Objective:** Complete installation through the Mainsail console.

Required outcomes:

- Instructions follow a logical sequence.
- Each step validates what it can reasonably validate.
- Configuration updates are predictable.
- Errors produce useful diagnostics.
- The user can complete installation without needing to understand the internal implementation.
- The wizard verifies the resulting configuration where possible.
- Failed or incomplete installation does not silently leave the system in an inconsistent state.

The agent should reuse the existing installer structure and conventions where appropriate.

### KANE acceptance criteria

The workstream is complete when:

1. Collision detection behavior is verified against the intended operating states.
2. Normal probe activity and collision events are distinguished correctly.
3. Persistent event handling is reliable within Klipper's timing constraints.
4. The installation wizard works through the Mainsail console.
5. Relevant tests pass.
6. Remaining physical-verification requirements are explicitly documented.
7. The agent provides a summary of changes, test evidence, and any remaining limitations.

---

# 4. Workstream C — Jabberwocky Toolhead (ASC)

## Objective

Develop ASC from demonstrated telemetry measurement into a guided calibration and monitoring system, followed by research into persistent inference and safe intervention.

ASC is a larger, research-oriented workstream. It should be divided into phases so that demonstrated capabilities are not confused with future goals.

Phase 0 has demonstrated that telemetry can be measured and that different observed states can produce distinguishable data. That is a useful starting point, but it does not establish that every condition can be identified reliably or across different machines.

## Phase 0 — Telemetry measurement and characterization

**Status:** Initial measurement and differentiation have been demonstrated. Further characterization and validation may still be required.

Objective: Establish which telemetry measurements and signatures are useful, repeatable, and meaningfully associated with known operating conditions.

Potential measurements include StallGuard readings, load-related behavior, stall events, oscillation, voltage/current where meaningfully available, and changes over time.

The agent must establish which signals the current hardware and software can actually provide. It must not assume that every potentially useful measurement is available or reliable.

Required outcomes:

- Relevant telemetry can be captured and recorded.
- Different known conditions can be compared.
- Candidate signatures are characterized.
- Repeatability is measured rather than assumed.
- Limitations and ambiguous cases are documented.
- Where practical, measurements are checked against known conditions or controlled tests.

The purpose of Phase 0 is to establish an evidence-based foundation for later calibration and monitoring.

## Phase 1 — Guided calibration and automatic monitoring

**Objective:** Use characterized telemetry profiles to guide calibration of a new or freshly serviced extruder installed on the Jabberwocky Toolhead.

The workflow should be accessible through a wizard using the Mainsail console. Macros should coordinate the workflow where appropriate, while any sampling or telemetry collection that requires code changes must respect Klipper and MCU timing constraints.

### Step 1: Empty-extruder motor calibration

With no filament loaded:

- Measure the extruder motor's behavior.
- Compare the measurements against the relevant manufacturer recommendations or established baseline, where applicable.
- Account for the physical screw adjustment used to position the motor on its pivot.
- Check the drive gear's mechanical backlash where the system permits meaningful measurement.

The system must distinguish an observed measurement from an inferred mechanical explanation.

### Step 2: Mechanical tension configuration

With the tension screws installed:

- Verify the intended tension configuration.
- Confirm that the anti-squish screw is set correctly.
- Capture the resulting telemetry.
- Compare the measurements with the appropriate baseline.

The agent must establish which aspects can be validated automatically and which require user confirmation.

### Step 3: Filament-loaded measurement

With filament loaded:

- Capture telemetry under the appropriate operating conditions.
- Compare the result with the unloaded and calibrated baselines.
- Investigate whether the observed changes can help identify downstream friction or resistance.

Potential causes such as bent filament or a kinked Bowden tube must be treated as hypotheses unless the telemetry has been validated sufficiently to distinguish them.

### Step 4: Sustained extrusion verification

Run a sufficiently long extrusion test to collect meaningful telemetry.

The system should evaluate whether the measurements remain consistent with the expected operating profile and whether there are signs requiring further investigation.

A short, inconclusive sample must not be treated as proof that the extruder is correctly calibrated.

### Step 5: Save the validated profile

Once the calibration workflow passes:

- Save a timestamped profile.
- Preserve previous profiles.
- Store sufficient metadata to understand the conditions under which the profile was captured.
- Ensure the profile can be retrieved and used in later monitoring.
- Do not mark an inconclusive or failed calibration as successful.

### Phase 1 acceptance criteria

Phase 1 is complete when:

1. The wizard follows a repeatable calibration workflow.
2. Telemetry can be captured and compared against the intended baselines.
3. Failed and ambiguous results are not falsely reported as successful.
4. Validated profiles are saved and can be retrieved.
5. Previous profiles and relevant metadata are preserved.
6. Repeatability has been tested and its limitations documented.
7. Klipper timing constraints are respected.

---

## Phase 2 — Persistent inference and intervention

Phase 2 is divided into two stages. The first gathers evidence and validates signatures; the second uses that evidence to develop bounded inference and intervention.

The two stages should not be collapsed into a single implementation task.

### Phase 2, Stage 1 — Persistent monitoring and data collection

**Objective:** Observe operating behavior over time, capture unusual telemetry, and gather enough evidence to determine which signatures can be interpreted reliably.

Required outcomes:

- Persistent monitoring detects telemetry that differs meaningfully from the relevant baseline.
- The system captures the relevant measurements and operating context.
- The user is prompted to select a likely condition from a list of candidate explanations.
- The user's feedback is associated with the captured data for later analysis.
- The system records ambiguous cases instead of forcing a confident classification.
- Monitoring and data collection do not automatically intervene in printer operation.

The resulting dataset should support investigation of:
- Signature repeatability.
- False positives and ambiguous results.
- Variations between machines.
- Variations across operating conditions.
- The relationship between observed telemetry and confirmed mechanical states.

This stage requires testing across diverse machines and conditions. A signature that works on one extruder should not automatically be assumed to work on all extruders.

**Stage 1 deliverable:** A useful collection of telemetry, operating context, and user-confirmed observations, together with an evidence-based assessment of which signatures are sufficiently repeatable to support further development.

### Phase 2, Stage 2 — Confidence-aware inference and safe intervention

**Objective:** Use the validated Stage 1 evidence to develop an inference system that can recognize relevant operating conditions and, where justified, perform bounded interventions.

Required outcomes:

- Inference is based on validated evidence rather than a single unexplained threshold.
- The system accounts for uncertainty and confidence.
- Ambiguous evidence does not automatically trigger intervention.
- Any intervention has clearly defined limits and safe operating conditions.
- Decisions and outcomes are logged.
- Controlled testing is completed before broadening the system's scope.

This stage is a larger research and development effort. Its schedule and resource requirements should be estimated separately from the work needed to finish Macro Manager and KANE.

**Stage 2 deliverable:** A tested, confidence-aware inference and intervention system with documented limitations and safety boundaries.

### ASC acceptance criteria

Phase 0 is sufficiently complete to support later phases when its relevant telemetry measurements and candidate signatures have been characterized and their limitations documented.

Phase 1 is complete when the calibration and profile workflow meets its acceptance criteria.

Phase 2, Stage 1 is complete when persistent monitoring and data collection produce a useful, validated dataset.

Phase 2, Stage 2 is complete only when the inference and intervention behavior has been validated through controlled tests and operates within documented safety boundaries.

Completion of one phase must not be represented as proof that later phases are complete.

---

# 5. Shared development and agent workflow

Use the following workflow for each bounded task.

## Step 1 — Establish the current state

Inspect the relevant source code, project instructions, configuration, and tests.

Identify:
- Existing behavior.
- Intended behavior.
- Known defects.
- Existing tests and their assumptions.
- Missing test coverage.
- Dependencies and protected behavior.

Do not assume that an existing function works correctly merely because it exists or has passing tests.

## Step 2 — Define the intended outcome

Before modifying code, establish a concise description of the required behavior.

Include:
- Expected inputs and outputs.
- Normal operating behavior.
- Relevant edge cases.
- Failure and recovery behavior.
- Protected data and existing functionality.
- Observable acceptance criteria.

If the intended behavior cannot be established from the project and this handoff, identify the ambiguity instead of guessing.

## Step 3 — Prepare a self-contained implementation plan

The plan should specify:
- Files and components likely to be affected.
- Required behavior changes.
- Dependencies.
- Tests to add or update.
- Acceptance criteria.
- Relevant safety and data-preservation constraints.

The plan should be detailed enough that the coding agent can work without repeatedly relying on the original conversation.

## Step 4 — Implement autonomously within the agreed scope

Once the plan is established, allow the coding agent to implement the changes, run tests, investigate failures, and correct defects.

The agent should not stop after producing a proposal if the task has been authorized for implementation.

It should continue until:
- The acceptance criteria are satisfied.
- Tests have been run and relevant failures addressed.
- The implementation is ready for human review.

The agent must not silently expand scope or make a consequential architectural decision that contradicts the established intent.

## Step 5 — Return evidence of completion

The agent's final report must contain:

1. **Changes made:** A concise description of the implementation.
2. **Files affected:** The important files changed.
3. **Tests run:** Commands or test groups executed and their results.
4. **Acceptance criteria:** Which criteria passed, failed, or remain unverified.
5. **Data safety:** Confirmation of how relevant files, backups, profiles, and quarantine contents were protected.
6. **Limitations:** Any unresolved issues or behavior requiring physical testing.
7. **Human review:** What the user should specifically test or inspect.

The agent must not claim success merely because the code compiles or a limited test suite passes.

## Step 6 — Human verification and correction

The user evaluates the result in the actual project and reports any discrepancies.

The next iteration should focus on the observed discrepancy, not restart the entire task without reason.

The implementation is accepted only when the intended behavior has been verified to a satisfactory level.

---

# 6. Resource and model-cycle tracking

Because local and cloud coding agents have different costs and capabilities, development should include lightweight tracking of actual task effort.

The goal is to learn which types of work are best suited to local models and which justify the expense of a cloud agent.

For each task, record:

| Metric | Purpose |
|---|---|
| Task identifier | Identify the work being measured |
| Estimated complexity | Record the expected difficulty before implementation |
| Estimated resource budget | Establish an initial allowance for model calls or cost |
| Model and agent | Record which model and framework performed the work |
| Input/output tokens | Record usage where available |
| Model calls or cycles | Record the number of requests and correction iterations |
| Elapsed time | Measure wall-clock duration |
| Human review and testing time | Capture effort outside the agent |
| Verification outcome | Record whether the intended result passed review |
| Actual cloud cost | Track billed usage where available |
| Local runtime/resource use | Track local execution where practical |

Use the existing accounting available from Pi, Ollama, or the cloud provider before building additional tracking software.

Avoid double-counting the same request at different layers. For example, an agent's model-call record and Ollama's corresponding request may describe the same operation rather than two separate calls.

Initially, the goal is to gather enough information to estimate future tasks more accurately, not to create another substantial software project.

Over time, compare:
- Estimated effort against actual effort.
- Local versus cloud performance on similar tasks.
- Correction cycles and repeated failures.
- Human verification effort.
- Successful completion rates.
- Actual costs and elapsed time.

The most useful measure is not simply how many tokens a model consumes. It is how much verified progress it produces for the resources spent.

---

# 7. Provisional work order

The following sequence is a starting point. Adjust it if the initial audits reveal important dependencies.

### Task 1 — Macro Manager audit and completion

Inspect the existing implementation and tests, then complete:
- A1: Profile backup and recovery.
- A2: Quarantine safety.
- A3: Commented includes without associated children.
- A4: Curses menu item 4 power-user report.

Keep all four deliverables in the Macro Manager workstream. Item 4 should be implemented alongside the other changes if the initial audit confirms it is as straightforward as expected.

### Task 2 — KANE collision verification

Establish the current behavior, close remaining gaps, and verify collision detection against the intended operating states.

### Task 3 — KANE persistent events and installation wizard

Verify event handling, resolve timing-related defects, and complete the Mainsail-console installation workflow.

### Task 4 — ASC Phase 1 planning and implementation

Review the current telemetry implementation, establish which parts of Phase 0 are sufficiently validated, and prepare the guided calibration workflow.

Implement Phase 1 against its acceptance criteria.

### Task 5 — ASC Phase 2, Stage 1

Define the persistent monitoring and data-collection design, then develop the dataset and validation process.

### Task 6 — ASC Phase 2, Stage 2

Use the validated Stage 1 evidence to plan and implement confidence-aware inference and bounded intervention.

This final stage should be estimated and managed separately because its scope depends on the results of the earlier research.

---

# 8. Instructions to the coding agent

When receiving a task from this handoff:

1. Read the relevant project instructions and inspect the current implementation.
2. Treat the implementation as unverified; compare it against the intended behavior.
3. Identify relevant existing tests and determine whether their assumptions are correct.
4. Produce a concise audit and implementation plan before making consequential changes.
5. Implement the agreed task and continue through testing and corrections.
6. Preserve existing user data and recovery information.
7. Do not silently overwrite files or alter expected behavior to make tests pass.
8. Do not claim that an unverified inference is a measured fact.
9. Stop and report if a significant ambiguity affects the architecture, safety, data preservation, or intended behavior.
10. Return a clear report of changes, test results, acceptance criteria, limitations, and the remaining human-verification steps.

**The goal is verified completion, not merely code generation.**

## Additional Macro Manager Requirements — Follow-up

These requirements supplement the existing handoff and original Copilot
Cloud Agent requirements. They do not replace the original intended behavior.

### A. Synchronization and configuration state

The dashboard is a control surface, not merely a generated report.

The intended workflow is:

1. The user changes an include, macro, or hardware-control selection.
2. The desired state persists across regeneration, installation, and sync.
3. Synchronization determines the required configuration changes.
4. The correct configuration blocks are masked or unmasked using the
   project's established custom convention.
5. The system reports whether changes were written successfully.
6. The system explains whether Klipper must reload or restart before the
   change takes effect, and whether that action is currently possible.
7. The result is verified wherever technically possible.

Dashboard generation and configuration synchronization are separate
responsibilities. Regenerating the dashboard must not silently reset user
selections. Updating the dashboard alone does not constitute a successful sync.

Trace the complete path from dashboard selection through parsing, state
persistence, file association, masking/unmasking, sync invocation, and
Klipper reload/restart behavior.

The observed failure remains an important acceptance case:
an include in mainsail.cfg was masked; the user enabled it in the dashboard
and restarted, but the configuration did not change as expected. Similar
behavior was observed with macros. Establish the actual cause from code and
tests rather than assuming it.

Do not assume that --sync should create a backup. Treat synchronization,
backup creation, dashboard regeneration, and installation as distinct
operations unless the established architecture explicitly coordinates them.

### B. Klipper limitations and user guidance

Identify any genuine Klipper limitations or operational blockers affecting
synchronization, configuration changes, reloads, or restarts.

For each verified blocker:
- Explain what it prevents.
- Explain what the user will observe.
- Give safe, practical steps the user can take, where a workaround exists.
- Clearly distinguish an automatic action from one requiring user intervention.
- Record documentation that should be added to the README or other user
  documentation at PR time.

Do not invent workarounds or claim that a change has taken effect when that
cannot be verified.

### C. Dashboard hierarchy

Hardware configuration blocks must appear at the top of the dashboard or
report as system-level controls. They must be distinguishable from ordinary
macros and includes.

Preserve meaningful associations between each dashboard control and its
actual configuration target.

### D. Scanner modularity and orphan detection

Maintain the modular structure of `software/macro_manager/`. New scanners,
file types, and checks should be addable without requiring a rewrite of the
entire scanner or orchestration system.

Identify files that appear to be complete orphans, including relevant
unused legacy modules. Provide evidence for each finding and distinguish:
- Confirmed unused/orphaned files.
- Files with no obvious direct references but possible dynamic or external use.
- Configuration files that are valid even if they have no macro child.
- Files whose purpose cannot yet be established.

Do not delete, move, or quarantine suspected orphans automatically.

### E. Curses user experience

Simplify menu wording so a novice user can understand the choices and their
consequences without being intimidated by technical language.

Improve operation feedback. Where useful, show progress, explain the current
stage, and present meaningful results on the next screen.

The interface may be deliberately paced enough for users to read important
feedback, but avoid arbitrary delays that make routine use unnecessarily slow.

Update revision numbers consistently wherever the implementation requires
them. Do not change unrelated versioning or project metadata without cause.

### F. Final report and clean-folder requirement

At completion, report:
- Changes made and files affected.
- Tests executed and their results.
- Acceptance criteria passed, failed, or still requiring physical testing.
- Remaining limitations and user actions required.
- Verified Klipper blockers and proposed documentation updates.
- Suspected or confirmed orphan files.
- Whether a clean folder is required for further testing or release.
- If one is required, what must be retained, rebuilt, or copied and why.

Do not silently delete or replace existing user data, backups, quarantine
contents, configuration files, or recovery information.