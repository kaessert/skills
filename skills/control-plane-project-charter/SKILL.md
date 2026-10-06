---
name: control-plane-project-charter
description: Shared rules and per-language references for the Upbound control-plane-project skills - agent behaviour, the test-first loop, what a v2 composed resource needs, the container boundary, what a green run proves, how to report, and the KCL, Python, TypeScript, Go and YAML references. Load it alongside the task skill - task skills reference it but do not load it, so loading one leaves this unread. Not the skill to pick for doing the work on its own - author-composition for composition function code, author-tests for composition or E2E tests, author-configuration-package for scaffolding, XRDs and dependencies, verify-configuration to build, verify or run the project, e2e-test-configuration to run E2E tests, and plan-v2-migration or execute-v2-migration for a Crossplane v2 migration.
license: Apache-2.0
references:
  - references/charter/agent-context.md
  - references/charter/container.md
  - references/charter/evidence.md
  - references/charter/generators.md
  - references/charter/provider-schema.md
  - references/charter/targets.md
  - references/charter/tdd.md
  - references/charter/v2-resources.md
  - references/charter/xrd-design.md
  - references/languages/README.md
  - references/languages/go-templating.md
  - references/languages/go.md
  - references/languages/go/functions.md
  - references/languages/go/tests.md
  - references/languages/kcl.md
  - references/languages/kcl/patterns-logic.md
  - references/languages/kcl/patterns.md
  - references/languages/kcl/pitfalls.md
  - references/languages/kcl/tests.md
  - references/languages/python.md
  - references/languages/python/examples.md
  - references/languages/python/imports.md
  - references/languages/python/patterns.md
  - references/languages/python/pitfalls.md
  - references/languages/python/readiness.md
  - references/languages/python/test-templates.md
  - references/languages/python/tests.md
  - references/languages/typescript.md
  - references/languages/yaml.md
  - references/rules-card.md
---
# Development Charter

**Every skill in this plugin follows this charter.** It holds the rules that do not depend on
which language a project is written in or which skill you happen to be: how to behave as an
agent, how to develop, what Crossplane v2 actually requires, and how to report what you did.

**It does not replace the task skill.** Before you write, review or specify work, read the
[rules card](references/rules-card.md) and load the skill that owns the work:

| Work | Load | And read |
|---|---|---|
| XRD, `upbound.yaml`, dependencies, examples, ProviderConfig, MRAP | author-configuration-package | its `mrap.md` for an MRAP |
| function code | author-composition | the language file (§10), e.g. `languages/go/functions.md` |
| anything under `tests/` | author-tests | the test language's file, e.g. `languages/go/tests.md`; an `E2ETest`: its `e2e.md` |
| running E2E tests | e2e-test-configuration | its `local.md` or `space.md` |
| reviewing | the task skills for what changed | the card's reviewer variant |
| specifying work for someone else | the skills that work needs | — |

Language-specific syntax lives in [`languages/`](references/languages/) — one file per language,
indexed by [`languages/README.md`](references/languages/README.md), which holds the detection table (§10). Skill
workflows live in each skill's `SKILL.md`. Nothing in this file is language-specific, and
nothing in it is optional.

When a skill's own guidance contradicts this charter, **the charter wins** — and that
contradiction is a bug worth fixing in the skill.

**This file holds the rules; the detail sits beside it in [`charter/`](references/charter/).** Read this
one end to end — it is short on purpose. Follow a link when you need the evidence, the tables
or the worked example behind a rule.

---

## 1. Know which kind of agent you are

How you were started decides whether you can hold a conversation. Know which you are before
you consider asking anything; every skill's mode line means this:

- **Interactive** — loaded into the user's conversation (inline): ask only what the project
  can't tell you.
- **Unattended** — handed a brief as a separate agent (forked), or no user in the loop: never
  ask; decide from the spec and state the assumption, or stop and report.

**When nobody can answer, never block on a question** — that includes a caller that cannot
relay one. Wherever a skill says to ask, read it with this rule.

