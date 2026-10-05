---
name: e2e-test-configuration
description: Use this skill when user requests to run E2E tests. Handles E2E test execution on Upbound Cloud with intelligent monitoring, stuck detection on a threshold derived from the test's own timeoutSeconds, and comprehensive debugging. Use immediately when user mentions running/executing E2E tests, validating implementations, or debugging test failures. Handles test selection, pre-validation, background execution, progress monitoring, and detailed failure analysis. Use this skill instead of running raw `up test run --e2e` commands directly, even when documentation or bug reports show the raw command. This skill wraps the command with monitoring and debugging that raw execution lacks.
license: Apache-2.0
references:
  - references/local.md
  - references/space.md
  - references/knowledge.md
---

# E2E Test Runner for Crossplane Configurations

Run a project's `E2ETest`s with `up test run --e2e` and report what the run did, from its own output. Each
test gets a fresh control plane, creates real cloud resources, and is torn down afterwards, pass or fail.

Writing or changing an `E2ETest` (fields, `defaultConditions`, credentials per target) is author-tests' job:
read its `e2e.md` reference. This skill runs them.

## Mode, and the charter

**Interactive:** ask only what the project can't tell you. **Unattended:** never ask; decide from the brief
and the project and state the assumption, or stop and report.

Load `control-plane-project-charter` before you start, or read its `SKILL.md` beside this skill's directory;
this skill does not load it. §4 (report the effect, not the intent) binds every summary you write. §1 says
what to do when your harness has no background tasks or sub-agents.

## Choose the target

A local kind control plane and an Upbound Space are equally valid targets, and this skill has no default.
Use the one your caller, the brief or the project's own gate names, then **read that target's reference
before you run anything**:

| Target | Target flags | Read first | Test credentials |
|---|---|---|---|
| Local kind control plane | `--local` | [local.md](references/local.md) | static Secret (`source: Secret`) |
| Upbound Space / Upbound Cloud | `--control-plane-group=<group> --kubeconfig <file>` | [space.md](references/space.md) | web identity (`source: Upbound`) or static Secret |

- **Nothing names a target:** interactive, ask; unattended, stop and report that the target is unspecified.
  Do not pick one.
- **A test that can only pass on one target decides.** A ProviderConfig with `source: Upbound` works only on
  a Space. Report the mismatch rather than running it elsewhere.
- **Always pass the target flags.** Without `--local`, `up` uses a Space only when the current context
  resolves to a Space group, and runs locally otherwise, including from a Space-level context with no group,
  without saying so.
