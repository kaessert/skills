---
name: author-tests
description: Use this skill when user requests to implement a feature, write, create, author, modify, refactor or plan refactoring of Crossplane configuration tests (composition tests or E2E tests) in a control-plane project - in any language (KCL, Python, YAML, Go, go-templating). Use this rather than a generic planning mode when the user asks for a plan to refactor composition tests or e2e tests in a crossplane configuration package. Specialized skill focused only on test authoring and modification (not running tests). Detects the test language and applies the right templates and patterns. Always load this skill before writing or changing composition or E2E test files, instead of writing them directly - also when you get there partway through another skill's workflow, such as scaffolding a new package. Covers writing an E2ETest - defaultConditions, extraResources, E2E credentials (static Secret or web identity) and what an E2ETest can assert.
license: Apache-2.0
references:
  - references/knowledge.md
  - references/e2e.md
---

# Crossplane Test Authoring Assistant

Author and modify Crossplane configuration tests, in any language `up test generate` supports.

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
5. **Managed resources carry `forProvider` only**, on the `.m.` API groups, unless the
   project's spec or API sets more: no `deletionPolicy`, `managementPolicies` or
   `metadata.namespace`; omit `providerConfigRef` if and only if
   `ClusterProviderConfig/default` exists and is the right one (§5).
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

## Core Principle

**A test's *meaning* is language-agnostic; only its *syntax* differs.**

Every composition and E2E test - whether written in KCL, Python, YAML, Go, or go-templating - compiles to the same two Kubernetes objects: `CompositionTest` and `E2ETest` (`meta.dev.upbound.io/v1alpha1`). The fields, the concepts, the critical rules, and the common mistakes are identical across languages. The only thing that changes is how you express those objects: KCL models, Python Pydantic builders, raw YAML manifests, or Go.

So this skill has two layers:
- **Language-agnostic core** (this file + [knowledge.md](references/knowledge.md)): the object model, rules, patterns, and mistakes. Read these regardless of language.
- **Per-language reference** (kcl.md (`control-plane-project-charter` `languages/kcl.md`), python.md (`control-plane-project-charter` `languages/python.md`), yaml.md (`control-plane-project-charter` `languages/yaml.md`), go/tests.md (`control-plane-project-charter` `languages/go/tests.md`)): syntax, scaffolding, templates, and language-specific mistakes.

## Scope

**This skill DOES:**
- Create/modify composition tests and E2E tests in any supported language
- Plan test refactoring (creates `.agents/tasks/REFACTOR_TESTS.md`)
- Execute refactoring (one priority item at a time)
- Generate scaffolds with `up test generate`
- **Run the test you just wrote** — `up test run "tests/<t>"`, directly, as the RED/GREEN loop requires