**Re-read a document before you write from it.** Long runs lose old file and command output.
Before you write anything derived from a document — a work item, a test expectation, a quote,
a field value — re-read the section you rely on in that same step. Never quote from memory. If
the re-read contradicts what you wrote, fix that first.

**Detail:** [`charter/agent-context.md`](references/charter/agent-context.md) has what each
context may and may not do, why a fork's only output channel is prose, and how to hand work to a
sub-agent or run a long command when your harness cannot: in band and in the foreground, never
detached by you.

## 2. Discover, do not interview

Inline or forked, the project answers most questions faster and more reliably than the user
does.

**The project's own decisions win over these skills' defaults.** When a design document,
work item or agent instruction for this project decides something differently — a
`providerConfigRef` the platform needs, a gate script in place of a skill's verification
steps, local E2E only — follow it, and say in your report where you departed from a
skill's default and why.

| What you need | Where it is |
|---|---|
| Project root | `args`, or the nearest ancestor containing `upbound.yaml` |
| XR kind, group, version, spec schema | `apis/*/definition.yaml` |
| Existing composition + `functionRef` | `apis/*/composition.yaml` |
| Available provider families | `upbound.yaml` `spec.dependsOn` |
| Example XR shape | the file `up example generate` writes: `examples/<kind-lowercase>/<xr-name>.yaml`, the name defaulting to the lowercase Kind (`examples/network/network.yaml`, up v0.55.0). Find it; don't assume `example.yaml` |
| Composition language | `functions/*/` contents — see [`languages/`](references/languages/) |
| Test language | the `tests/*/` dirs that produce a `CompositionTest` or `E2ETest` — may differ from the composition language; with none yet, §10 picks it |
| Provider field names, types and constraints | the generated models under `.up/` |
| Current Space / group / control plane | `up ctx . --short` — how to read it: [`charter/targets.md`](references/charter/targets.md) |

Read the XRD's **defaults** before you design anything against it. `up test run` applies them
itself — it derives a CRD from the XRD and runs Kubernetes' structural-defaulting library over
the XR before the pipeline sees it — so a field with a `default:` reaches your function whether
the example sets it or not, and a test that asserts only what the example mentions is asserting
the XRD's defaults back to itself.

## 3. Develop test-first (RED → GREEN → REFACTOR)

This is the plugin's default flow for composition code, tests, and migrations alike.
`author-tests` owns the authoring detail; the loop itself is
here because every skill is bound by it.

**Test-first is for behaviour:** the function, the composition, how status is derived.
Scaffolding, `upbound.yaml` metadata, dependencies, the XRD, an MRAP and the examples are
declarative: `up project build`, author-configuration-package's `check_xrd_schema.py` and the
composition tests that use them check those. Write no test program for them, and don't copy a
skill's script into the project.

**Why test-first.** The most common false report is coverage for a test that could not have
failed — *"covers the conditional branch"*, *"Coverage: complete"*. Watching the test fail first
makes a coverage claim checkable: you saw it catch the absence of the implementation.

### The loop

