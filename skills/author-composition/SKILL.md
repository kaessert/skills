---
name: author-composition
description: Use this skill when the user asks to create, extend, modify, or debug a Crossplane composition function in a control-plane project — in any language (KCL, Python, TypeScript, Go). Detects the function language and applies the matching reference. Also use when asked about Crossplane v2 composition patterns, model/type import paths, namespaced `.m.` APIs, or why a composition renders green but the resource never reconciles. For authoring the tests themselves use author-tests; for XRD design use author-configuration-package. Always load this skill before writing or changing composition function code, instead of writing it directly - also when you get there partway through another skill's workflow, such as scaffolding a new package. It enforces the v2 rules that composition tests cannot catch — `forProvider`-only resources, no dangling `providerConfigRef`, resolved import paths — and the test-first loop that makes a coverage claim checkable.
license: Apache-2.0
references:
  - references/knowledge.md
---

# Composition Authoring

Author and modify Crossplane composition functions, in any language `up function generate`
supports.

## Binding rules — they hold even if you open nothing else

These are the core of `control-plane-project-charter`, which this skill does not load for you;
the charter has the reasons. Where the project's spec, work item or gate script decides
otherwise, the project wins: say so in your report.

1. **Never block on a question nobody can answer.** Decide from the project's spec and state
   the assumption, or stop and report the open question (charter §1).
2. **Never create a group, Space, control plane or cloud resource as a side effect** (§9).
3. **Test first: watch each new test fail for the reason you intended**, then make it pass. A
   broken test is not RED, even when it exits 1: a syntax error, a missing path, a run that
   stops at `✗ Parsing tests`, a bug in the test's own logic (§3).
4. **Backfilling a test for code that already works: mutate the implementation, never the
   test's expected value.** See that test go red, then revert (charter `tdd.md`).
5. **Managed resources carry `forProvider` only**, on the `.m.` API groups: no
   `deletionPolicy`, `managementPolicies` or `metadata.namespace`, and a `providerConfigRef`
   only when `ClusterProviderConfig/default` is not the right config (§5).
6. **Name what ran and the command's own exit code.** After `| tail`, `$?` is `tail`'s: read
   `${PIPESTATUS[0]}`, or redirect to a file and then read `$?`. No command, no claim (§4).
7. **`No test files found` means nothing ran**, though `up test run` exits 0. A test program
   that prints `items: []` contributes zero tests (§8).
8. **For every test you added or changed, name the code change that turns it red**, and say
   whether you saw it fail. If you did not, call the test unproven (§4).
9. **Name the layer you reached** — render, composition test, local control plane, cloud — and
   never claim one you did not reach. Comments and docs claim no more than the test checks (§4).

## Core principle

**A composition's *meaning* is language-agnostic; only its *syntax* differs.**

Every composition function — KCL, Python, TypeScript, Go — receives the same
`RunFunctionRequest` and returns the same `RunFunctionResponse`, and every managed resource
it emits is the same Kubernetes object. The v2 rules, the failure modes, and the design
questions are identical across languages. What changes is how you express them: KCL schemas,
Python Pydantic models, TypeScript interfaces.

So this skill has three layers, and you read all three:

| Layer | File | What it holds |
|---|---|---|
| Charter | `control-plane-project-charter` | agent behaviour, the TDD loop, what v2 requires, the container boundary, reporting discipline. **Binding on every skill.** |
| Agnostic patterns | [knowledge.md](references/knowledge.md) | what each composition pattern *means*, the design questions, the failure modes |
| Language syntax | `languages/` (`control-plane-project-charter` `languages`) | imports, layout, bootstrap, templates, per-language mistakes |

**Load the charter before you start — this skill does not load it for you.** Load the
`control-plane-project-charter` skill, or read its `SKILL.md`, which sits beside this skill's
directory. Apart from the rules at the top of this file, nothing in it is repeated here; when
this file and the charter disagree, the charter wins.

## Phase 0: You run inline, and you are bound by the charter

This skill runs inline — you expand into the caller's conversation, share their
working directory, and can ask. `control-plane-project-charter` §1 (when nobody can answer,
never block) says what that means for asking questions; §4 (report the effect, not the
intent) says what it means for your summary. Both apply in full.

## Phase 1: Detect the language *and the Crossplane generation* — do not ask

