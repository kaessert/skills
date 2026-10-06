# E2E report templates

Read when writing the report (SKILL.md Phase 6). Every line traces to the run's log or a read taken during the
run.

## Pass

```markdown
## E2E test: PASSED

**Test:** <test-name>  **Target:** <local kind | Space <space>/<group>>
**Exit code:** 0 (`EXIT=0`)  **Duration:** <END - START> s, from the log
**Control plane:** <project>-uptest-<test>

### Evidence
- <quoted assert line, e.g. `--- PASS: chainsaw/apply (79.15s)`>
- <quoted `Cleanup summary: N deleted, 0 remaining`>
- Provider state: <quoted read taken during the run | not verified at the provider>
- Leftovers: <how checked, result | not checked, and why>
```

## Stuck or failed

```markdown
## E2E test: <FAILED | STUCK (terminated)>

**Test:** <test-name>  **Target:** <target>
**Exit code:** <N | none: terminated after <s> s>  **Phase:** <phase>
**No progress for:** <s> s (threshold <s> s, from timeoutSeconds <N>)

### Last output
<quoted last lines>

### Analysis
<sub-agent output>

### References
- Test directory: `tests/<test>/`
- Related file: `<file>`
```

## Several tests

```text
[1/3] e2etest-basic       PASSED  (EXIT=0, 412 s)
[2/3] e2etest-secondary   FAILED  (EXIT=1, 1310 s)
[3/3] e2etest-peering     not run (stopped: shared cause in [2/3])
```