1. **RED — write the test, run it, and read the failure.**

   ```bash
   up test run "tests/<t>"      # expect: FAIL
   ```

   Run it directly. Do not route this through `verify-configuration`: that skill builds the
   package and runs the whole suite, and can go on to E2E or a control plane, which is not an
   inner loop.

   **A failure is only RED if it fails for the reason you intended.** Check the message:

   | Failure | Verdict |
   |---|---|
   | `no actual resource found` for the resource you are about to compose | valid RED |
   | a field mismatch naming the exact field you are adding | valid RED |
   | a syntax error, an unresolved import, a missing `compositionPath`, a run that stops at `✗ Parsing tests`, a bug in the test's own logic | **not** RED, even though it exits 1 — the test is broken, not the code. Fix it before writing any implementation |
   | a compiled language (Go): `undefined: <symbol you are adding>` | **not** RED — a compile error. Add a stub returning the zero value, then watch the assertion fail |
   | passes immediately | **not** RED — the assertion is vacuous, or the behaviour already exists |
   | E2E: an implementation mutation (drop a composed resource others depend on, break a selector) that never readies within a short `timeoutSeconds` | valid RED, and optional (below). Editing `defaultConditions` or an expected value is not; an unparsable condition is a broken test (author-tests' `e2e.md` reference) |

   Record the failure text. It goes in your report as the evidence that the test bites.

   **RED is required for composition tests and function unit tests, and optional for a new
   `E2ETest`.** An e2e RED costs a real control-plane run: take it when it is cheap, as in the
   table's last row; otherwise report the E2ETest as unproven (§4).

2. **GREEN — implement** until the test passes, and no further.

3. **REFACTOR** with the suite green, then add the next failing assertion and repeat.

**Use distinguishing inputs.** Every value the function passes through gets, in at least one
test, an input that is neither its default nor shared with a sibling field, or a hard-coded
constant stays green (author-tests Phase 3). For a pass-through field, expected == input is
correct; prove it by hard-coding the field in the function and seeing a test go red, never by
editing the expectation.

**Detail:** [`charter/tdd.md`](references/charter/tdd.md) has the two-tier inner loop (every
`up test run` pays a full build, so use a fast tier for crashes), and how to backfill tests for
code that already works by proving each one can fail: mutate the implementation, never the
test's expected value.

## 4. Report the effect, not the intent

Overstated reports follow one pattern — a green composition suite called "production-ready",
a local KIND run reported as a Space pass, "all resources Ready" above a tree showing
`Ready=False`, provider values "verified" from the input manifest: asserting what the change was
*meant* to do instead of reading back what it *did*.

Before writing any summary:

1. **Name what you actually ran**, and what its exit code was — the command's own. After
   `up test run … | tail -20`, `$?` is `tail`'s, not `up`'s. Redirect, then read `$?`
   (`up test run "tests/test-*" > /tmp/t.log 2>&1; echo "exit=$?"`), or read `${PIPESTATUS[0]}`
   straight after the pipe in bash.
2. **Re-read the evidence you are about to paste** and check it does not contradict your
   verdict.
3. **Distinguish the layers.** A render is not an install; an install is not a provider
   accepting the resource; `Ready=True` is not the provider holding the value you meant.
   Say which layer you reached.
4. **When you did not verify something, say so plainly.** "Not verified at the provider" is
   a useful report. A checkmark you cannot support is not.
5. **A coverage claim is a claim about what would fail.** Before writing "covers X",
   "complete", or "N/N", answer: *what change to the code would make this go red?* If you
   cannot name one, you have not covered X — you have written something that passes.
6. **Drop the checkmark register.** `✅ Complete`, `PASS`, and a tidy summary table read as
   verification regardless of what is behind them, and they are what makes an overstated
   report persuasive. Write what ran, what it printed, and what remains unknown. If the
   honest summary is "tests pass; provider validity unchecked; not deployed", that is the
   summary — it is more useful to the caller than a confident one that is wrong. A skill's
   success criteria are checks for you, not a report format: do not tick them off in a report.
7. **Comments, docs and READMEs claim no more than a named test or run.** They are read as
   reports.

## 5. Crossplane v2: what a composed resource actually needs

**These rules are for a v2 project.** A v1 project — which is what every `up project init`
template produces (§10) — keeps its v1 APIs and its Kinds; migrating it is separate work
(`plan-v2-migration`).

### API groups and versions

Compositions target the `.m.` provider API groups (`.m.` means *modern*, not "naMespaced":
[`charter/v2-resources.md`](references/charter/v2-resources.md)).

| Aspect | Use this | Not this |
|---|---|---|
| Managed resource `apiVersion` | `<service>.<cloud>.m.upbound.io/v1beta1` (Upbound providers) or `<...>.m.crossplane.io/v1beta1` (community) | the same group without `.m.` |
| A new XRD | `apiextensions.crossplane.io/v2` + `scope: Namespaced`; Kind without an `X` prefix, no `claimNames` | `v1`, cluster-scoped, `claimNames` |
| **Composition** | **stays `apiextensions.crossplane.io/v1`** | there is no `v2` Composition — do not bump it |

### Set `forProvider`, and stop

Crossplane v2 fills in the rest. Adding "required v2 fields" the project does not ask for is at
best noise and at worst breaks the resource.

| Field | Do you set it? (the default; the project may override) | Why |
|---|---|---|
| `metadata.namespace` | **No** | A namespaced XR's namespace overwrites it; only a cluster-scoped XR's resources keep the one the function sets |
| `managementPolicies` | **No** | The CRD defaults it to `["*"]`; never write that yourself. Set it only for another policy (orphan on delete) or when the project's API exposes it |
| `deletionPolicy` | **No** | A namespaced MR has no such field; orphan with `managementPolicies` |
| `providerConfigRef` | Omit it if and only if `ClusterProviderConfig/default` exists and is the right one | The CRD defaults it to `ClusterProviderConfig/default` |
| `metadata.name` | Only for a stable external name | Otherwise generated: deterministic in a render (safe to assert), not across re-creations |
| `crossplane.io/composition-resource-name` | Never by hand | It comes from the key you store the resource under |

The verified behaviour behind each row (the source lines, the name formula):
[`charter/v2-resources.md`](references/charter/v2-resources.md).

**The table is about the composed resource's own metadata, not about objects inside
`forProvider`.** A Kubernetes object embedded in a managed resource — the `manifest` of a
provider-kubernetes `Object`, for instance — is input to the provider, and nothing fills in its
namespace. Set it explicitly, normally to the XR's namespace: without it a provider-kubernetes
`Object` stays `Synced=False` with `an empty namespace may not be set when a resource name is
provided` (v1.3.3), and composition tests that assert the same omission stay green.

**These are defaults; the project may override them (§2).** When the project's spec or API
sets `managementPolicies`, `providerConfigRef` or an MR's `metadata.namespace` — an XRD that
exposes `managementPolicies` as a parameter, a spec that requires a per-XR `providerConfigRef`
— set it as specified and say so in your report. A review flags these fields as removable
**unless the project's spec or API sets them**, and flags
`providerConfigRef.kind: ProviderConfig` as a bug only when no namespaced `ProviderConfig` of
that name exists in, or is created in, the XR's namespace.

**Detail:** [`charter/v2-resources.md`](references/charter/v2-resources.md) has what these CRD
defaults do to a render (it differs by language), when a `providerConfigRef` is genuinely
warranted, what a missing or wrong ProviderConfig looks like on a control plane, and the two
greps that catch a hardcoded one.

### The XRD

**Write the XRD yourself** rather than inferring it from an example with `up xrd generate`: an
example carries values, never constraints, so an inferred schema loses every `required:`,
`default:`, open-ended map and `status` field you meant to have.
[`charter/v2-resources.md`](references/charter/v2-resources.md) has the v2 skeleton and what
inference does to the generated model.

**Then design the schema, do not just transcribe fields.** A schema that parses can still be
one nobody can consume: no `description` means `kubectl explain` documents nothing, no `enum`
or `pattern` means bad input fails in the provider rather than at `kubectl apply`, and an empty
`status` means the caller cannot learn what the composition computed. Because XRD versions must
round-trip, most of this is permanent from the first version that ships, so it is cheap at
`v1alpha1` and impossible later.
[`charter/xrd-design.md`](references/charter/xrd-design.md) has the rules, the CEL patterns, and the
`--dry-run=server` loop that proves them on a control plane.

## 6. The provider schema is a lower bound, not the constraint set

Namespaced APIs and `forProvider`-only are *Crossplane* correctness; they say nothing about
whether the provider accepts the resource, and a composition test passes either way.

**Check every Kind you compose against its provider.** Read the conditional rules the
generated models record in docstrings and field descriptions (`Required if …`, `Conflicts
with …`): optional in the type means only that the CRD does not require it. Then check the
cloud API's own rules (name formats, reserved prefixes, create-only fields), and treat *one
list element → one object* as a decision you justify, not the default.

State the result in your summary: which Kinds you checked, what the schema required, and
which API-level rule you could not confirm. "I checked and found nothing" is a valid result.
Silently skipping is not.

**Detail:** [`charter/provider-schema.md`](references/charter/provider-schema.md) has examples
(an S3 lifecycle rule that renders and fails with `MalformedXML`), the measured hit rates, the
one docstring that is always a false positive, and the rule classes only the cloud API docs
hold.

## 7. The container boundary

`up test run` runs the test program of every directory it matches before any test, with or
without `--e2e` (up v0.55.0). **Go test programs run locally, with your full environment; KCL
and Python programs run in a container that sees only `UP_*` variables and no `~/.aws`.** Name
every test input `UP_*`, and run the composition gate as `up test run "tests/test-*"`: one e2e
program that exits non-zero — on a missing input, say — fails a plain `tests/*` run at
`✗ Parsing tests`. `no valid CompositionTests found` means the matched dirs produced no
`CompositionTest` (e.g. `e2etest-*` without `--e2e`): a wrong glob, not a failing test.

**Detail:** [`charter/container.md`](references/charter/container.md) has the per-language
table, the `UP_` credential route, the E2E command and the README note, and the tighter second
boundary around function rendering.

## 8. A green run is not evidence

| Green thing | What it actually proves |
|---|---|
| `up project build` | the package was assembled, never that the function *runs*. Only Go compiles here; what each language's build checks: [`charter/evidence.md`](references/charter/evidence.md#what-a-clean-up-project-build-checks) |
| `up test run` printing `No test files found` | **nothing ran.** No test was collected, and it exits 0 anyway — that is not a pass. A test directory that emits no `CompositionTest`, such as a Go test program printing `items: []`, contributes zero tests; next to real tests it just drops out of the count. Report "no tests ran". |
| A composition test suite | the assertions you wrote held against the render. `assertResources` is **partial and positive for objects**: it ignores composed resources it does not list, and within a resource it checks only the fields you name, at every depth. **Lists are the exception** — an asserted list must match the rendered one exactly in length *and* order, or you get `lengths of slices don't match`. A short list assertion is not a weak assertion; it is a failing one. |
| A render | the function produced objects. Not that the API server accepts them, and not that the provider does. |
| `Ready=True` | the provider reconciled *something*. Read back the field you meant, from the live object, not from the input manifest. |

**`up test generate` emits a stub that does not even run.** `assertResources: []` plus empty
`xrPath`, `compositionPath` and `xrdPath`, and the empty `compositionPath` fails before any
assertion is reached:

```
cannot load Composition from "": not a composition: /
```

Per §3's table that is a **broken test, not RED** — fill the paths in first.

The vacuous pass is the *next* state: correct paths, and an `assertResources` list you never
populated. An empty expected list produces no errors, so that test is green and means nothing.

A filled-in single test is not much better: one input shape, asserting only composed
resources, passes over a function that crashes on a minimal XR and drops three of four status
fields.

**Observed-state branches are reachable, and you are expected to reach them.** A render starts
with no observed resources *unless the test supplies `spec.observedResources`*. So code gated
on observed-and-ready is dead in a test that omits that field and live in one that sets it —
write the second test rather than declaring the branch untestable. For a namespaced XR, give
each mock the XR's namespace and the render's name: without the namespace it is silently ignored
([`charter/evidence.md`](references/charter/evidence.md), Coverage). Then be precise about what
it proves: your branch logic, given the status you wrote. It does not prove a provider ever
reports that status. For that, `--e2e` or a live apply — or say it is unverified.

The XRD defaulting in §2 has two limits:

- **Only if the test sets `xrdPath` (or inline `xrd`).** Without it the XR is rendered exactly
  as written and no defaulting happens at all.
- **The XR only.** Composed resources are never touched by this. Provider *CRD* defaults are a
  different mechanism — see §5.

**Detail:** [`charter/evidence.md`](references/charter/evidence.md) has how to find the render
artifacts, how `assertResources` matches a resource, asserting `spec.crossplane.resourceRefs` so
a surplus resource fails the suite, and what a suite must contain (minimal XR, observed-state
branches, status on the composite).

## 9. Never create infrastructure as a side effect

A group, a Space, a control plane or a published package is the user's decision. Running what
you were asked to run — an E2E test, `up project run` — is not a side effect; anything you add
to make it work is.

- **Never create a group, Space or control plane to make a command work.**
- **Never let the context choose the target silently.** Read it with `up ctx . --short`, or
  pass `--local`; a local KIND result is not a Space result.
- **Never pass `--public` on your own initiative.** It publishes the user's package — an
  irreversible disclosure, never a debugging step.
- **Never pass a `--kubeconfig` you did not write and check in this run.**
- **Delete what this run created, and nothing else.** Your own leftovers — a control plane, a
  kind cluster and its registry container, a scratch directory — must be removed before
  you report; for anything else, report what you would delete and let the user choose.

**Abort on a failed precondition; do not proceed and report the symptom.** A check that
comes back *blocked* — not merely *failed* — means the run you are about to start cannot
produce a valid result. Starting it anyway spends real time and produces a failure whose
cause you already knew.

**Detail:** [`charter/targets.md`](references/charter/targets.md) has which control plane a
run lands on, how to read `up ctx`, how the group defaults to `default`, why a bad
`--kubeconfig` silently goes local, what `--public` does and does not change, diagnosing
`context deadline exceeded`, and teardown.

---

## 10. Language dispatch

Detect the composition language from `functions/` and the test language from `tests/`, then
read the matching file. They are separate axes — `up function generate` and `up test generate`
each take their own `--language`, and an existing project may mix them. The detection table — the
markers `up` itself checks, and which reference to read for functions and for tests — is
[`languages/README.md`](references/languages/README.md).

**New tests use the language of the existing tests, else the composition language if `up`
tests in it, else YAML.** Only a test dir that produces a `CompositionTest` or `E2ETest`
counts; a program that emits none (a Go program printing `items: []`) is not a test (§8) and
sets nothing. The reasons and the `init`/`generate` flags:
[`languages/README.md`](references/languages/README.md#choosing-the-test-language-for-new-tests).

**Detail:** [`charter/generators.md`](references/charter/generators.md) has the accepted
`--language` slugs and what each generator actually emits: `up project init` produces a **v1**
project, `up test generate` prepends `test-`, `up composition generate` wires only auto-ready,
and `up xrd generate` drops every constraint.

## Detail files

| Detail file | What is in it |
|---|---|
| [`charter/agent-context.md`](references/charter/agent-context.md) | what inline and forked (separate-agent) skills may and may not do, delegation and long runs (§1) |
| [`charter/tdd.md`](references/charter/tdd.md) | the two-tier inner loop, and backfilling tests for existing code (§3) |
| [`charter/v2-resources.md`](references/charter/v2-resources.md) | what `.m.` means, the verified behaviour behind §5's field table, the v2 XRD skeleton, what CRD defaults do to a render, choosing a ProviderConfig, the symptom of a missing or wrong one (§5) |
| [`charter/xrd-design.md`](references/charter/xrd-design.md) | naming, validation, immutability, status and printer columns for the XR API (§5) |
| [`charter/provider-schema.md`](references/charter/provider-schema.md) | examples, measured constraint density, and the rules that live only in cloud API docs (§6) |
| [`charter/container.md`](references/charter/container.md) | which languages are containerized, and what crosses the boundary (§7) |
| [`charter/evidence.md`](references/charter/evidence.md) | what `up project build` checks per language, reading a render, how `assertResources` matches, making a suite exhaustive, what a suite must contain (§8) |
| [`charter/targets.md`](references/charter/targets.md) | where `up project run` and `up test run --e2e` land (local KIND or a Space), reading `up ctx`, the group, `--kubeconfig`, `--public` and repository visibility, a run stuck on `Waiting for package to be ready`, teardown (§9) — read before a run on a Space, or one without a target flag; a `--local` E2E run needs e2e-test-configuration's `local.md` instead |
| [`charter/generators.md`](references/charter/generators.md) | the `--language` slugs, and what each CLI generator actually emits (§10) |
| [`rules-card.md`](references/rules-card.md) | the charter on one screen, plus a reviewer variant: read them when you build or review |
