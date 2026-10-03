---
name: e2e-test-configuration
description: Use this skill when user requests to run E2E tests. Handles E2E test execution on Upbound Cloud with intelligent monitoring, stuck detection on a threshold derived from the test's own timeoutSeconds, and comprehensive debugging. Use immediately when user mentions running/executing E2E tests, validating implementations, or debugging test failures. Handles test selection, pre-validation, background execution, progress monitoring, and detailed failure analysis. Use this skill instead of running raw `up test run --e2e` commands directly, even when documentation or bug reports show the raw command. This skill wraps the command with monitoring and debugging that raw execution lacks.
license: Apache-2.0
references:
  - references/knowledge.md
---

# E2E Test Runner for Crossplane Configurations

Run end-to-end tests with active monitoring, stuck detection (15 min threshold), and comprehensive debugging.

See [knowledge.md](references/knowledge.md) for detailed commands and troubleshooting prompts.

## Phase 0: Know how you were started, and you are bound by the charter

This skill is written for a separate agent (a forked sub-agent) — one that does not see the
caller's conversation, and for which **asking a question ends the turn**. If you were handed
a brief as a separate agent, that is you: act on the brief you were given, discover the rest
from the project, and do the work. If you were loaded into the user's conversation instead —
your harness has no sub-agents, or the user invoked you directly — you are inline and may ask
when a decision is genuinely undetermined. `control-plane-project-charter` §1 says what each
means.

As a separate agent, your only output channel is prose: the caller cannot see your exit codes, your `render.log`,
or your resource tree. That is why §4 (`control-plane-project-charter`) — report the
effect, not the intent — is binding on every summary you write, and it is not repeated here.

**Read the whole charter before you start.** It also carries the TDD loop (§3), what a v2
composed resource needs (§5), the container boundary (§7), what a green run does and does not
prove (§8), and the rule against creating infrastructure as a side effect (§9).

## Local-only projects and projects with their own gate

- **The project's own gate runs E2E** — use it, and report its command, exit code and output
  (`control-plane-project-charter` §4, §2).
- **Upbound Cloud is ruled out** — use `--local`, skip the Space-context checks and the
  push-target decision, and run in the foreground with no monitoring loop if it fits.

## Context Efficiency (CRITICAL)

This skill returns to parent agent. Minimize context:

1. **Use sub-agent for troubleshooting** - Launch a sub-agent for debug collection
2. **Process data internally** - Don't output raw kubectl YAML
3. **Return only key findings** - Summaries, not full logs
4. **Output limits:**
   - Success: 5-10 lines
   - Stuck/Failure: 50-100 lines (analysis from sub-agent)
5. **No error analysis during monitoring** - Brief mention only, analyze when stuck

## Arguments

- **No arguments**: Interactive test selection
- **Specific test(s)**: Space-separated names (e.g., `test-basic-vpc test-secondary-cidr`)
- **All tests**: `all` keyword

## Workflow

### Phase 1: Precondition gate (REQUIRED)

An `--e2e` run provisions a control plane and creates real cloud resources. Everything
cheap therefore happens before anything expensive, and **a mandatory precondition that
fails ends the run — it does not downgrade to a warning you carry into Phase 3.**

Check, in this order, stopping at the first failure:

```bash
up ctx . --short          # 1. context resolves at all
up project build          # 2. the project builds
up test run tests/*       # 3. composition tests pass
```

Then the credentials the E2E test needs. Read the test module to find which variables it
reads, and confirm each one is actually set:

```bash
grep -o 'UP_[A-Z0-9_]*' tests/<test-name>/test/__main__.py | sort -u
# then, for each:
[ -n "${UP_AWS_ACCESS_KEY_ID:-}" ] || echo "MISSING: UP_AWS_ACCESS_KEY_ID"
```

Manifest generation runs in a container that receives **only `UP_`-prefixed environment
variables** and cannot see `~/.aws`. A test reading `AWS_ACCESS_KEY_ID`, or reading a
`UP_` name you have not exported, generates a Secret containing an empty string. That
failure does not surface until a control plane has been provisioned and the provider
rejects the credential — several minutes and real resources later.