**The function language is not necessarily the test language.** Detect the *function*
language from `functions/`, then read the file named. It is in the charter's `languages/`
directory (`control-plane-project-charter/references/languages/`, beside this skill's directory):

```
functions/*/*.k                            → KCL           → kcl.md
functions/*/main.py | */function/fn.py     → Python        → python.md
functions/*/*.ts                           → TypeScript    → typescript.md
functions/*/*.go                           → Go            → go.md, then go/functions.md
functions/*/*.gotmpl                       → go-templating → go-templating.md
```

New tests follow the function language unless the project already has tests in another one
(`control-plane-project-charter` §10: existing tests decide, else the composition language,
else YAML).

No functions yet? Take the language from `upbound.yaml`, else from an existing function
anywhere in the project, else ask — this is a decision, not a discoverable fact.

**Then detect the generation**, which governs more of the guidance than the language does:

```
apis/*/definition.yaml: apiextensions.crossplane.io/v2  → v2: charter §5 (.m. groups, forProvider only) applies
                                                  /v1  → v1: it does NOT
```

A v1 project uses the **non-`.m.`** provider models and a cluster-scoped `ProviderConfig`.
Every `up project init` template is v1 today, so a freshly initialised project is v1 and its
shipped function is a v2 anti-pattern from top to bottom. Match what the project is; migrating
it is a separate, deliberate piece of work (`plan-v2-migration`), not cleanup you do in
passing. `probe_project.py` reports the generation on its first line and recommends imports
accordingly.

**Then read that language file before writing a line.** It carries the layout detection, the
import formula, and the bootstrap, all of which are wrong by default if you guess.

## Phase 2: Discover — do not ask

`control-plane-project-charter` §2 (discover from the project, do not interview) has the
general table.
These are the composition-specific additions:

| What you need | How to get it — no question required |
|---|---|
| **Models missing entirely** (fresh clone) | `.up/` is gitignored and starts **empty**. Run `up dep update-cache`, then `up project build`. Nothing prompts for this and every model import fails until you do |
| Function layout + import prefix | the language file's detection recipe — for Python, `python3 "$SCRIPTS/probe_project.py" --project <root>` |
| Exact import line and class names per Kind | same probe, with the Kinds named |
| Field names and types on a managed resource | `python3 "$SCRIPTS/probe_project.py" --project <root> --fields <Kind>` — prints every `forProvider` field, flags list fields whose Upjet names are misleadingly **singular** (`attribute`, `globalSecondaryIndex`), and lists cross-resource `*Ref`/`*Selector` fields. For other languages, read the generated schema directly |

`$SCRIPTS` is this skill's [`scripts/`](scripts/) directory (`scripts/probe_project.py`,
`scripts/setup_venv.py`, `scripts/run_function.py`), `<author-composition>/scripts`,
where `<author-composition>` is this skill's directory — the directory containing this
SKILL.md — as an absolute path. A wrong path makes every call die with a bare "No such
file". Resolve it once, and check it:

```bash
SCRIPTS=<author-composition>/scripts
[ -f "$SCRIPTS/probe_project.py" ] || echo "probe_project.py not found — pass its path explicitly"
```

The scripts are Python-specific; the other languages read their generated types directly.

**Python: set up the venv now, before Phase 3.**

```bash
python3 "$SCRIPTS/setup_venv.py" --project <root>     # ~11s, once
```

Do this as part of discovery, not when something breaks. It builds `.venv` from the project's
own pins, installs the generated models **editable** so later `up project build` runs need no
reinstall, and points VS Code at the interpreter.

**The main reason is the person reading along.** They have the project open while you work,
and without the venv every `from models.io...` and `from crossplane.function import ...` is
underlined on correct code, with no go-to-definition into the generated models and no
`forProvider` autocomplete. They cannot tell your errors from the environment's. Secondarily,
the **fast tier** in Phase 5 cannot run at all without the SDK this installs, so the two-tier
loop collapses to one and every iteration pays a full build.

None of it is needed to reach green — the function runs in a container — which is exactly why
it gets deferred and then never done. Run it now.

**Never hand-derive an import path and never guess a provider field name.** Both are the
single largest source of trial-and-error in this skill's history, and both are one command
away.

Legitimately worth asking, and only if `args` does not already say: optional/conditional
resources, whether connection details must reach the XR, and whether child XRs are composed.
If unstated, choose the simplest correct behaviour, say so in your summary, and continue.

## Phase 3: Design against what you discovered

See [knowledge.md](references/knowledge.md) for each design question in full. In brief:

