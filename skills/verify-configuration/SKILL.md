---
name: verify-configuration
description: Verify a Crossplane configuration package before commit, and run, deploy, or try the project on a development control plane. Use when asked to verify, validate, or check a configuration package, "run the tests", "check if this is ready to commit", "run the project", "deploy it", "spin it up", "try it on a control plane", or for anything that would otherwise mean typing `up project run`. Builds the project, runs composition tests, reads the render for unasserted resources, and optionally runs every E2E test with a cumulated report. Use it instead of raw `up project run` because on a Space context that command pushes to a private repository the dev control plane cannot pull, then fails with an uninformative `context deadline exceeded`; this skill pre-flights the pull and asks whether to supply pull access, publish with `--public`, or run `--local`, and never silently falls back to a local KIND cluster. Does not modify code. Single live E2E runs belong to `e2e-test-configuration`.
license: Apache-2.0
references:
  - references/knowledge.md
---

# Crossplane Configuration Verification

Verify Crossplane configuration packages are ready for commit.

## Phase 0: Load the charter, and know whether you can ask

**Load the `control-plane-project-charter` skill first and read its SKILL.md.** Nothing in it
is repeated here; when this file and the charter disagree, the charter wins.

This skill runs either in the user's conversation or as a delegated agent started by another
agent. `control-plane-project-charter` §1 says what each may do. In short: in the user's
conversation you can ask; as a delegated agent you cannot reach the user, so act on the brief
you were given, discover the rest from the project, and do the work.

Either way, your summary is often all the reader gets: they may not see your exit codes,
your `render.log`, or your resource tree. That is why §4 (`control-plane-project-charter`) —
report the effect, not the intent — is binding on every summary you write, and it is not
repeated here.

**Read the whole charter before you start.** It also carries the TDD loop (§3), what a v2
composed resource needs (§5), the container boundary (§7), what a green run does and does not
prove (§8), and the rule against creating infrastructure as a side effect (§9).

## Purpose

This skill **VERIFIES** that a configuration package is ready by:
1. Building the project
2. Running composition tests
3. Reporting pass/fail status
4. Offering E2E tests (requires user confirmation)
5. Running every E2E test and writing a cumulated report (if confirmed)

**NOT in scope:** Making code changes (verification only)

## When to Use

**Use when** the user requests:
- "verify the configuration"
- "check if this is ready to commit"
- "run the tests"
- "validate the project"
- **"run the project"** / "deploy it" / "spin it up" / "try it on a control plane"
- anything that would otherwise make you type `up project run` into a shell

## Quick Reference

```bash
up project build                        # Phase 1: Build
up test run tests/test-*                # Phase 2: Composition tests
up project run --local --timeout=20m    # Phase 5: run it on a dev control plane
```

> **If the context is a Space, STOP and ask — do not silently run `--local`.** See
> *"Phase 5"* below. Being connected to a Space is usually deliberate, and quietly
> substituting a local KIND cluster changes what is being tested without telling anyone.

**Success criteria:**
- ✅ Build succeeds (exit 0, package in `_output/`)
- ✅ All composition tests pass ("Failed tests: 0")
- ⚠️ E2E tests required (ask user for confirmation)

---

## Workflow

### Phase 1: Build

Run `up project build`. If fails → report error and EXIT.

### Phase 2: Composition Tests

Run `up test run tests/test-*`. If any fail → report failures and EXIT.

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

### Phase 3: Report & Ask

**If passed:** Report success, then ask the user (as a delegated agent, put this question in
your report instead of choosing):
```
Verification passed! Would you like to run E2E tests now?
Options:
1. Yes - Run E2E tests (recommended, ~30-60 min per test)
2. No - I'll run them later
3. Skip - E2E already passed
```

**If failed:** Report failures. Do NOT ask about E2E tests.

### Phase 4: E2E Orchestration (if user confirms)

1. **Discover:** `ls -1d tests/e2etest-* | sed 's|tests/||' | sort`
2. **Execute sequentially, one test at a time, each with the `e2e-test-configuration` skill.**
   If your agent can delegate work, give each test to a delegated agent that loads
   `e2e-test-configuration` for that one test and returns PASSED with a summary or FAILED with
   its analysis, and wait for it before starting the next; otherwise run each one yourself.
3. **Collect results:** Continue even if tests fail
4. **Write report:** `e2e-test-report-YYYY-MM-DD.md`
5. **Output summary:** Brief pass/fail count with durations

See [knowledge.md](references/knowledge.md) for report templates and detailed patterns.

### Phase 5: Run it on a dev control plane (when asked to run/deploy)

Only when the user asked to run, deploy, or try the project — verification alone stops at
Phase 3. **Never run `up project run` without working through this phase.**

**1. Detect what your context points at.** The context, *not* a flag, decides which kind of
dev control plane you get. One command settles it:

```bash
up ctx . --short | awk -F/ '{print NF" segments"}'   # 4 => you are on a Space
up ctp list >/dev/null 2>&1 && echo "Space reachable"
```