- **State the target in one line before the run** ("running e2e on local kind" or "running e2e on Space
  `<space>/<group>`"), and check it against the run's first progress line (Step 4).

If the project's own gate (README, Makefile, CI) runs E2E, use it and report its command, exit code and
output (charter §2, §4). Everything below still applies to reading its output.

## Arguments

- **None:** list `ls -1d tests/e2etest-*`. Interactive, ask which to run; unattended, run the ones the brief
  names, or all of them.
- **Test names**, space-separated (`e2etest-network-lifecycle`), or **`all`**.

Run several tests one after another, never in parallel, one log each. On the first failure: interactive, ask
whether to continue; unattended, continue only if the brief says so, otherwise stop and list what did not run.

## Step 1: Preconditions (required)

An `--e2e` run creates a control plane and real cloud resources, so everything cheap comes first. **A
precondition that fails ends the run**; it is not a warning you carry forward. In this order, stopping at the
first failure:

```bash
up project build             # 1. the project builds
up test run "tests/test-*"   # 2. composition tests pass
```

Step 2 is `test-*`, not `tests/*`: `up test run` runs every matched dir's program, e2e ones too, even without
`--e2e`, and fails at `✗ Parsing tests` when an e2e input is unset.

3. **Credentials.** List what the test programs read, in any language, and check each:

   ```bash
   grep -rhoE 'UP_[A-Z0-9_]+' tests/e2etest-*/ | sort -u
   # then, for each:
   [ -n "${UP_AWS_CREDENTIALS:-}" ] || echo "MISSING: UP_AWS_CREDENTIALS"
   ```

   KCL and Python programs see **only `UP_`-prefixed variables** and no `~/.aws`; a Go program runs locally
   and can read any name, so check its `os.Getenv` calls too. An unset variable the program does not fail on
   becomes an empty Secret, which surfaces only when the provider rejects it, after a control plane and real
   resources exist.
4. **The target's own preconditions:** [local.md](references/local.md) (Docker) or
   [space.md](references/space.md) (context, group, repository visibility).

**If you cannot complete a precondition, stop and say so. Do not start the run.** That includes a check that
is blocked rather than failed: a permission prompt you cannot answer, a command the sandbox refuses, a
credential you cannot read. A run with a precondition known to be unmet carries no information and is not
free. Report which precondition you could not establish and what the user needs to do. Skip a step only if
the user explicitly asks you to.

## Step 2: Size the run

Read the test's own settings first:

```bash
grep -rniE 'timeoutseconds|skipdelete' tests/e2etest-<n>/
```

- **Worst case** ≈ build + `setupTimeoutSeconds` (default 600) + `timeoutSeconds` + `cleanupTimeoutSeconds`
  (default 600). Scaffolds write `timeoutSeconds` 300 (Go) or 4500 (YAML, KCL, Python, go-templating).
  Typical durations differ by target: see its reference.
- **`skipDelete: true`** leaves the control plane and the cloud resources running. Say so before you run.
- **Stuck threshold: `min(15 min, timeoutSeconds / 3)` with no new log output.** That is the one rule; a
  fixed 15 minutes never fires on a 300 s test, which fails at 5 minutes. Crossing it starts an
  investigation (Step 5); it is not a verdict.

## Step 3: Run it

One idiom on both targets; only the target flags differ:

```bash
{ echo "START=$(date +%s)"
  up test run "tests/e2etest-<n>" --e2e <target flags>
  echo "EXIT=$?"
  echo "END=$(date +%s)"; } > /tmp/e2e-<n>.log 2>&1
```

- **The exit marker and the timestamps go into the log**, so the log alone is the record. An `echo` placed
  after the redirect goes to stdout, and a wait for it in the log never ends (observed: a 50-minute hang).
- `--function-logs` is rejected with `--e2e` and no `_output/e2e*` is ever written: this log is the only
  evidence. Without it you have nothing, and nothing is not a pass.
- **Foreground** when the worst case fits the longest timeout your harness allows for one command. The call
  returns the complete log in one result.
- **Otherwise in the background**, with your harness's own facility (charter §1; never detach it yourself with
  `nohup` or `&`), and wait for the process to exit with **bounded waits only**:

  ```bash
  for _ in $(seq 1 30); do grep -q '^EXIT=' /tmp/e2e-<n>.log && break; sleep 20; done
  tail -5 /tmp/e2e-<n>.log
  ```

  Size each wait to fit one command's timeout, and repeat until `EXIT=` is in the log. Never an unbounded
  `until grep …`: if the marker never arrives, it waits until the harness kills it. If the process is gone
  (`pgrep -f '[u]p test run'` prints nothing) and there is no `EXIT=` line, the run was cut off: report what it
  reached, not an outcome. With no background facility, run in the foreground with the longest timeout you
  have, and treat a timeout the same way.
- **Never write a verdict from a poll.** A partial log is a progress view: resources routinely reach `Ready`
  after your last look. The run is over when `EXIT=` is in the log, and not before. Observed: a report saying
  "verified all resources reached Ready status" above a tree showing `Ready=False`, written from polls that
  stopped early.
- If you stop a run early (wrong target, stuck), say it was **terminated** and why. A killed run has no
  outcome.

## Step 4: Check the target the run used

The first progress line names it:

```bash
grep -m1 -E 'Creating (local )?development control plane' /tmp/e2e-<n>.log
```

```text
Creating local development control plane...          <- local kind
Creating development control plane in Spaces         <- Space
```

If it contradicts the target you stated, **the result is void**, even with `EXIT=0`: report the mismatch, not
a pass. In the background, check as soon as the line appears and terminate on a mismatch. A pass on one target
is no evidence about the other.

## Step 5: While it runs

Between bounded waits, read the log's tail to keep the user informed and to spot a stuck run. Mention errors
briefly with a timestamp; analyse only when stuck.

