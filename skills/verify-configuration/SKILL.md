---
name: verify-configuration
description: Verify a Crossplane configuration package before committing - build it, run its composition tests and read the render, and optionally orchestrate its E2E tests or run the project on a development control plane ("verify the configuration", "validate the project", "is this ready to commit", "run the tests", "run the project", "deploy it", "spin it up", "try it on a control plane", "up project run", "dev control plane"). Use it instead of running raw `up project run` - on a Space context that run pushes to a private repository the control plane cannot pull, hangs on `Waiting for package to be ready` and dies with `context deadline exceeded`; this skill checks for that first and hands the choice of target back rather than falling back to `--local`. Not for writing tests (author-tests) or running a single E2E test (e2e-test-configuration).
license: Apache-2.0
references:
  - references/knowledge.md
  - references/dev-control-plane.md
---

# Crossplane Configuration Verification

Verify that a configuration package is ready for commit: build it, run the composition tests,
report what ran, and on request orchestrate E2E tests or run the project on a dev control
plane. This skill changes no code.

## Mode, and the charter

**Interactive:** ask only what the project can't tell you. **Unattended:** never ask; decide from
the spec and state the assumption, or stop and report. Started as a separate agent, you are
unattended, and prose is your only output channel: `control-plane-project-charter` §4 (report
the effect, not the intent) binds every summary. Load the charter before you start, or read its
`SKILL.md` beside this skill's directory: this skill does not load it.

## Local-only projects and projects with their own gate

- **The project has its own gate** — a script or make target that builds and runs the
  tests. Run it instead of the steps it covers, and report its command, exit code and output
  (`control-plane-project-charter` §4: report the effect, not the intent). The project's
  decision wins over this skill's steps (§2: the project's own decisions win).
- **Upbound Cloud is ruled out** — by the project or the user. Use `--local` throughout and
  skip the Space-context checks and the push-target decision. A local run that fits in your
  shell's timeout runs in the foreground, with no monitoring loop.

## Quick Reference

```bash
up project build                        # Phase 1: Build
up test run "tests/test-*"              # Phase 2: Composition tests
up project run --local --timeout=20m    # Phase 5: run it on a dev control plane
```

> **If the context is a Space, STOP and ask — do not silently run `--local`.** See
> *"Phase 5"* below. Being connected to a Space is usually deliberate, and quietly
> substituting a local KIND cluster changes what is being tested without telling anyone.

**Success criteria** (checks for you, not a report format — report what ran, charter §4):
- Build succeeds (exit 0, package in `_output/`)
- All composition tests pass ("Failed tests: 0"), and the run did not print `No test files found`
- E2E tests offered (ask user for confirmation), unless the project rules them out

---

## Workflow

### Phase 1: Build

Run `up project build`. If fails → report error and EXIT.

### Phase 2: Composition Tests

Run `up test run "tests/test-*"`. If any fail → report failures and EXIT. If it prints
`No test files found`, no test ran, though it exits 0 — report that, never a pass
(`control-plane-project-charter` §8).

Keep the `test-*` glob: `up test run` runs the program of every dir it matches, e2e ones
too even without `--e2e`, so `tests/*` fails at `✗ Parsing tests` whenever an e2e input is
unset. `no valid CompositionTests found` means the matched dirs produced no
`CompositionTest` (e.g. only `e2etest-*` dirs): a wrong glob, not a failing test
(`control-plane-project-charter` §7).

### Phase 2b: Read the render, don't just trust the exit code

`up test run` reports PASS for the resources a test *asserts*. It does not notice resources the
composition emits but the test never lists — verified: adding a whole extra managed resource to a
function left a 2-test suite at 2/2 PASS with the assertions untouched. **A green suite is not
evidence that new work is covered.**

So when verifying a change that added or modified a composed resource, re-run with logs and read
the render:

```bash
up test run "tests/test-*" --function-logs
# -> Test artifacts written to _output/composition_test/<timestamp>
```

| File | Use it for |
|---|---|
| `_output/composition_test/<ts>/<test>/render.log` | the rendered XR plus **every** composed resource as applied — the ground truth of what the function emits |
| `_output/composition_test/<ts>/<test>/<function>.log` | that function's container logs: Python tracebacks, `self.log` output |

Check that (a) every resource the change should produce appears in `render.log`, and (b) each one
is named in the test's `assertResources`. If a resource is in the render but not in the
assertions, the verification is incomplete — report it as a gap rather than a pass.