> **Bare `up ctx` cannot work for an agent.** With no terminal it fails with `could not open a new TTY: open /dev/tty: device not configured` and tells you nothing about the flag that would have worked. The non-interactive forms are `up ctx .` (current context) and `up ctx . --short` (bare path, no prose). Relative navigation (`up ctx ../<name>`) also works without a TTY.

**Test the shape, not the first word.** A Space context has **four** `/`-separated segments —
`<profile-type-or-org>/<space>/<group>/<controlplane>`. The first segment is your *profile
type*: it reads `disconnected` on a disconnected Space and your **org/domain** on Upbound
Cloud. So matching the literal string `disconnected/` is a false negative on every Upbound
Cloud Space — the agent concludes "not a Space, local is the default", runs `up project run`
with no flag, gets the **cloud** path anyway, and wedges exactly as before with a different
explanation. Four segments (or `up ctp list` succeeding) means cloud path, whatever the first
segment says. Fewer segments, or `up ctx .` erroring, means local KIND is the default.

**2. Not on a Space?** Local is already the default. Just run it:

```bash
up project run --timeout=20m     # the --timeout default is 5m, short for a first run
```

**3. On a Space? Pre-flight before you spend ten minutes.** On the cloud path
`up project run` pushes to a **private** repository and then installs onto a control plane
it gives no pull credential — two halves of one invocation that do not fit together. It
wedges on `Waiting for package to be ready` and exits `context deadline exceeded`, naming
neither half. Catch it in seconds instead:

```bash
up repository get <project-name>            # PUBLIC=false and no pull secret => it will wedge
kubectl get imageconfigs.pkg.crossplane.io
kubectl -n crossplane-system get secrets | grep -i pull
```

If it *can* pull, run it on the Space — that is the environment they chose.

**4. If the pre-flight says it will wedge, hand the decision back. Do not decide it
yourself.** In particular do **not** "helpfully" fall back to `--local`: they connected to
that Space on purpose, and a local KIND cluster is a *different environment*, not a
transparent substitute. In the user's conversation, put the three options below to them
and wait. If you are running as a delegated agent you cannot ask the user — **stop and
report that the decision is needed, with these three options and their consequences**,
rather than choosing one.

| Option | Command | What it costs them |
|---|---|---|
| **A. Cloud control plane, with pull access** | `up project run --timeout=20m`, once the control plane can pull | Nothing, if the repo is pullable or they can point you at an existing pull secret / `ImageConfig`. **Ask where it is rather than assuming.** The only option that tests what they actually connected to |
| **B. Publish the repository** | `up project run --public --timeout=20m` | `--public` means *"create new repositories with public visibility"* — it **permanently publishes their package**. A disclosure decision, never made on their behalf |
| **C. Local KIND control plane** | `up project run --local --timeout=20m` | Side-loads, so the pull failure is unreachable, and it still creates real cloud resources through their provider credentials — a genuine end-to-end test. But it is *not* the Space they were pointed at, and Space-specific behaviour goes uncovered |

**5. Do not pipe the run into `tail`/`head`.** That buffers everything until the process
exits, so a run that is progressing normally looks like a hang and gets killed. Let it
stream, or `tee` it to a file.

**6. If it wedges anyway**, read *"When a run hangs on Waiting for package to be ready"*
below. Do not retry blindly — the cause is usually permanent and another attempt costs
another ~10 minutes.

**7. Confirm it actually reconciled**, rather than trusting the exit code:

```bash
kubectl get <xr-kind> -A
kubectl describe <xr-kind> <name> -n <ns>    # conditions AND events
```

A composed resource with **no conditions and no events at all** means no controller has
reconciled it yet. That is a symptom with several causes, so check it first but do not stop
there:

| Also produces silence | How to tell |
|---|---|
| `providerConfigRef` naming an object nothing created, or a missing `ClusterProviderConfig` | `kubectl get clusterproviderconfig,providerconfig -A` — is the referenced object there? |
| The provider package is not installed or not healthy | `kubectl get providers.pkg.crossplane.io` — `INSTALLED` and `HEALTHY` both `True`? |
| The provider pod is crashing or not yet running | `kubectl get pods -n crossplane-system`, then its logs |
| The MR's CRD is not established, so nothing watches the kind | `kubectl get crd <plural>.<group>` |

Only the first is peculiar to this suite's guidance, and it is the one composition tests
cannot catch — which is why it is listed first, not why it is the answer.

**8. Read the effect back from the provider, not from your own input.** `Ready=True` is
Crossplane's report that it finished reconciling; it is not proof the provider holds the
configuration you meant. Drift, silently-ignored fields, and values the provider normalised
all survive `Ready=True`. Before teardown, run the provider's own read for at least the
field the change was about, and quote it:

```bash
aws s3api get-bucket-lifecycle-configuration --bucket <name>
az <service> show -n <name> -g <rg>
gcloud <service> describe <name>
```

