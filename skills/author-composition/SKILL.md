---
name: author-composition
description: Use this skill when the user asks to create, extend, modify, or debug a Crossplane composition function in a control-plane project — in any language (KCL, Python, TypeScript, Go). Detects the function language and applies the matching reference. Also use when asked about Crossplane v2 composition patterns, model/type import paths, namespaced `.m.` APIs, or why a composition renders green but the resource never reconciles. For authoring the tests themselves use author-tests; for XRD design use author-configuration-package. Always load this skill before writing or changing composition function code, instead of writing it directly - also when you get there partway through another skill's workflow, such as scaffolding a new package. It enforces the v2 rules that composition tests cannot catch — `forProvider`-only resources, no dangling `providerConfigRef`, resolved import paths — and the test-first loop that makes a coverage claim checkable.
license: Apache-2.0
references:
  - references/patterns.md
---

# Composition Authoring

Author and modify Crossplane composition functions, in any language `up function generate`
supports, test first.

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
   test's expected value.** See that test go red, then revert (the charter's `charter/tdd.md`).
5. **In a v2 project, managed resources carry `forProvider` only**, on the `.m.` API groups,
   unless the project's spec or API sets more: no `deletionPolicy`, `managementPolicies` or
   `metadata.namespace`; omit `providerConfigRef` if and only if
   `ClusterProviderConfig/default` exists and is the right one. A v1 project keeps its v1
   APIs: migrating it is separate work (§5).
6. **Name what ran and the command's own exit code.** After `| tail`, `$?` is `tail`'s: read
   `${PIPESTATUS[0]}`, or redirect to a file and then read `$?`. No command, no claim (§4).
7. **`No test files found` means nothing ran**, though `up test run` exits 0. A test program
   that prints `items: []` contributes zero tests (§8).
8. **For every test you added or changed, name the code change that turns it red**, and say
   whether you saw it fail. If you did not, call the test unproven (§4).
9. **Name the layer you reached** — render, composition test, local control plane, cloud — and
   never claim one you did not reach. Comments and docs claim no more than the test checks (§4).
10. **Re-read a document before you write from it.** Long runs lose old output: before you
    write a work item, a test expectation, a quote or a field value taken from a document,
    re-read the section you rely on in that step. Never quote from memory; if the re-read
    contradicts what you wrote, fix it first (charter §1).

## Mode, and the charter

**Interactive:** ask only what the project can't tell you. **Unattended:** never ask; decide from
the spec and state the assumption, or stop and report. Load `control-plane-project-charter`
before you start, or read its `SKILL.md` beside this skill's directory: this skill does not
load it.

A composition's *meaning* is language-agnostic; only its *syntax* differs. Read three layers:
the charter (the rules), [patterns.md](references/patterns.md) (what each pattern means), and
the charter's `languages/` file for your language (the syntax).

## Phase 1: Detect the language and the Crossplane generation — do not ask