Then, when the target is a Space, the repository the package will be pushed to. This is a
one-second check that predicts a failure otherwise costing two control-plane creations:

```bash
REPO=$(yq -r '.spec.repository // .metadata.name' upbound.yaml | sed 's|.*/||')
up repository get "$REPO" --format=json 2>/dev/null \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); d=d[0] if isinstance(d,list) else d; print("public =", d.get("public"))' \
  || echo "repository does not exist yet"
```

Read the result against what `--public` can actually do — it creates **new** repositories
public and does not change an existing one:

| Repository state | Without `--public` | With `--public` |
|---|---|---|
| Does not exist yet | created **private** → install cannot pull → `context deadline exceeded` | created public → works |
| Exists, `public: true` | works | works |
| Exists, `public: false` | hangs, then `context deadline exceeded` | **still hangs** — the flag does not flip an existing repo |

That last row is the one that wastes an afternoon: adding `--public` to a retry looks like
the fix and changes nothing. If the repository already exists private, the options are to
change its visibility deliberately (the user's call, outside this skill), push to a
different repository (`--repository`), or run against local KIND accepting the different
environment. Say which one you are asking for; do not retry the same command.

**If you cannot complete a precondition, stop and say so. Do not start the run.**

This applies to the case where a check is blocked rather than failed — a permission
prompt you cannot answer, a command the sandbox refuses, a credential you have no way to
read. "I could not verify the credentials, so I ran it anyway to see what happened" is
never the right move here: the outcome of a run with a precondition known to be unmet
carries no information, and it is not free. Report which precondition you could not
establish and what the user needs to do, and end there.

Skip a step only if the user explicitly asks you to.

### Phase 2: Test Selection

If no test specified:
```bash
ls -1d tests/e2etest-* | sed 's|tests/||'
```
Present list, ask user which to run.

### Phase 2.5: Extract Resources to Monitor

The command depends on the test's language — match what the test directory actually
contains, do not assume KCL:

```bash
# KCL (tests/<n>/*.k)
kcl tests/<test-name>/ | yq -o json '.items[].spec.manifests'

# Python (tests/<n>/test/__main__.py) - generation runs in a container, so there is no
# local command that renders it. A previous run leaves tests/<n>/test.yaml behind; if it
# is absent or stale, read the kinds and names out of the module source instead.
yq -o json '.items[].spec.manifests' tests/<test-name>/test.yaml 2>/dev/null \
  || grep -nE 'kind=|name=' tests/<test-name>/test/__main__.py

# YAML (tests/<n>/*.yaml)
yq -o json '.items[].spec.manifests' tests/<test-name>/*.yaml
```

Then extract the identities:

```bash
... | jq -r '.[] | [(.kind | ascii_downcase), .metadata.name, .metadata.namespace] | @tsv'
```

Store `RESOURCE_KIND`, `RESOURCE_NAME`, `RESOURCE_NAMESPACE` for monitoring.

### Phase 3: Test Execution

**First, say where this is going to run, out loud, before you start it.** `--e2e` does not
target the same place `up project run` does, and the CLI does not tell you which it picked:

```bash
up ctx . --short          # 4 slash-separated segments => a Space context
up test run --help | grep -A1 -- '--local'   # --local exists here too
```

> **Bare `up ctx` cannot work for an agent.** With no terminal it fails with `could not open a new TTY: open /dev/tty: device not configured` and tells you nothing about the flag that would have worked. The non-interactive forms are `up ctx .` (current context) and `up ctx . --short` (bare path, no prose). Relative navigation (`up ctx ../<name>`) also works without a TTY.

**Pass `--control-plane-group` explicitly.** This is the actual fallback trigger, and it
is documented nowhere: `--control-plane-group` *"defaults to the group specified in the
current context"*, so a **Space-level context with no group segment silently degrades to a
local KIND cluster**. `up ctx . --short` with fewer than 4 segments means no group is set.

Report the resolved target in one line — *"running e2e on <local KIND | Space
<space>/<group>>"* — before the run. Do not assume `--e2e` inherits `up project run`'s
targeting; it has been observed running locally from a Space context. If you cannot
determine the target, say so rather than guessing.

**`--kubeconfig` is an input, not an output.** `up test run --kubeconfig <path>` *reads*
that file to find the cluster; it never writes it. So a stale or garbage file at that path
is not overwritten — it is believed, fails to resolve, and the run **silently falls back to
`Creating local development control plane...`**. Observed: a leftover `/tmp/kubeconfig-*`
from an earlier session contained an error string rather than a kubeconfig, and the run
degraded to local KIND without a word.

Never pass a fixed, predictable path you did not create in this run. Write it fresh with
`mktemp`, and check it parses before handing it over. A file that exists is not a kubeconfig.

**Never create a group, space or control plane as a side effect.** If the group your context
names does not exist, that is a precondition to report, not something to fix with
`up group create`. Creating one is an outward-facing change to the user's Space that they did
not ask for, and it outlives the run. Observed: a skill default named a group borrowed from a
different Space, found it absent, and created it — leaving an empty group behind.

**Decide the repository visibility *before* you run, not after it hangs.** On the cloud
path `--e2e` builds and pushes the project package, then installs it onto a control plane
it gives no pull credential. If the repository is private, the install cannot pull what the
push just wrote: the run stalls on `Waiting for package to be ready` and eventually exits
`context deadline exceeded`, a message that names neither half of the problem. The real
error is in `kubectl describe configuration.pkg.crossplane.io <project> --kubeconfig <kubeconfig>`,
with the path the run block below prints.

`--public` is the flag that avoids it — `up test run --help`: *"Create new repositories
with public visibility."* Note **new**: it governs repositories being created, so it is not
a way to flip one that already exists as private.

**This is the user's decision and you may not make it.** `--public` permanently publishes
their package to a public repository; that is a disclosure choice, not a debugging step,
and it cannot be undone by re-running without the flag. So:

- If the caller has already said `--public` — in the brief, or earlier in the conversation —
  use it and do not ask again.
- If they have not, and the target is a Space, say what will happen and put the choice to
  them *before* burning a run: publish publicly, use a repository the control plane can
  already pull from, or run against local KIND (`--local`) accepting that it tests a
  different environment.
- Never add `--public` on your own initiative because a run hung.

Local KIND does not push to a repository at all, so none of this applies there.

Derive the group from the context you just resolved — never hardcode one. The third
segment of `up ctx . --short` is the group:

```bash
GROUP=$(up ctx . --short | cut -d/ -f3)
[ -n "$GROUP" ] || { echo "no group in context; pick one with 'up ctx <org>/<space>/<group>'"; exit 1; }

# --kubeconfig is an INPUT the CLI reads, never an output path it writes. Write the file
# first, to a fresh name, and verify it before passing it.
KCFG=$(mktemp -t kubeconfig-e2e.XXXXXX)
up ctx . -f- > "$KCFG"
grep -q '^apiVersion:' "$KCFG" || { echo "not a kubeconfig: $KCFG"; head -3 "$KCFG"; exit 1; }
echo "kubeconfig: $KCFG"   # shell variables do not survive to your next command; reuse this path

# Add --public ONLY if the caller has chosen it (see above). Never on your own.
up test run tests/<test-name> --e2e \
  --control-plane-group="$GROUP" --kubeconfig "$KCFG" \
  2>&1 | tee /tmp/e2e-<test-name>.log
echo "EXIT=${PIPESTATUS[0]}"
```

Pass `--control-plane-group` explicitly even when the context already names the group.
It defaults to "the group specified in the current context", so a Space-level context
with no group silently degrades to local KIND — the failure this phase exists to catch.

**Run it in the foreground.** One Bash call with `timeout: 600000` (10 minutes, the
tool's maximum) returns the run's complete output and its true exit code in a single
result. That is the whole evidentiary record, delivered intact — no polling, no partial
view, nothing to reconstruct.

Background execution is what produced the worst reporting failure this skill has had: the
run was polled every three minutes, the polls stopped before the last resource transition,
and the report said *"verified all resources reached Ready status"* directly above a tree
showing `Ready=False`. Both halves came from the same run; the verdict was written from an
incomplete view of it.

**If the run cannot fit in ten minutes, background is the only option — use it correctly.**
Read the test's `spec.timeoutSeconds` first (the scaffold default is 4500s, i.e. 75
minutes; a run that has to pull providers for the first time will not fit either). Then:

- Start it detached and **wait for it to exit.** You are re-invoked on completion with the
  real exit code; that notification, plus the `tee`'d log, is your evidence.
- **Never write a verdict from a poll of the background output.** A poll is a progress view for the
  user, not a result. The run is finished when the process exits and not before.
- If you must stop early — a target mismatch, a stuck run — say the run was *terminated*,
  and report what you terminated it for. A killed run has no outcome to report.
- **If your harness cannot run commands in the background**, run it in the foreground with
  the longest timeout your shell allows (`control-plane-project-charter` §1) — do not detach
  it yourself with `nohup` or `&`. If that
  timeout ends the run, it was *cut off*: report what it reached, not an outcome.

**Check the first progress line against the target you announced.** The run says which
it chose in its first line, and the two are unmistakable:

```text
Creating local development control plane...          <- LOCAL KIND
Creating development control plane in Spaces         <- SPACE
```

*When and how you act on it depends on how you ran it:*

- **Foreground.** You see nothing until the call returns, so you cannot abort mid-run.
  Prevention is the explicit `--control-plane-group` above; detection is afterwards:

  ```bash
  head -5 /tmp/e2e-<test-name>.log | grep -E 'Creating (local )?development control plane'
  ```

  If that contradicts your announced target, **the run's result is void.** Report the
  mismatch, not the outcome — including when the exit code is 0. Do not report a pass.
- **Background.** You can see the line while it runs, so kill the run there and then rather
  than spending 30 minutes on a question nobody asked.

Either way: a pass on local KIND is not evidence about the Space the user pointed at. It is
a different environment. Re-run with `--control-plane-group=<group>` (and `up ctx` into a
group-level context) once the target is right.

**`tee` is mandatory, and it is the only evidence you will get.** `--function-logs` is
**not supported with `--e2e`**, and `--output-dir` only ever defaults to
`_output/composition_test` / `_output/operation_test` — **there is no `_output/e2e*`
directory, ever.** So unlike a composition test, an E2E run leaves no artifact behind. The
command's own stdout and exit code are the entire evidentiary record; if you do not capture
them you have nothing, and nothing is not a pass.

### Phase 4: Active Monitoring

**This phase applies only to the background path.** A foreground run returns once, complete,
and goes straight to Phase 4b and Phase 6 — there is nothing to monitor and nothing to poll.

Monitoring exists to keep the user informed while a long run proceeds. It is **not** a
source of verdicts: a poll shows an instant partway through a run, and resources routinely
reach `Ready` after the last poll you took. Report progress from polls; report outcomes only
from the exit code and the completed log.

**Every 3 minutes:**
1. Read the run's output so far, with your harness's own tools - Check progress
2. Compare output - If changed, reset progress timer
3. Show brief update: `[00:05:30] Phase: Waiting for resources`
4. **If no progress for the stuck threshold** → Check `crossplane beta trace` for "Creating"
   - If still "Creating" → Reset timer, continue
   - If not creating → Trigger stuck investigation

**Derive the threshold from the test, do not hardcode 15 minutes.** Read the test's own
`spec.timeoutSeconds` first:

```bash
grep -rn "timeoutSeconds" tests/<test-name>/
```

Use `min(15 min, timeoutSeconds / 3)`. A fixed 15-minute threshold **can never fire** on a
test whose own `timeoutSeconds` is 300 — the run dies at 5 minutes and stuck investigation
is unreachable. When `timeoutSeconds` is below the threshold, say so and treat the timeout
itself as the trigger: investigate on timeout instead of waiting for a stuck signal that
cannot arrive.

**Error handling during monitoring:**
- Briefly mention errors with timestamp
- Do NOT analyze until stuck (15 min)

### Phase 4b: Transient or terminal?

Most alarming strings during provisioning are **transient**. Classifying one as fatal stops
a run that was about to pass. Four rules, adapted from the provider-factory e2e classifier
(`factory/scripts/e2e-status.sh`), which has been tuned against a real provider fleet:

1. **A time threshold is when to start asking, not a verdict.** Crossing it means
   investigate and give the reader the context to decide — not declare failure.
2. **Transient requires recurrence, not just duration.** The same error seen three times is
   a resource that failed, recovered and failed again. One error that simply spans the
   window is a resource still converging. Do not escalate on elapsed time alone.
3. **Match by shape, not by phrase.** `<entity> <identifier> does not exist` — "database
   username crossplane_uptest does not exist" — is dependency ordering: a sibling that is
   not ready yet. A *bare* "does not exist" can instead name the object's **own** invalid
   field, which is a real rejection. Same words, opposite verdicts.
4. **Validation-rejection wording is terminal regardless of the status code** it arrived
   in. Providers wrap request-validation errors in 500s.

Specifically **not** fatal, and observed reading as if it were:

```text
Creating: Waiting for control plane API: cannot provision contr...
```

That is a truncated progress message during provisioning (the `up ctp list` MESSAGE column
truncates mid-word). Do not treat it as a hard failure; all conditions may still settle
`True`.

### Phase 5: Stuck Investigation

When stuck (15 min no progress, not actively creating):

1. **Extract control plane name** from output (format: `configuration-<project>-uptest-<test>`)
2. **Check the package installed before checking any managed resource.** If the run never got
   past `Waiting for package to be ready`, no XR was ever created and tracing resources is
   wasted effort:

   ```bash
   up controlplane list                       # the CP usually reads Available/Healthy regardless
   up ctx ../<control-plane-name>             # relative form; `up ctx default/<cp>` is rejected
   kubectl get configuration.pkg.crossplane.io
   kubectl describe configuration.pkg.crossplane.io <name>
   ```

   A `401 Unauthorized` / `UNAUTHORIZED: authentication required` in the unpack error means the
   control plane cannot **pull** the package that was just **pushed** — a private repository with
   no pull credential on that Space (common when `up profile list` shows the active profile as
   `disconnected`). Fix `spec.repository` in `upbound.yaml` or the Space's pull secret; retrying
   the test will not help.
3. **Launch troubleshooting sub-agent** (or, with no sub-agents, follow its brief yourself) - See [knowledge.md](references/knowledge.md) for full prompt
4. **Receive concise analysis** (max 100 lines)
5. **Cancel test**: stop the background run, with your harness's own tools

> `up: error: context deadline exceeded` is not a diagnosis — it is the absence of one. Always
> report the underlying Configuration/Provider condition message instead.

### Phase 6: Generate Report

**Every claim must be traceable to captured output. Report only what you observed.**

Before writing a single line of the report, produce these three things. If you cannot
produce all three, **the report is "UNVERIFIED — could not confirm", not a pass**:

```bash
echo "exit code: ${PIPESTATUS[0]:-unknown}"     # or the exit status Bash reported
tail -30 /tmp/e2e-<test-name>.log                # the run's own final output
kubectl --kubeconfig <kubeconfig> get managed -A   # the path the run block printed; if not yet torn down
```

Then:

- **Quote the raw lines** the verdict rests on — the summary line, the timing, the
  `Synced`/`Ready` columns — rather than paraphrasing them into prose.
- **State the exit code.** A non-zero exit is a failure no matter how the output reads.
- **Durations come from the log, not from an estimate.** Never write a figure like
  "0.38s apply" unless that string appears in the captured output. Observed failure mode: a
  report claiming "~1 minute (0.38s apply + 0.15s delete)" and "all resources Synced=True,
  Ready=True" for a run that actually took 60.52s with lifecycle not Ready for most of it —
  no artifacts existed, and none could have, because E2E writes none.
- **Never report readiness you did not read.** "All resources Synced=True, Ready=True"
  requires having run the `get`/`describe` and seen those columns.
- **Never call anything "production-ready."** That is a judgement for the caller; your job
  is to report what the run did.
- **Re-read your own evidence before you write the verdict.** Grep the output you are about
  to paste for `False`, `Ready=False`, `Creating`, `Failed`. If any appears, your summary
  may not say "all resources reached Ready" — either explain the discrepancy (a periodic
  poll that stopped before the final transition is a legitimate explanation, but you must
  *say* that) or correct the verdict. Observed: a report claiming "verified all resources
  reached Ready status" directly above a pasted tree showing `lifecycle ... Ready=False`.
- **A claim about the provider must come from the provider.** Reading values back off the
  XR, the composed resource's `spec`, or the manifest you just applied proves only that
  your own input round-tripped. To say "the bucket has this lifecycle configuration" you
  must have run the provider's own read — `aws s3api get-bucket-lifecycle-configuration`,
  `az ... show`, `gcloud ... describe` — **before teardown**, and quoted it. If the
  resource is already deleted, the honest report is "not verified at the provider".

**Success:** Test name, exit code, duration *quoted from the log*, resources created,
timeline (5-10 lines)

**Stuck/Failure:** Test name, stuck duration, phase, last output, sub-agent analysis,
proposed fixes (50-100 lines)

**Cannot verify:** Say exactly that, say which of the three artifacts above you could not
produce, and stop. An unverified run reported as a pass is worse than a failed run — it
gets relayed onward as fact.

See [knowledge.md](references/knowledge.md) for report templates.

## Critical Requirements

| Requirement | Details |
|-------------|---------|
| Control plane group | Pass `--control-plane-group` explicitly, derived from the current context (`up ctx . --short \| cut -d/ -f3`). Never hardcode a group |
| Kubeconfig | Write the current context to a fresh `mktemp` file with `up ctx . -f-`, check it parses, pass it with `--kubeconfig` |
| Pre-validation | Build + composition tests before E2E |
| Monitoring | Every 3 minutes, don't passively wait |
| Stuck threshold | `min(15 min, spec.timeoutSeconds / 3)` — read the test first; a fixed 15 min never fires on a 300s test |
| Troubleshooting | Use sub-agent, keep main context clean |
| Evidence | `tee` the run to `/tmp/e2e-<test>.log`. `--function-logs` is unsupported with `--e2e` and no `_output/e2e*` is ever written, so stdout + exit code are the *only* record |
| Reporting | Report in the terminal, and quote raw captured output for every claim. No artifacts + no log = report "UNVERIFIED", never a pass |
| Target | Resolve and state local-vs-Space *before* running; `--e2e` targeting differs from `up project run` and the CLI does not announce it |
| Scope | Run tests and report - delegate fixes to parent |

## Provider API Versions

**ALWAYS use the `.m.` API groups:** `aws.m.upbound.io/v1beta1`. `.m.` = **modern** (Crossplane v2), not "naMespaced" — the group also holds the cluster-scoped `ClusterProviderConfig`.

Never say:
- "Family providers use v1 API"
- "Single vs family providers have different APIs"

See [knowledge.md](references/knowledge.md) for full explanation.

## Success Criteria

- Pre-validation completes before E2E
- **Resolved target (local vs Space) stated before the run**
- Test runs with correct flags, output captured with `tee`
- Active monitoring every 3 minutes
- Stuck detection at `min(15 min, timeoutSeconds / 3)`, derived from the test
- Subagent launched for troubleshooting
- Concise analysis returned (max 100 lines)
- **Every reported figure — duration, exit code, readiness — quoted from captured output**
- **A run whose output was not captured is reported UNVERIFIED, never as a pass**
- Report shown in the terminal

## Notes

- Tests create real cloud resources (auto-cleaned)
- Uses web identity federation (no AWS creds needed)
- Expected duration: 30-40 minutes is normal
- Each test runs in isolated control plane