Reading values back off the XR, the composed resource's `spec`, or the manifest you applied
proves only that your input round-tripped. If you did not run a provider read, say
"reconciled; not independently verified at the provider" rather than "verified".

---

## When a run hangs on "Waiting for package to be ready"

`up project run` (and cloud E2E runs) can sit on `Waiting for package to be ready` and then fail
with nothing but:

```text
✗ Waiting for package to be ready
up: error: context deadline exceeded
```

That message names no control plane and no package. **Do not retry blindly** — the cause is
usually permanent, and a second run wastes another ~10 minutes. Diagnose it:

```bash
up controlplane list                 # dev CP is named up-<project>; it will usually read Available/Healthy
up ctx ../up-<project>               # relative path from a sibling CP context
kubectl get configuration.pkg.crossplane.io
kubectl describe configuration.pkg.crossplane.io <project>   # <- the real error is here
```

### Prevent it: choose the right dev control plane

`up project run` does two things in one invocation, minutes apart: it **pushes** the
package to a registry, then **installs** it onto a control plane. On a cloud dev control
plane the push creates a **private** repository and the install is given no pull
credential, so the second half fails on what the first half wrote — and the error names
neither half.

Which kind of control plane you get is decided by your current context, not by a flag:

> Cloud dev control planes are used by default when the current `up` context is an Upbound
> Cloud Space. Local dev control planes are used by default otherwise, and can be
> explicitly requested with `--local`.

**Prefer `--local` for iteration.** It runs in a KIND cluster and serves images from a
local registry path, so there is no remote push, no repository, and no visibility decision
at all — the 401 class cannot occur. It still creates real cloud resources through your
provider credentials, so it gives the same end-to-end proof:

```bash
up project run --local --timeout=20m
```

The default `--timeout` is `5m`, which is short for a first run that has to pull providers.

**If you are on a Space and hit the 401**, switch to `--local` rather than working around
the credential. Do **not** reach for `--public` as a workaround: it means *"create new
repositories with public visibility"* — it permanently publishes the user's package to a
public repository. That is the user's decision to make, not a debugging step. Use it only
when they have explicitly asked for a public repository.

Retrofitting visibility afterwards is its own trap: `up repository update <name>` requires
an unrelated `--publish` flag, rejects the value `up repository get` prints for it, and has
no `--yes`, so it needs a TTY.

Note `up ctx default/up-<project>` is rejected with *"not available in the current profile"*; the
relative form (`up ctx ../up-<project>`) is what works from a sibling control-plane context.

**Check you are looking at the right cluster first.** A failed `up project run` may leave
kubeconfig pointed at a *different* control plane than the one it created, so `kubectl
describe` will happily describe a healthy unrelated package and send you chasing a
non-existent problem. Confirm with `up ctx .` before believing anything you read.

The control plane being `Available`/`Healthy` says nothing about the package. Read the
Configuration's conditions and events. Causes seen in practice:

| `describe` shows | Cause | Fix |
|---|---|---|
| `cannot unpack package: ... 401 Unauthorized ... UNAUTHORIZED: authentication required` | the control plane can't **pull** the package `up project run` just **pushed** — it pushes to a **private** repository by default and gives the control plane it created no pull credential (common on `disconnected` Spaces; check `up profile list`) | Re-run with **`--local`** (KIND + local registry, so nothing is pushed and the failure class cannot occur). Do *not* use `--public` to work around it — that permanently publishes the package. See below |
| `cannot resolve ... not found` | pushed to a different repo than the CP is installing | reconcile `spec.repository` with the installed package reference |
| provider revision unhealthy | provider still installing, or a bad version constraint | check `kubectl get provider.pkg.crossplane.io` and its revisions |

Report the underlying condition message to the user — not "the run timed out".

## Critical Requirements

1. **Sequential execution:** Build MUST succeed before tests
2. **Exit on failure:** Stop if build or composition tests fail
3. **User confirmation:** ALWAYS ask before E2E tests; as a delegated agent, report the
   question rather than starting them
4. **Sequential E2E:** run one test at a time, each through `e2e-test-configuration`
5. **Continue on E2E failure:** Run all E2E tests even if some fail
6. **Concise reporting:** Summary only, not full logs

---

## Skill Boundaries

**This skill:**
- ✅ Builds project
- ✅ Runs composition tests (local)
- ✅ Runs every E2E test through `e2e-test-configuration` and cumulates the results
- ✅ Reports pass/fail status

**Other skills:**
- ❌ Does NOT modify code
- ❌ Does NOT fix errors → use authoring skills
- ❌ Does NOT create tests → use `author-tests`
- ❌ Does NOT run a single E2E test itself → that is `e2e-test-configuration`

---

## Typical Durations

| Phase | Duration |
|-------|----------|
| Build | 2-5 min |
| Composition tests | 5-15 min |
| E2E tests | 30-60 min per test |

---

## Reference

See [knowledge.md](references/knowledge.md) for:
- Detailed phase instructions
- Report templates (success/failure)
- E2E orchestration patterns
- Composition rendering (optional)
- Project structure reference
- Command reference