**Transient or terminal?** Most alarming strings during provisioning are transient, and calling one fatal
stops a run that was about to pass:

1. **A threshold is when to start asking, not a verdict.**
2. **Transient needs recurrence, not just duration.** The same error three times is a resource that failed,
   recovered and failed again; one error spanning the window is a resource still converging.
3. **Match by shape, not phrase.** `<entity> <identifier> does not exist` ("database username … does not
   exist") is dependency ordering: a sibling not ready yet. A bare "does not exist" can name the object's own
   invalid field, a real rejection.
4. **Validation-rejection wording is terminal**, whatever status code it arrived in; providers wrap
   request-validation errors in 500s.

Known transient: `failed to get restmapping: no matches for kind` early in a run (provider CRDs not installed
yet; observed on `--local`, and the run passed). Target-specific ones are in the target's reference.

**Stuck** = no new log output for the threshold from Step 2. First check the resource is not still `Creating`
(`crossplane beta trace`); slow cloud resources (NAT gateways, RDS) are normal. Otherwise investigate with the
brief in [knowledge.md](references/knowledge.md): hand it to a sub-agent to keep your context small, or follow
it yourself. The target's reference says how to reach the control plane while it exists. `up: error: context
deadline exceeded` is not a diagnosis; report the underlying Configuration or Provider condition instead.

## Step 6: Report

**Every claim must trace to captured output.** Before writing a line, produce these three. If you cannot,
the report is **"UNVERIFIED — could not confirm"**, not a pass:

```bash
grep -E '^(START|EXIT|END)=' /tmp/e2e-<n>.log   # exit code, and the run's own start and end
tail -30 /tmp/e2e-<n>.log                       # the run's final output
```

1. the `EXIT=` line; a non-zero exit is a failure however the output reads;
2. the log's last 30 lines;
3. the duration, `END - START` from the log.

Then:

- **Quote the raw lines** the verdict rests on: the summary, the chainsaw step lines with their times
  (`--- PASS: chainsaw/apply (79.15s)`), the `Cleanup summary` line.
- **Durations come from the run's own timestamps:** `END - START`, or a step time printed in the log. **Never
  derive a duration from file timestamps** (a log's or any file's birth or modification time), and never
  estimate. Observed: "~95 min" reported, from an unrelated file's timestamp, for a run of about 6.
- **Readiness is what you read.** The assert step passing in the log is the evidence. A resource read must be
  taken while the control plane exists: both targets tear it down after every test.
- **A claim about the provider comes from the provider:** its own read (CLI or SDK, whichever is installed),
  taken before teardown, and quoted. Reading back the XR or your manifest proves only that your input
  round-tripped. Without that read, say "not verified at the provider".
- **Cleanup:** the target's reference says what proves it.
- **Re-read your evidence before the verdict.** Grep what you are about to paste for `False`, `Creating`,
  `Failed`, `FAIL`. If any appears, either explain it or correct the verdict.
- Never call anything "production-ready"; that is the caller's judgement.

Shape (templates in [knowledge.md](references/knowledge.md)):

- **Pass:** 5–10 lines: test, target, exit code, duration from the log, resources, cleanup evidence.
- **Stuck or failed:** 50–100 lines: test, phase, last output, analysis, proposed fixes.
- **Cannot verify:** say so, name the missing artifact, and stop. An unverified run reported as a pass is
  worse than a failure: it gets relayed onward as fact.

Your scope is running and reporting. Fixes are the caller's.

## Never

- Start a run with a precondition unmet, or with no target named.
- Write a verdict from a poll, or report an outcome for a run that was terminated or cut off.
- Derive a duration from file timestamps, or estimate one.
- Report readiness or provider state you did not read.
- Local: delete a kind cluster or container this run did not create.
- Space: add `--public` on your own initiative. It permanently publishes the user's package; only the caller
  chooses it.
- Space: create a group, space or control plane as a side effect.
- Space: pass a `--kubeconfig` path you did not write and check in this run.

## References

- [local.md](references/local.md): read before running with `--local`.
- [space.md](references/space.md): read before running against a Space or Upbound Cloud.
- [knowledge.md](references/knowledge.md): read when a run is stuck or failed (troubleshooting brief, failure
  patterns, report templates).