**Language.** Detect the *function* language from `functions/` with the table in the charter's
`languages/README.md` (`control-plane-project-charter/references/languages/`, beside this
skill's directory), then read the file it names before writing a line: it carries the layout
detection, the import formula and the bootstrap, all wrong by default if you guess. The test
language is a separate choice (charter §10; `author-tests` applies it). No functions yet? Take
the language from `upbound.yaml`, else from an existing function anywhere in the project, else
ask — this is a decision, not a discoverable fact.

**Generation**, which governs more of the guidance than the language does:

```
apis/*/definition.yaml: apiextensions.crossplane.io/v2  → v2: binding rule 5 and charter §5 apply
                                                   /v1  → v1: they do not
```

A v1 project uses the non-`.m.` provider models and a cluster-scoped `ProviderConfig`. Every
`up project init` template is v1 today, so a freshly initialised project is v1 and its shipped
function breaks every v2 rule. Match what the project is (binding rule 5); migrating it is
`plan-v2-migration`'s work, not cleanup in passing. Python: `probe_project.py` reports the
generation on its first line and recommends imports accordingly.

## Phase 2: Discover — do not ask

`control-plane-project-charter` §2 has the general table. The composition-specific additions:

| What you need | How to get it — no question required |
|---|---|
| **Models missing entirely** (fresh clone) | `.up/` is gitignored and starts empty. Run `up dep update-cache`, then `up project build`; every model import fails until you do |
| Function layout + import prefix | the language file's detection recipe (Python: `probe_project.py`) |
| Exact import line and class names per Kind | the language file; Python: the same probe, with the Kinds named |
| Field names and types on a managed resource | the generated schema. Python: `probe_project.py --fields <Kind>` prints every `forProvider` field, flags list fields with misleadingly singular Upjet names (`attribute`, `globalSecondaryIndex`), and lists cross-resource `*Ref`/`*Selector` fields |
| Go: import path, types, fields | the generated types under `.up/go/models/` — `languages/go.md` (imports and models) |

**Python:** before Phase 3, read the charter's `languages/python.md` and run what it says —
the venv (`scripts/setup_venv.py`, once, right after the first build; why it comes first is in
that file), `scripts/probe_project.py` (layout, imports, fields) and `scripts/run_function.py`
(the fast tier), all in this skill's [`scripts/`](scripts/) directory. The other languages read
their generated types directly.

**Never hand-derive an import path and never guess a provider field name.** Both are one
command away.

Worth asking, and only if `args` does not already say: optional/conditional resources, whether
connection details must reach the XR, and whether child XRs are composed. If unstated, choose
the simplest correct behaviour, say so in your summary, and continue.

## Phase 3: Design against what you discovered

[patterns.md](references/patterns.md) has each design question in full. In brief:

1. **Layout** — match what the project already uses; never convert one to the other.
2. **Composition keys** — they become `crossplane.io/composition-resource-name`, and
   Crossplane derives resource names from them. A rename is a migration.
3. **References before status plumbing.** If resource B needs an ARN or ID from resource A,
   a `*Ref` field makes the provider resolve it, so the composition stays single-pass and
   never reads A's status.
4. **List fields.** *One element → one resource* is a decision you justify, not a default
   (charter §6).
5. **Conditional resources** — which use `ready OR exists`, and where each belongs relative to
   the existing guard clauses (patterns.md: the guard-clause chain).
6. **Flexible maps** — tags and labels need `additionalProperties` in the XRD; fixed
   `properties:` produce null-value failures in typed languages.

## Phase 4: RED — write the failing test before the implementation

Binding rule 3, before any function code; `control-plane-project-charter` §3 owns the loop.
The design you just settled fixes what the function must emit — keys, Kinds, fields. Write
that as an assertion now, while it states intent.

**Who does what in a run that changes the function.** `author-tests` writes the test (its
Phases 1–3, and Phase 5 for what no render reaches). This skill runs RED (step 3 below), GREEN
(Phase 5) and REFACTOR (Phase 6). The gate comes once, after this skill's Phase 6, as
`author-tests` Phase 6 describes. A run that only adds or changes tests stays in `author-tests`
throughout.

1. Make sure the XRD and a composition exist so the test has something to point at. Write the
   XRD yourself (`author-configuration-package`; the charter's `charter/v2-resources.md` has the v2 skeleton), scaffold the
   composition with `up composition generate`, which emits only an auto-ready step, and wire
   your function in with `up function generate <n> <composition-path>`. The function body
   stays empty or unchanged.
2. Author the test via `author-tests`, which reads the same `languages/` file you did.
3. **Run it and read the failure:** `up test run "tests/<t>"` — expect FAIL, for a reason the
   charter's §3 table counts as RED.
4. **Keep the failure text.** It is what makes the coverage claim in your summary checkable.

Adding to a composition that already works has no natural RED: write the new assertion, run
it, and confirm *it* fails while the others still pass.

## Phase 5: GREEN — implement until the test passes

Implement until the test passes, and no further. Re-run `up test run "tests/<t>"` and report
the RED→GREEN transition, not merely the final green.

The language file has the bootstrap and the syntax. Language-independent, in order:

1. Parse the observed XR with the language's required bootstrap (Python needs
   `struct_to_dict`; skipping it fails *silently* on current Up CLI versions. Go: the generated
   models are not `runtime.Object`s, so convert through JSON, in and out).
2. Create managed resources per binding rule 5.
3. Convert flexible maps to the language's plain map type before assigning them.
4. Extract connection details by **composition key**, not by resource name.
5. Mark a composed ProviderConfig — anything auto-ready cannot judge — ready explicitly.
6. Give each optional resource its **own conditional block** rather than another early
   return (patterns.md: the guard-clause chain).

For iterating on a crash rather than an assertion, use the fast tier where the language
offers one (Python: `run_function.py`; Go: `go test ./...` in `functions/<n>/` — the scaffold's
`fn_test.go` is an empty table that passes with zero cases, so add one before you count it).
It supplements the loop and never replaces it.

## Phase 6: REFACTOR and verify — coverage, not a green exit code

With the suite green, tidy the implementation, then add the next failing assertion and go
round again. This is what "covered" has to mean before you write it down (charter §8 explains
why each green thing is not evidence).

1. **Check provider validity, not just v2 conformance** (charter §6: the provider schema is a
   lower bound). Read the generated model's constraints, then ask the structural question the
   models cannot answer. Two defects that passed a green suite: `rule.id` optional in the
   model but required by the AWS provider, and an S3 lifecycle rule with neither `filter` nor
   `prefix`, rejected with `MalformedXML`. Write in your summary which Kinds you checked, what
   the schema required, and which API-level rule you could not confirm.
2. **Grep your own function** with the two greps in the charter's `charter/v2-resources.md`
   and judge each hit rather than counting them. Legitimate: a `namespace` chosen by a
   cluster-scoped XR or set on an object embedded inside `forProvider` (a provider-kubernetes
   `Object` manifest); a `providerConfigRef` where the right config is not
   `ClusterProviderConfig/default`, with a `kind` naming an object that exists; any field the
   project's spec or API sets. A `namespace` on a composed Secret or ConfigMap of a namespaced
   XR is not legitimate: Crossplane overwrites it.
3. **The suite satisfies the charter's `charter/evidence.md` "Coverage"**: one test per input shape,
   including a minimal XR via inline `xr`; one test per observed-state branch, saying what it
   proves (your branch logic, given the status you wrote) and what it does not (that a provider
   reports that status); every `status` field the function writes asserted on the composite.
4. **Read the render, not the assertions:** `up test run "tests/test-*" --function-logs`, then
   read it as `charter/evidence.md` says (the directory the run prints). Add each emitted
   resource to `assertResources`; until you do it is untested, though the suite is green.
5. **Claim only what ran** (binding rule 9). Composition tests render and assert; they talk
   to no provider and install nothing.

   | You may say | You may not say |
   |---|---|
   | "composition tests pass, N/N" | "production-ready" |
   | "renders the resources I intended, with these fields" | "can be deployed to a control plane" |
   | "provider constraints checked for Kinds X, Y" | "verified" / "working" — you ran no provider |

   **Out of reach locally:** external-name semantics — whether a resource's external name is
   provider-assigned or the identifier you set — are undiscoverable from CRDs or models, and
   `assertResources` is partial-positive, so a stray annotation is never flagged. Check it on
   a live control plane, or say it is unchecked.

## Boundaries

- **Reviewing function code, or a test passes but the resource misbehaves on a control
  plane:** the checklists in
  [patterns.md](references/patterns.md#reviewing-function-code-and-a-green-test-with-a-misbehaving-resource).
- Tests → `author-tests`; XRD design and scaffolding → `author-configuration-package`; the
  gate and deploying → `verify-configuration`; live cloud runs → `e2e-test-configuration`;
  migrating a function to v2 → `plan-v2-migration` (the function-side points:
  [patterns.md](references/patterns.md#migrating-a-function-to-v2)).

## Success criteria

Checks for you before you report, not a report format (`control-plane-project-charter` §4).

1. The function language and generation were detected, not assumed, and the matching
   `languages/` file was read
2. Import paths resolved from the project, never derived by hand
3. Managed resources follow binding rule 5, with no dangling `providerConfigRef`
4. A test was written first, run, and observed to fail for the right reason
5. The RED→GREEN transition is reported, with the failure text
6. The render was read and every emitted resource is asserted
7. Provider-level constraints were checked, and the result — including "found nothing" —
   is in the summary
8. The summary claims the layer that was actually reached, and no further

## References

- [patterns.md](references/patterns.md) — read in Phase 3 for each design question, when
  reviewing function code or debugging a green test whose resource misbehaves, and when
  migrating a function to v2.
- [`scripts/`](scripts/) — Python only; read the charter's `languages/python.md` before running
  them.
- The language files — the charter's, indexed by its `languages/README.md`; read the one
  Phase 1 names before writing code.