1. **Layout** — match what the project already uses; never convert one to the other.
2. **Composition keys** — the names under which you store desired resources. They become
   `crossplane.io/composition-resource-name`, and Crossplane derives resource names from them.
3. **References before status plumbing.** If resource B needs an ARN or ID from resource A,
   a `*Ref` field makes the **provider** resolve it, so the composition stays single-pass and
   never reads A's status. Plumbing the value yourself forces a second reconcile and a
   readiness branch you then have to test.
4. **List fields.** *One element → one resource* is a decision you justify, not a default —
   `control-plane-project-charter` §6 (the provider schema is a lower bound).
5. **Conditional resources** — which use `ready OR exists`, and where each conditional
   belongs relative to the existing guard clauses (knowledge.md: the guard-clause chain).
6. **Flexible maps** — does the XRD use `additionalProperties` for tags and labels? Fixed
   `properties:` under a map produces null-value failures in typed languages, and it is what
   an XRD inferred from an example always contains.

## Phase 4: RED — write the failing test before the implementation

**Not optional, and it comes before any function code.**
`control-plane-project-charter` §3 (RED → GREEN → REFACTOR) owns the loop; this is the
composition author's half of it.

The design you just settled already fixes what the function must emit — the keys, the Kinds,
the fields. Write that as an assertion **now**, while it states intent, rather than
afterwards when it can only describe whatever the code produced.

1. Make sure the XRD and a composition exist so the test has something to point at. Write
   the XRD directly — `control-plane-project-charter` §5
   has the v2 skeleton — and scaffold the composition with `up composition generate`, which
   emits only an auto-ready step, so wire your function in with
   `up function generate <n> <composition-path>`. The function body stays empty or unchanged.
2. Author the test via **author-tests**, which reads the same
   `languages/` file you did.
3. **Run it and read the failure:**

   ```bash
   up test run "tests/<t>"      # expect FAIL
   ```

   Check the failure is RED for the right reason — the charter's table says which failures
   count. A broken test is not RED, and a test that passes before the code exists is vacuous.
4. **Keep the failure text.** It is what makes the coverage claim in your summary checkable.

Adding to a composition that already works has no natural RED. Write the new assertion, run
it, and confirm *it* fails while the others still pass.

## Phase 5: Implementation — make it GREEN

Implement until the test passes, and no further. Re-run `up test run "tests/<t>"` and report
the RED→GREEN transition, not merely the final green.

The language file has the bootstrap and the syntax. Language-independent, in order:

1. Parse the observed XR using the language's required bootstrap (Python needs
   `struct_to_dict`; skipping it fails *silently* on current Up CLI versions).
2. Create managed resources with **`forProvider` only** — no `providerConfigRef` (unless the
   right config is not `ClusterProviderConfig/default`), no `managementPolicies`, no
   `metadata.namespace` (`control-plane-project-charter` §5: Crossplane v2 fills in the rest).
3. Convert flexible maps to the language's plain map type before assigning them.
4. Extract connection details by **composition key**, not by resource name.
5. Mark any ProviderConfig ready **after** writing the resource, never before.
6. Give each optional resource its **own conditional block** rather than another early
   return — see the guard-clause chain in knowledge.md.

For iterating on a crash rather than an assertion, use the fast tier where the language
offers one (Python: `run_function.py`, well under a second against `up test run`'s tens of
seconds — it needs a venv with `crossplane-function-sdk-python`; run it once and it prints the
exact recipe). It asserts nothing, so it supplements the loop and never replaces it.

## Phase 6: REFACTOR and verify — coverage, not a green exit code

With the suite green, tidy the implementation, then add the next failing assertion and go
round again. Everything below is what "covered" has to mean before you write it down.
`control-plane-project-charter` §8 explains why each
green thing is not evidence; this is the checklist.

**1. Check provider validity, not just v2 conformance.** Namespaced APIs and
`forProvider`-only are *Crossplane* correctness — they say nothing about whether the
provider will accept the resource. Read the generated model's own constraints, then ask the
structural question the models cannot answer
(`control-plane-project-charter` §6: the provider schema is a lower bound, not the
constraint set).
Write the result in your summary: which Kinds you checked, what the schema required, and
which API-level rule you could not confirm.

This step gets skipped, and it is where the real bugs are. Two that shipped from one S3
lifecycle task, both with a fully green composition suite:

