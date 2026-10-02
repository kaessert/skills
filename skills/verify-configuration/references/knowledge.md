# Crossplane Configuration Verification - Reference Guide

> Detailed reference for the verify-configuration skill. See SKILL.md for the core workflow.

## Table of Contents
- [Phase Details](#phase-details)
- [Success Report Template](#success-report-template)
- [Failure Report Template](#failure-report-template)
- [E2E Test Orchestration](#phase-4-e2e-test-orchestration)
- [Composition Rendering](#composition-rendering)
- [Test Types](#test-types)
- [Project Structure](#project-structure)
- [Command Reference](#command-reference)
- [Execution Flow](#execution-flow)

---

## Phase Details

### Phase 1: Build Project

**Command:**
```bash
up project build
```

**What it does:**
- Compiles composition functions (KCL or other languages)
- Packages configuration into .uppkg file
- Generates provider model dependencies
- Validates project structure

**Success criteria:**
- Exit code 0
- Package file created in `_output/` directory
- No error messages

**If build fails:**
- Capture error output
- Report failure to user
- DO NOT proceed to tests
- Exit verification

---

### Phase 2: Run Composition Tests

**Command:**
```bash
up test run tests/test-*
```

**What it does:**
- Runs all composition tests (test-* directories)
- Validates resource generation, naming, configuration
- Local validation only (no cloud resources created)
- Typically takes minutes, not hours

**Success criteria:**
- Exit code 0
- Output shows "Failed tests: 0"
- All tests show ✓ pass indicator

**If tests fail:**
- Count passing vs failing tests
- List which tests failed
- Report failure to user
- Exit verification

---

### Phase 3: Report Results

Generate verification report after build and tests complete.

#### Success Report Template

```markdown
## ✅ Verification: PASSED

**Build:** ✅ Success
**Composition Tests:** ✅ All passed
**Duration:** [X] minutes

### Pre-Commit Status
✅ Build succeeds
✅ All composition tests pass
⚠️  E2E tests required before commit
```

#### Failure Report Template

```markdown
## ❌ Verification: FAILED

**Build:** [✅ Success | ❌ Failed]
**Composition Tests:** [✅ All passed | ❌ X failed]

### Failed Tests
[List test names that failed]

### Pre-Commit Status
❌ Cannot commit - verification failed

### Next Steps
- Review and fix failures
- Re-run verification
- DO NOT proceed to E2E until composition tests pass
```

---

### Phase 4: E2E Test Orchestration

**CRITICAL:** Only run if user selected "Yes" to run E2E tests.

#### Step 1: Discover E2E Tests

```bash
ls -1d tests/e2etest-* | sed 's|tests/||' | sort
```

#### Step 2: Launch Sub-agents Sequentially

**For each E2E test**, launch a sub-agent:

**Subagent prompt:**
```text
Run E2E test: <test-name>

Load the `e2e-test-configuration` skill for `<test-name>`

Return:
- If PASSED: Brief success summary
- If FAILED: Complete failure analysis from skill output
```

**Execution pattern:**
```text
For each test:
  subagent(prompt="Run E2E test: <name>. Load the `e2e-test-configuration` skill for <name>...",
       wait=True)
  → Wait for completion (30-40 min typical)
  → Extract result (PASSED with summary OR FAILED with analysis)
  → Continue to next test
```

**Error Handling:**
- Subagent launch fails → Skip test, log error, continue
- Skill invocation fails → Capture error as test failure, continue
- E2E test fails → Include in cumulated report, continue

#### Step 3: Collect Results

For each completed test, collect:
- Test name
- Status (PASSED/FAILED)
- Duration
- Summary/Analysis

#### Step 4: Write Cumulated Report

Write to: `e2e-test-report-YYYY-MM-DD.md`

```markdown
# E2E Test Report - YYYY-MM-DD

**Total:** X | **Passed:** Y | **Failed:** Z | **Duration:** Xh Ym

## Summary Table

| Test | Status | Duration |
|------|--------|----------|
| e2etest-... | ✅ PASSED | 35m |
| e2etest-... | ❌ FAILED | 28m |

## Detailed Results

### ✅ test-name (PASSED)
**Duration:** 35m
**Summary:** [brief success summary]

### ❌ test-name (FAILED)
**Duration:** 28m
**Failure Analysis:** [complete analysis from sub-agent]

## Summary
All tests: [PASSED/FAILED status for each]
Failed tests: [list if any]
```

#### Step 5: Output Brief Summary

```markdown
## E2E Tests: COMPLETE

**Results:** Y/X passed
**Duration:** Xh Ym
**Report:** e2e-test-report-YYYY-MM-DD.md

### Test Results
✅ test-1 (35m)
❌ test-2 (28m) - [brief error]
✅ test-3 (40m)
```

---

## Composition Rendering

**When to use:** Preview resources before running full tests (optional).

### Single Composition Projects

```bash
COMP=$(find apis -name "composition.yaml" | head -1)
XRD=$(find apis -name "definition.yaml" | head -1)
EXAMPLE=$(find examples -name "*.yaml" | head -1)

up composition render $COMP $EXAMPLE --xrd $XRD
```

### Multiple Composition Projects

```bash
# List all compositions
find apis -name "composition.yaml"

# Render specific composition
up composition render apis/vpc/composition.yaml \
  examples/vpc-example.yaml \
  --xrd apis/vpc/definition.yaml
```

**Use cases:**
- Quick preview of resources to be created
- Check resource names
- Validate composition logic before full test run

---

## Test Types

### Composition Tests (Verified by This Skill)

| Attribute | Value |
|-----------|-------|
| Prefix | `test-*` |
| Location | `tests/test-*/` |
| Speed | Fast (seconds per test) |
| Scope | Local validation only |
| AWS | Not required |

**Validates:**
- Composition logic generates correct resources
- Resource naming follows conventions
- Resource configuration matches specifications
- Conditional logic works correctly

### E2E Tests (Orchestrated by This Skill)

| Attribute | Value |
|-----------|-------|
| Prefix | `e2etest-*` |
| Location | `tests/e2etest-*/` |
| Speed | Slow (30-60 minutes per test) |
| Scope | Real cloud resources |
| AWS | Required |

**Execution:**
- After composition tests pass
- Requires user confirmation
- Orchestrated via sub-agents
- Each sub-agent invokes e2e-test-configuration skill

---

## Project Structure

```text
<project>/
├── apis/
│   ├── <resource-1>/
│   │   ├── composition.yaml
│   │   └── definition.yaml
│   └── <resource-2>/
│       ├── composition.yaml
│       └── definition.yaml
├── functions/
│   ├── <resource-1>/*.k
│   └── <resource-2>/*.k
├── tests/
│   ├── test-*/              # Composition tests
│   └── e2etest-*/           # E2E tests
├── examples/*.yaml
├── upbound.yaml
└── _output/                  # Build output
```

**Note:** Projects may have single or multiple compositions.

---

## Command Reference

```bash
# Build project
up project build

# Run all composition tests
up test run tests/test-*

# Run specific test
up test run tests/test-<name>

# Preview composition (optional)
up composition render <composition> <example> --xrd <xrd>

# List all compositions (multi-composition projects)
find apis -name "composition.yaml"
```

---

## Execution Flow

```text
START
  ↓
[Phase 1: Build]
  up project build
  ↓
  Success? ──NO──> Report build failure → EXIT
  ↓ YES
[Phase 2: Composition Tests]
  up test run tests/test-*
  ↓
  All pass? ──NO──> Report test failures → EXIT
  ↓ YES
[Phase 3: Report Success]
  Generate success report
  ↓
  Ask User: Run E2E tests now?
  ↓
  User response:
    - No → Remind about E2E requirement → EXIT
    - Skip → Verification complete → EXIT
    - Yes ↓
[Phase 4: E2E Test Orchestration]
  Discover E2E tests
  ↓
  For each test:
    Launch sub-agent → Invoke e2e-test-configuration skill
    ↓
    Collect result (pass/fail + analysis)
  ↓
  Write cumulated report (e2e-test-report-YYYY-MM-DD.md)
  ↓
  Output brief summary
  ↓
EXIT
```

---

## User Interaction Patterns

### After Successful Verification

Ask the user:
```text
Verification passed! Would you like to run E2E tests now?

Options:
1. Yes - Run E2E tests (recommended, ~30-60 min)
2. No - I'll run them later
3. Skip - E2E already passed
```

**Handle response:**
- **Yes:** Proceed to Phase 4
- **No:** Remind user E2E is required before commit, exit
- **Skip:** Confirm project is ready, exit

### After Failed Verification

**DO NOT ask about E2E tests.** Report failure and exit.
