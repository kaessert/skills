# Verification report templates

Read when writing the verification report (Phase 3) or the cumulated E2E report (Phase 4).
Report what ran and what it printed, with no checkmarks (`control-plane-project-charter` §4:
report the effect, not the intent).

## Verification passed

```markdown
## Verification: build and composition tests passed

**Build:** `up project build` → exit 0; package [path in _output/]
**Composition tests:** `up test run "tests/test-*"` → exit 0; [the summary line it printed]
**Render:** [every new or changed resource asserted | gaps: resources rendered but not asserted]
**Layer reached:** composition test (render). Not deployed; provider validity unchecked.
**Not run:** E2E tests [required before commit | ruled out by the project]
```

## Verification failed

```markdown
## Verification: FAILED at [build | composition tests]

**Build:** `up project build` → exit [code]
**Composition tests:** `up test run "tests/test-*"` → exit [code]; [X] failed [or: not run, build failed]

### Failed tests
[Each failing test name, with its failure message quoted]

### Next steps
Cannot commit. Fix the failures and re-run the verification; E2E waits until the composition
tests pass.
```

## Cumulated E2E report

Write to `e2e-test-report-YYYY-MM-DD.md`. Durations come from each run's own log (the
`e2e-test-configuration` report), never from file timestamps or estimates.

```markdown
# E2E Test Report - YYYY-MM-DD

**Target:** [local kind | Space <space>/<group>]
**Total:** X | **Passed:** Y | **Failed:** Z | **Not run:** N

| Test | Status | Duration |
|------|--------|----------|
| e2etest-... | PASSED | 412 s |
| e2etest-... | FAILED | 1310 s |
| e2etest-... | not run (shared cause, see above) | - |

## e2etest-... (PASSED)
[the sub-agent's summary]

## e2etest-... (FAILED)
[the sub-agent's failure analysis]
```

## Summary in your reply

```markdown
## E2E tests: Y/X passed

**Target:** [target]  **Report:** e2e-test-report-YYYY-MM-DD.md
- e2etest-1: PASSED (412 s)
- e2etest-2: FAILED (1310 s) - [one-line cause]
- e2etest-3: not run - [why]
```
