# Recording Cross-Project Reuse Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement
> this plan task-by-task.

**Goal:** Make GUI-recorded scenarios as reusable as possible across Unity projects
by recording variable-first selectors with multi-strategy fallbacks (Unity
hierarchy/UIA/coordinate), and by post-processing recorded steps into a
cross-project friendly shape.

**Architecture:**

- Record richer selector graphs at capture time (primary selector + ordered fallbacks).
- Exporter generates Robot code that can execute mixed-strategy fallback chains.
- Recording stop hook normalizes hierarchy paths into variables (profile-ready)
  to reduce per-project edits.

**Tech Stack:** Python (PySide6), Robot Framework suite generation, Unity bridge
(HTTP), JSON schema v2.

## Task 1: Unity Bridge Parity (UPM vs Legacy)

**Files:**

- Modify: `D:\ghws\robotframework-unity-editor\unity-package\Editor\RobotFrameworkUnityBridge.cs`
- Test: `D:\ghws\robotframework-unity-editor\tests\test_bridge_parity.py`

**Step 1: Write failing test.**

- Assert that the UPM C# file contains:
  - selection state fields (`selection_version`, `selection_changed_unix_ms`)
  - `/v1/selection/wait`
  - any-root wildcard handling (`allowAnyRoot`)

**Step 2: Run test to verify it fails.**

Run: `python -m pytest -k bridge_parity -v`
Expected: FAIL (missing strings)

**Step 3: Update UPM C# file to match legacy capabilities.**

- Add selection state tracking + wait endpoint.
- Add wildcard root selection support (`*/Child/...`).

**Step 4: Run full verify.**

Run: `./scripts/verify.ps1`
Expected: PASS

**Step 5: Commit.**

Commit message: `feat: align unity bridge UPM with legacy selection features`

## Task 2: Recorder Emits Multi-Strategy Targets

**Files:**

- Modify: `D:\ghws\robot-automation-studio\src\robot_automation_studio\recorder.py`
- Test: `D:\ghws\robot-automation-studio\tests\test_recorder.py`

**Step 1: Write failing tests.**

- Click outside hierarchy records `target` with UIA primary + coordinate fallback.
- Drag records `input.source` and `target` selectors with coordinate fallbacks.

**Step 2: Implement recorder selector enrichment.**

- Compute window-relative `x_ratio/y_ratio` from the captured window snapshot.
- Append coordinate selector at the end of the UIA fallback chain.

**Step 3: Run verify.**

Run: `./scripts/verify.ps1`
Expected: PASS

**Step 4: Commit.**

Commit message: `feat: record coordinate fallbacks for UIA actions`

## Task 3: Exporter Supports Mixed-Strategy Fallback Chains

**Files:**

- Modify: `D:\ghws\robot-automation-studio\src\robot_automation_studio\exporter.py`
- Test: `D:\ghws\robot-automation-studio\tests\test_exporter.py` (new or existing)

**Step 1: Write failing tests.**

- A click step with `uia` + `coordinate` fallback exports Robot that tries UIA then
  coordinate.
- A drag_drop step with UIA primary and coordinate fallbacks exports Robot that
  tries UIA->coordinate fallback pair.

**Step 2: Implement exporter changes.**

- Flatten selector candidates (primary + fallbacks) preserving order.
- Add Robot user keywords:
  - `Click Unity Target With Fallbacks`
  - `Drag Unity Target With Fallbacks`
- Update click/drag generation to use these keywords when mixed strategies exist.

**Step 3: Run verify.**

Run: `./scripts/verify.ps1`
Expected: PASS

**Step 4: Commit.**

Commit message: `feat: export mixed selector fallback chains`

## Task 4: Auto Variable-First Normalization for Hierarchy Paths

**Files:**

- Create: `D:\ghws\robot-automation-studio\src\robot_automation_studio\recording_normalization.py`
- Modify: `D:\ghws\robot-automation-studio\src\robot_automation_studio\app.py`
- Test: `D:\ghws\robot-automation-studio\tests\test_recording_normalization.py`

**Step 1: Write failing tests.**

- Given recorded hierarchy paths, produces:
  - `avatar_root` variable (mode root segment)
  - per-path variables for relative suffixes
  - rewrites selectors to `${avatar_root}/${var}` form

**Step 2: Implement normalization + integrate into stop_recording.**

**Step 3: Run verify.**

Run: `./scripts/verify.ps1`
Expected: PASS

**Step 4: Commit.**

Commit message: `feat: normalize recorded hierarchy paths into variables`

## Task 5: Spec/Examples Update

**Files:**

- Modify: `D:\ghws\automation-scenario-spec\README.md`
- Create: `D:\ghws\automation-scenario-spec\examples\unity-recorded-reusable.scenario.json`

**Step 1: Update docs + add example.**

**Step 2: Commit.**

Commit message: `docs: add reusable recording example`