| Defect | Why nothing caught it |
|---|---|
| `rule.id` optional in the generated model but **required** by the AWS provider | the XRD left it optional, the render succeeded, AWS rejected the resource |
| a rule with neither `filter` nor `prefix` | S3 rejects it with `MalformedXML`; nothing emitted a fallback filter |

**2. Grep your own function** for `providerConfigRef`, `managementPolicies` and `namespace`
— the two greps in the charter's `charter/v2-resources.md` (§5) — and judge each hit rather
than counting them. Legitimate hits: a `namespace` on a Secret or ConfigMap you compose
yourself, and a `providerConfigRef` where the right config is not
`ClusterProviderConfig/default` — in which case `kind` must name an object that exists.

**3. The suite is not done until it satisfies all three rules:**

1. **One test per input shape**, including a **minimal XR that omits every optional
   field.** Use the inline `xr` field rather than `xrPath`, so no second example file is
   needed. This is where "the user wrote the obvious minimal manifest" bugs live.
2. **One test per observed-state branch.** Anything gated on observed resources or on
   readiness is dead with `observedResources=[]` — unexercised, not merely unasserted — and
   live as soon as a test supplies `observedResources`. Write that test rather than declaring
   the branch untestable; then say what it proves (your branch logic, given the status you
   wrote) and what it does not (that a provider reports that status).
3. **Every `status` field the function writes must be asserted on the composite.**
   `assertResources` matches the composite: include the XR with a `status` block. It is the
   only programmatic check on composition outputs.

**4. Read the render, not the assertions.**

```bash
up test run "tests/test-*" --function-logs
grep -h "composition-resource-name:" _output/composition_test/<ts>/<test>/render.log \
  | sort | uniq -c
```

That counts everything the function emitted, including what nothing asserts. Add each new
resource to `assertResources` — until you do it is untested even though the suite is green.

**5. What you may and may not claim.** Composition tests render and assert; they do not talk
to a provider and do not install anything.

| You may say | You may NOT say |
|---|---|
| "composition tests pass, N/N" | "production-ready" |
| "renders the resources I intended, with these fields" | "can be deployed to a control plane" |
| "provider constraints checked for Kinds X, Y" | "verified" / "working" — you ran no provider |

**Out of reach locally.** External-name semantics — whether a resource's external name is
provider-assigned or is the identifier you set — are undiscoverable from CRDs or generated
models, and `assertResources` is partial-positive so a *stray* annotation is never flagged.
That class only fails on a live control plane. Check it there, or say it is unchecked.

## Responding to the user

**When shown function code:**
1. Check the language's required bootstrap is present.
2. Check imports resolve against the probe or the generated schemas, and that every provider
   path is namespaced (`.m.`).
3. Flag any `providerConfigRef`, `managementPolicies`, or MR `metadata.namespace` as
   removable — and `providerConfigRef.kind: "ProviderConfig"` as an active bug.
4. Check flexible maps are converted to a plain map type.
5. Check the guard-clause order — does a return above the new resource gate it unintentionally?
6. Check ProviderConfig readiness is marked *after* the resource is written.

**When a test passes but the resource misbehaves on a control plane:**
1. Read `render.log` — the test may never have asserted it.
2. Look for a `providerConfigRef` the function should not be setting.
3. Check the guard-clause chain and readiness branches; neither is exercised locally.

Language-specific error messages — Pydantic validation, KCL type errors, TypeScript
compilation — are in the matching `languages/` file.

## Skill boundaries

| This skill | Elsewhere |
|---|---|
| Composition function structure, imports, patterns | Test authoring → `author-tests` |
| v2 managed-resource rules in code | XRD design and scaffolding → `author-configuration-package` |
| Provider-validity checks on emitted resources | Running the suite and deploying → `verify-configuration` |
| The RED/GREEN authoring loop | Live cloud runs → `e2e-test-configuration` |

## v2 migration

Migrating a function to v2 is its own piece of work (`plan-v2-migration`). The
language-independent checklist is in
[knowledge.md](references/knowledge.md#v2-migration-checklist).

## Success criteria

1. The function language was detected, not assumed, and the matching `languages/` file was read
2. Import paths resolved from the project, never derived by hand
3. Managed resources carry `forProvider` only, with no dangling `providerConfigRef`
4. A test was written first, run, and observed to fail for the right reason
5. The RED→GREEN transition is reported, with the failure text
6. `render.log` was read and every emitted resource is asserted
7. Provider-level constraints were checked, and the result — including "found nothing" —
   is in the summary
8. The summary claims the layer that was actually reached, and no further