Two things composition tests structurally cannot cover, so don't report them as verified:
- **Readiness branches** — tests render with only the observed resources you supply, so code gated on live `observed`/`is_ready` state never executes.
- **`providerConfigRef` correctness** — a reference to a ProviderConfig that doesn't exist renders and asserts cleanly, then leaves the resource with no status conditions at all on a real control plane.

### Phase 3: Report, then offer E2E

**If failed:** report the failures and stop. Do not offer E2E tests.

**If passed:** report what ran. **Interactive:** ask whether to run the E2E tests now (~30-60
min per test), later, or not at all because they already passed. **Unattended:** run them only
if your brief asks for E2E; otherwise say they were not run.

### Phase 4: E2E Orchestration (if user confirms)

1. **Discover:** `ls -1d tests/e2etest-* | sed 's|tests/||' | sort`
2. **Execute sequentially:** For each test, hand this brief to a sub-agent and wait for its
   result. Do not load `e2e-test-configuration` into your own context while you can start a
   sub-agent; only if your harness has none, follow the brief yourself
   (`control-plane-project-charter` §1: delegate with whatever your harness supports):
   ```text
   Run E2E test: <name>. Load the `e2e-test-configuration` skill for <name>. Return PASSED with summary or FAILED with analysis.
   ```
3. **Collect results:** Continue even if tests fail
4. **Write report:** `e2e-test-report-YYYY-MM-DD.md`
5. **Output summary:** Brief pass/fail count with durations

Report templates and the orchestration detail: [knowledge.md](references/knowledge.md).

### Phase 5: Run it on a dev control plane (when asked to run/deploy)

Only when the user asked to run, deploy, or try the project — verification alone stops at
Phase 3. **Read [dev-control-plane.md](references/dev-control-plane.md) before any
`up project run`**, and work through its steps: which control plane the context gives you
(it decides, not a flag), the Space pre-flight, the choice you hand back when a Space cannot
pull, confirming the run reconciled, reading the effect back from the provider, and what to do
when the run hangs on `Waiting for package to be ready`.

**Wait for the run inside your turn.** `up project run` takes several minutes. Run it in the
background only if your harness tells you when it exits, and then wait for that; otherwise run
it in the foreground (`control-plane-project-charter` §1: never detach a run yourself).
Never end your turn with the run still in flight: in many agents the jobs a session started die with it, leaving a half-created
KIND cluster and no result. Observed in a headless session: the run was killed at
"Building functions..." and the cluster `up-<project>` had to be deleted by hand.

**Tear down with `up project stop`** from the project root. If you delete the KIND cluster
directly instead, also remove its registry container: `kind delete cluster --name up-<project>`
leaves `up-<project>-registry` running (`docker rm -f up-<project>-registry`).

**Never:**
- Run `up project run` without working through the reference's steps.
- On a Space the control plane cannot pull from, pick the target yourself: no silent
  `--local`, and never `--public` on your own initiative — it permanently publishes the
  user's package. Put the three options to the user, or report them to your caller and stop.
- Pipe the run into `tail`/`head`: it buffers until exit, so a healthy run looks hung.
- Retry a hang blindly, or report "the run timed out": the cause is usually permanent, and the
  real error is in the Configuration's conditions.
- Report "verified" from `Ready=True` or from your own manifest. Without a provider read, say
  "reconciled; not independently verified at the provider".

## Critical Requirements

1. **Sequential execution:** Build MUST succeed before tests
2. **Exit on failure:** Stop if build or composition tests fail
3. **User confirmation:** ALWAYS ask before E2E tests (unattended: only what the brief asks for, see Mode)
4. **Sequential E2E:** Run one test at a time via sub-agents
5. **Continue on E2E failure:** Run all E2E tests even if some fail
6. **Concise reporting:** Summary only, not full logs

Typical durations: build 2-5 min, composition tests 5-15 min, E2E tests 30-60 min per test.

This skill does not modify code or fix errors (use the authoring skills), create tests (use
`author-tests`), or run E2E itself (it delegates to `e2e-test-configuration`).

## References

- [dev-control-plane.md](references/dev-control-plane.md) — read before any `up project run`,
  and when a run hangs on `Waiting for package to be ready`.
- [knowledge.md](references/knowledge.md) — read for the report templates, the E2E
  orchestration detail, composition rendering, and the command reference.