**This skill does NOT:**
- Build the package, or run the whole suite as a gate (the project's own gate, else `verify-configuration` — but *after* the loop below, never inside it)
- Execute E2E tests (use `e2e-test-configuration`)
- Implement composition features (use `author-composition`)

## The TDD loop — this skill owns the RED step

The canonical loop lives in
`control-plane-project-charter` §3 (RED → GREEN → REFACTOR): write the
test, run it, read the failure, then implement. It is not repeated here — read it, including
the table of which failures count as RED and the deliberate-mutation technique for backfill.

**What is specific to this skill** is that you are the one writing the assertion that has to
fail. Four things make that assertion bite:

| | |
|---|---|
| **Assert the field, not the existence.** | `assertResources` is partial and positive. An entry naming only `kind` passes against any resource of that kind, whatever it contains. Name the field you are adding. |
| **Assert on the composite too.** | Every `status` field the function writes needs an assertion on the XR itself. It is the only programmatic check on composition outputs. |
| **Cover the minimal XR.** | Use the inline `xr` field with every optional property omitted. That is the shape a real user writes first, and the one the scaffold never generates. |
| **Use distinguishing inputs.** | Every parameter the function passes through (region, config names, CIDRs, the XR's own name, …) gets a non-default value, unique across fields, in at least one test; a required field with no default needs two tests with different values. An input equal to the default or to a sibling field can't tell pass-through from a hard-coded constant. Backfill check: charter `tdd.md`. |

Run it directly — `up test run "tests/<t>"` — not through `verify-configuration`, which builds
the package and runs the whole suite, and is not an inner loop. If it prints
`No test files found`, **nothing ran**: it exits 0, and that is not a pass.

### Asserting absence

`assertResources` cannot assert that something is absent — it has no absence operator, so do
not search the CLI for one.

| Must be absent | How |
|---|---|
| A composed **resource** | Assert the composite's `spec.crossplane.resourceRefs` as the exact list from `render.log`. Lists match exactly, so a surplus resource fails it. The templates in the charter's `languages/go/tests.md` and `languages/go-templating.md` show this guard; detail in its `charter/evidence.md` |
| A **field** | Not expressible in a composition test. Use a unit test on the function's desired state, in the function's own language (Go: `go test ./...` in `functions/<n>/`), or confirm it once in `render.log` and report it as not asserted |

### Asserting a requirement on every resource

When a requirement applies to *every* composed resource (a label, a policy, a config ref, a
region), assert it in one test that ranges over all desired resources, not in per-resource
expectations: those inherit each row's omissions, so a resource that misses it stays green.
The tier that can range is a function unit test over the desired state (Go sketch: the
charter's `languages/go/functions.md`, unit-test template). A CompositionTest cannot iterate
over the render; it fits only when one helper adds the requirement to every expectation and
there is one expectation per entry of the exact `resourceRefs` list.

## Checking what is not a render

`up test run` evaluates `CompositionTest` and `E2ETest` objects and nothing else. For a
requirement on a file — dependencies in `upbound.yaml`, a frozen XRD surface, `examples/`, a
`ManagedResourceActivationPolicy` — sort it:

- **What a render reaches, cover with a render.** XRD defaults reach the render through
  `xrdPath` (charter §2), so assert the defaulted values on the composite. Render a shipped
  example with `xrPath: examples/<kind>/<file>.yaml` plus `xrdPath`: that proves the function
  handles it, not that the API server accepts it. A pipeline function missing from `dependsOn`
  already fails every render (`unknown function`).
- **The rest is outside this suite.** `up project build` does not validate `examples/`, and it
  accepted an MRAP without its API dependency (up v0.55.0).
  `<author-configuration-package>/scripts/check_xrd_schema.py` checks XRD design, not a frozen
  surface; `<author-configuration-package>` is the directory containing that skill's SKILL.md,
  beside this skill's directory. Where the project has a gate script, such checks belong there,
  beside the build and the test run (charter §2: the project's gate wins; `verify-configuration`).
- **Never turn a test program into a linter.** A test dir that checks repo files, exits
  non-zero on a mismatch and prints `items: []` adds zero tests. Passing, it drops out of the
  count (alone: `No test files found`, exit 0); failing, it stops at `✗ Parsing tests`, which
  is a broken test, not RED.
- **The report lists what nothing covers.** A required line, not optional prose: by spec
  clause, each requirement no automated check covers (e.g. XRD `required` lists, enums,
  scope; the dependency set), and whether it was checked by hand or not at all.

## Step 1: Detect the Test Language (do this first)

**Existing tests decide; otherwise the composition language does.** Only a test dir that produces a `CompositionTest` or `E2ETest` counts as an existing test. Detect the *test* language from the `tests/` directory first — a project may already mix languages (`configuration-aws-ctp` is Python functions with YAML tests), and new tests match what is there. With no tests yet, write them in the composition language whenever `up` supports it as a test language, and fall back to YAML only when it does not. The full rule and its reasons: `control-plane-project-charter` §10.

The files named below are in the charter's `languages/` directory
(`control-plane-project-charter/references/languages/`, beside this skill's directory).

```
Inspect tests/ (skip empty projects) - new tests match the language found:
  tests/*/**.k                         → KCL           → kcl.md
  tests/*/test/__main__.py, main.py    → Python        → python.md
  tests/*/*.yaml, no other test source → YAML          → yaml.md
  tests/*/go.mod + main.go             → Go            → go/tests.md
  tests/*/*.gotmpl (every file)        → go-templating → go-templating.md

  A dir that emits no CompositionTest/E2ETest (a Go program printing `items: []`,
  a linter over repo files) is not a test: skip it, it does not set the language.

No such test yet? Pick the language:
  1. The composition language - every language `up function generate` produces is a
     test language too:
       functions/**/*.k        → kcl
       functions/*/main.py | */function/fn.py → python
       functions/*/*.go        → go
       functions/*/*.gotmpl    → go-templating
  2. Else YAML: TypeScript functions (no CLI test language), or no embedded function at all
  3. Functions in more than one language: ask the user
```

Scaffold in the chosen language:

| Language | Composition test | E2E test |
|----------|------------------|----------|
| KCL | `up test generate <name> --language kcl` | `up test generate <name> --e2e --language kcl` |
| Python | `up test generate <name> --language python` | `up test generate <name> --e2e --language python` |
| YAML | `up test generate <name> --language yaml` | `up test generate <name> --e2e --language yaml` |
| Go | `up test generate <name> --language go` | `up test generate <name> --e2e --language go` |
| go-templating | `up test generate <name> --language go-templating` | `up test generate <name> --e2e --language go-templating` |

> **Python tests: set up the venv before you write one.** `up test generate --language python`
> creates a `pyproject.toml` in the new test directory; installing it is what makes
> `from models.io...` resolve for the person reading along in an editor, and it is a
> prerequisite for the fast tier. One command, ~11s, after `up project build`:
>
> ```bash
> python3 <author-composition>/scripts/setup_venv.py --project <root>
> ```
>
> `<author-composition>` is the directory containing that skill's SKILL.md, beside this skill's
> directory.
>
> It installs every function *and* test directory from the project's own pins, so run it again
> after generating a new test directory. Details in
> `languages/python.md` (`control-plane-project-charter` `languages/python.md`).

> **New projects:** `up project init` takes `--test-language` **separately** from `--language` (functions). Pass the same value to both (`--language go --test-language go`). It does not accept `yaml`; YAML tests are scaffolded per test with `up test generate --language yaml`.

> **Go / go-templating:** same object model and rules as every other language. Read the verified templates and the reproduced failure modes before writing one: `languages/go/tests.md` (Go programs that print the tests; commit `go.mod`/`go.sum`; an empty `items` list passes silently) and `languages/go-templating.md` (a misspelt key renders `<no value>` silently; every file in the test dir must be a template) in `control-plane-project-charter`.

## Decision Tree

```
User Request → What action?

CREATE NEW TEST:
  → Detect/choose language (Step 1)
  → Which type?
    → Composition (fast, no cloud): up test generate <feature> --language <lang>
    → E2E (real resources):        up test generate <feature> --e2e --language <lang>
  → Fill in logic using the matching per-language reference

MODIFY EXISTING TEST:
  → Read test first, match its language and style, then apply changes

PLAN REFACTORING:
  → Create .agents/tasks/REFACTOR_TESTS.md with prioritized items
  → DO NOT execute, just plan

EXECUTE REFACTORING:
  → Check for plan file first
  → Execute ONE item at a time
  → Run tests after each item
```

## Quick Reference

| Type | Timeout | Validate | Dir prefix | Purpose |
|------|---------|----------|------------|---------|
| Composition | ≥60s | `false` (scaffold/lab default) | `test-` | Local render validation, no cloud |
| E2E | sized to resources (see below) | n/a | `e2etest-` | Real cloud lifecycle |

**E2E tests: read [e2e.md](references/e2e.md) before writing or changing any `E2ETest`** — fields and
defaults, credentials per target, a Go template, and what counts as an e2e RED.
- **`defaultConditions` lists condition types (`Ready`), never expressions or status paths.**
- **An `E2ETest` cannot assert a status value.** Prove it with an `observedResources`
  CompositionTest plus a unit test, and report the e2e layer as "Ready only". Never search the
  `up` binary or the web for another mechanism: e2e.md says what exists.
- **Set `timeoutSeconds` explicitly**, sized to what you provision. Credentials depend on the
  target: `source: Upbound` works only on a Spaces control plane.

**CRITICAL**: always use the `.m.` API groups in tests. The `.m.` marks the **modern** (Crossplane v2) API group — not "naMespaced" and not "monolithic". It holds the namespaced managed resources *and* the cluster-scoped `ClusterProviderConfig` they default to, which is why "m = namespaced" cannot be right. See `control-plane-project-charter` §5 (what a v2 composed resource needs). How the `.m.` is written differs per language — the import path in KCL, Python and Go, the `apiVersion` string in YAML; see the per-language reference.

**Omit `providerConfigRef` if and only if `ClusterProviderConfig/default` exists and is the
right one** — the API server defaults an omitted one to
`{kind: ClusterProviderConfig, name: default}`, the object the templates and generated E2E
tests create. These are defaults the project may override (`control-plane-project-charter` §5):
when its spec or API sets `providerConfigRef` or `managementPolicies`, assert them as
specified (whether a render keeps a value equal to the model default depends on the language
and SDK; see the language file).
`kind: ProviderConfig` is a bug only when no namespaced `ProviderConfig` of that
name exists in, or is created in, the XR's namespace — the resource then stays inert on a
control plane while the tests pass.

So in a test's `extraResources`, create a **`ClusterProviderConfig`** (cluster-scoped, no
namespace) by default. When the project uses namespaced credentials, create the namespaced
`ProviderConfig` the function references instead, in the XR's namespace (`namespace: default`).
The training labs use `ClusterProviderConfig`; see
[knowledge.md](references/knowledge.md#two-providerconfig-kinds-v2).

## Critical Rules (all languages)

### MUST DO:
1. **Always scaffold with `up test generate`** - never create test directories manually
2. **Define the XR inline** where the format supports it (composition tests) - keeps tests self-contained
3. **Assert ALL critical fields** - not just resource existence
4. **Match exact composed-resource names** - find them with `up composition render`
5. **`namespace: default` on the XR** (v2). On the provider config only if the project actually uses the namespaced `ProviderConfig` kind — the default and the usual case is `ClusterProviderConfig`, which is cluster-scoped and takes no namespace
6. **Run the test directly while authoring** (`up test run "tests/<t>"`); run the gate once the suite is green (Workflow Summary)

### NEVER DO:
1. Hardcoded long-lived credentials in E2E tests (use web/injected identity, or a Secret sourced from a `UP_*` env var)
2. `skipDelete: true` in E2E tests (always clean up)
3. `timeoutSeconds < 60` for composition tests
4. Under-sized or unset E2E timeouts (sizing: [e2e.md](references/e2e.md))
5. Assert resource existence only, with no field assertions

## Test Organization

**CONSOLIDATE (same directory) when:**
- Same resource type, different configs
- Feature enabled/disabled variants
- 3-5 related scenarios

**SEPARATE directory when:**
- Different resource types
- E2E tests (always separate, `e2etest-` prefix). `up test run` runs every matched dir's program even without
  `--e2e`, so the composition gate is `up test run "tests/test-*"`; write it in the project README (charter §7)
- Complex sequential dependencies

## Phase 0: You run inline, and you are bound by the charter

This skill runs inline — you expand into the caller's conversation, share their
working directory, and can ask. `control-plane-project-charter` §1 (when nobody can answer,
never block) says what that means for asking questions, and §4 (report the effect, not the
intent) what it means for your summary. Both apply in full; only the binding rules above
repeat them.

**Load the charter before you start — this skill does not load it for you.** Load the
`control-plane-project-charter` skill, or read its `SKILL.md`, which sits beside this skill's
directory. It also carries the TDD loop (§3), what a v2 composed resource needs (§5), the
container boundary (§7), and what a green run does and does not prove (§8).

## Workflow Summary

### New Test
1. Detect/choose test language (Step 1)
2. Determine feature/resources/variants from `args` and the project (`apis/*/definition.yaml`,
   `apis/*/composition.yaml`, the function source, `examples/*/example.yaml`) — do not ask;
   see Phase 0
3. Generate scaffold: `up test generate <feature> --language <lang>` (add `--e2e` for E2E)
4. Write test using the template from the matching per-language reference
5. **Run the gate once the suite is green** — see [The gate](#the-gate-after-the-loop)

### Modify Test
1. Read existing test; match its language and style
2. Understand current assertions
3. Apply changes
4. **Run the gate once the suite is green** — see [The gate](#the-gate-after-the-loop)

### The gate, after the loop

- **The project defines its own gate** (a script or make target): run that, not
  `verify-configuration` (charter §2: the project's own decisions win).
- **Otherwise** hand off to `verify-configuration` for the build and the whole suite.
- **No control plane or deploy allowed** (the project, the user or your instructions say so):
  the gate is the build and the whole `up test run` — `verify-configuration` Phases 1–2, or
  the project's gate — and nothing after it: no E2E, no `up project run` (charter §9: no
  infrastructure as a side effect). Where only Upbound Cloud is ruled out,
  `verify-configuration`'s "Local-only projects and projects with their own gate" says what
  changes.

### Refactoring

Planning or executing a test refactor: follow
[knowledge.md](references/knowledge.md#refactoring-workflow) — plan into
`.agents/tasks/REFACTOR_TESTS.md` without executing, then execute one item at a time.

## References

- [knowledge.md](references/knowledge.md) - language-agnostic object model, patterns, common mistakes, refactoring template
- [e2e.md](references/e2e.md) - read before writing or changing any `E2ETest`: fields, `defaultConditions`, status, credentials per target, Go template, e2e RED
- kcl.md (`control-plane-project-charter` `languages/kcl.md`) - KCL syntax, imports, templates (composition + E2E for AWS/Azure/GCP)
- python.md (`control-plane-project-charter` `languages/python.md`) - Python SDK test layout, Pydantic dump modes, templates
- yaml.md (`control-plane-project-charter` `languages/yaml.md`) - raw YAML tests, real-world examples
- go/tests.md (`control-plane-project-charter` `languages/go/tests.md`) - Go test layout, composition-test template, failure modes (unit tests: `languages/go/functions.md`)
- go-templating.md (`control-plane-project-charter` `languages/go-templating.md`) - `*.gotmpl` tests

## Success Criteria

Checks for you before you report, not a report format (charter §4: report what ran). Test
authoring is complete when:
- Test language detected/chosen and scaffold generated (or existing test read)
- Test content follows the agnostic rules + the matching per-language reference
- All critical fields asserted (not just existence)
- The new assertion was observed to FAIL before the implementation existed, and to pass after
- The report lists, by spec clause, each requirement no automated check covers
- The gate passed once the suite was green — the project's own gate if it has one, else
  `verify-configuration`, without a deploy where none is allowed (see The gate, after the loop)
