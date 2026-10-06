---
name: author-tests
description: Use this skill when user requests to implement a feature, write, create, author, modify, refactor or plan refactoring of Crossplane configuration tests (composition tests or E2E tests) in a control-plane project - in any language (KCL, Python, YAML, Go, go-templating). Use this rather than a generic planning mode when the user asks for a plan to refactor composition tests or e2e tests in a crossplane configuration package. Specialized skill focused only on test authoring and modification (not running tests). Detects the test language and applies the right templates and patterns. Always load this skill before writing or changing composition or E2E test files, instead of writing them directly - also when you get there partway through another skill's workflow, such as scaffolding a new package. Covers writing an E2ETest - defaultConditions, extraResources, E2E credentials (static Secret or web identity) and what an E2ETest can assert.
license: Apache-2.0
references:
  - references/test-model.md
  - references/e2e.md
  - references/refactoring.md
---

# Crossplane Test Authoring

Author and modify Crossplane configuration tests, in any language `up test generate` supports,
and write the assertion that has to fail first.

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

A test's *meaning* is language-agnostic; only its *syntax* differs. Every test, in any
language, compiles to a `CompositionTest` or an `E2ETest` (`meta.dev.upbound.io/v1alpha1`):
the rules are in this file, the object model and common mistakes in
[test-model.md](references/test-model.md), the syntax in the charter's file for the test
language (Phase 1).

## Phase 1: Detect the test language — do this first

**Existing tests decide; otherwise the composition language; otherwise YAML** — the rule is
charter §10, its reasons the charter's `languages/README.md`. Only a test dir that produces a
`CompositionTest` or `E2ETest` counts as an existing test: a Go program printing `items: []` or
a linter over repo files does not set the language. A project may already mix languages
(Python functions with YAML tests), and new tests match what is in `tests/`. Functions in more
than one language and no tests yet: ask the user.

Detect with the table in the charter's `languages/README.md`
(`control-plane-project-charter/references/languages/`, beside this skill's directory), then
read the file it names before writing a test: each carries its templates and its silent
failure modes (Go: an empty `items` list passes; go-templating: a misspelt key renders
`<no value>`).

## Phase 2: Decide what to test, and scaffold

1. **New test:** determine the feature, resources and variants from `args` and the project
   (`apis/*/definition.yaml`, `apis/*/composition.yaml`, the function source, the example XRs
   in `examples/*/*.yaml`) — do not ask. **Modifying a test:** read it, match its language and
   style, and understand its current assertions before you change them.
2. **Scaffold with `up test generate <name> [--e2e] --language <lang>`** (`kcl`, `python`,
   `yaml`, `go`, `go-templating`); never create a test directory by hand. Then write the test
   from the template in the language file. Python: run `setup_venv.py` again after generating
   each test directory (the charter's `languages/python.md`).
3. **Organise:**

   | Type | Dir prefix | Timeout | `validate` | Purpose |
   |---|---|---|---|---|
   | Composition | `test-` | ≥60s | `false` (scaffold default) | local render, no cloud |
   | E2E | `e2etest-` | sized to what you provision ([e2e.md](references/e2e.md)) | n/a | real cloud lifecycle |

   Consolidate in one directory: the same resource type in different configs, feature on/off
   variants, 3–5 related scenarios. Separate directories: different resource types, complex
   sequential dependencies, and every E2E test. `up test run` runs every matched dir's program,
   so the composition gate is `up test run "tests/test-*"` (charter §7).

## Phase 3: Write the assertion that has to fail

Four things make an assertion bite:

| | |
|---|---|
| **Assert the field, not the existence.** | `assertResources` is partial and positive. An entry naming only `kind` passes against any resource of that kind, whatever it contains. Name the field you are adding. |
| **Assert on the composite too.** | Every `status` field the function writes needs an assertion on the XR itself. It is the only programmatic check on composition outputs. |
| **Cover the minimal XR.** | Use the inline `xr` field with every optional property omitted. That is the shape a real user writes first, and the one the scaffold never generates. |
| **Use distinguishing inputs.** | Every parameter the function passes through (region, config names, CIDRs, the XR's own name, …) gets a non-default value, unique across fields, in at least one test; a required field with no default needs two tests with different values. An input equal to the default or to a sibling field can't tell pass-through from a hard-coded constant. Backfill check: the charter's `charter/tdd.md`. |

- **Define the XR inline** where the format supports it, with `namespace: default` (v2).
- **Assert list membership on the parsed list**, not by substring matching on a joined string:
  a short token matches inside a longer one (`rt` inside `rta-…`).
- **Composed-resource names:** never guess one; the naming rule is in the charter's
  `charter/evidence.md` ([test-model.md, mistake 1](references/test-model.md#1-guessed-composed-resource-names)).
- **Managed resources in a test follow binding rule 5**, written as the import path in KCL,
  Python and Go and as the `apiVersion` string in YAML. Assert `providerConfigRef` and
  `managementPolicies` only where the project's spec or API sets them (whether a render keeps
  a value equal to the model default depends on the language and SDK; see the language file).

### Asserting absence

`assertResources` cannot assert that something is absent — it has no absence operator, so do
not search the CLI for one.

| Must be absent | How |
|---|---|
| A composed **resource** | Assert the composite's `spec.crossplane.resourceRefs` as the exact list from the render. Lists match exactly, so a surplus resource fails it. The templates in the charter's `languages/go/tests.md` and `languages/go-templating.md` show this guard; detail in its `charter/evidence.md` |
| A **field** | Not expressible in a composition test. Use a unit test on the function's desired state, in the function's own language (Go: `go test ./...` in `functions/<n>/`), or confirm it once in the render and report it as not asserted |

### Asserting a requirement on every resource

When a requirement applies to *every* composed resource (a label, a policy, a config ref, a
region), assert it in one test that ranges over all desired resources, not in per-resource
expectations: those inherit each row's omissions, so a resource that misses it stays green.
The tier that can range is a function unit test over the desired state (Go sketch: the
charter's `languages/go/functions.md`, unit-test template). A CompositionTest cannot iterate
over the render; it fits only when one helper adds the requirement to every expectation and
there is one expectation per entry of the exact `resourceRefs` list.

### E2E tests

**Read [e2e.md](references/e2e.md) before writing or changing any `E2ETest`** — fields and
defaults, credentials per target, the ProviderConfig the test creates, a Go template, and what
counts as an e2e RED.

- `defaultConditions` lists condition types (`Ready`), never expressions or status paths.
- An `E2ETest` cannot assert a live status value. A requirement for one is not covered by e2e:
  say so and name the substitute evidence (an `observedResources` CompositionTest, a unit test,
  a read-back during the run; [e2e.md](references/e2e.md#status-values-cannot-be-asserted)).
  Do not search the `up` binary or the web for another mechanism: e2e.md says what exists.
- Set `timeoutSeconds` explicitly, sized to what you provision. Credentials depend on the
  target: `source: Upbound` works only on a Spaces control plane.
- `extraResources` creates the ProviderConfig: by default a `ClusterProviderConfig` named
  `default`, with no namespace ([e2e.md](references/e2e.md#the-providerconfig-the-test-creates)).
- **Never put long-lived credentials in a test** — use web identity, or a Secret filled from a
  `UP_*` variable — and **never set `skipDelete: true`**: it leaves real cloud resources
  running.

## Phase 4: Run it — RED, then GREEN

`control-plane-project-charter` §3 owns the loop (RED → GREEN → REFACTOR), including which
failures count as RED and deliberate mutation for backfill. This skill writes the assertion
that has to fail. In a run that also changes the function, `author-composition` Phase 4 says
which skill runs RED, GREEN and the gate; only when you add or change tests alone are this
phase and Phase 6 the whole loop.

Run the test directly — `up test run "tests/<t>"` — not through `verify-configuration`, which
builds the package and runs the whole suite and is not an inner loop. `No test files found`
means nothing ran (binding rule 7).

## Phase 5: Checking what is not a render

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
- **A check is coverage only if it is committed** — under `tests/`, or in the gate script —
  and run by the gate. A scratch check in `/tmp` is not.
- **Never turn a test program into a linter.** A test dir that checks repo files, exits
  non-zero on a mismatch and prints `items: []` adds zero tests. Passing, it drops out of the
  count (alone: `No test files found`, exit 0); failing, it stops at `✗ Parsing tests`, which
  is a broken test, not RED.
- **What no check here reaches** — XRD `required` lists, enums and scope; the dependency set —
  stays uncovered unless the project's gate checks it (charter §4: say what you did not
  verify).

## Phase 6: The gate, after the loop

Once the suite is green:

- **The project defines its own gate** (a script or make target): run that, not
  `verify-configuration` (charter §2: the project's own decisions win).
- **Otherwise** hand off to `verify-configuration` for the build and the whole suite.
- **No control plane or deploy allowed** (the project, the user or your instructions say so):
  the gate is the build and the whole `up test run` — `verify-configuration` Phases 1–2, or
  the project's gate — and nothing after it: no E2E, no `up project run` (binding rule 2).
  Where only Upbound Cloud is ruled out, `verify-configuration`'s "Local-only projects and
  projects with their own gate" says what changes.

## Boundaries

- Planning or executing a test refactor: [refactoring.md](references/refactoring.md) (plan into
  `.agents/tasks/REFACTOR_TESTS.md` without executing, then one item per run).
- Not here: building the package or running the whole suite as a gate, except Phase 6
  (`verify-configuration`); running E2E tests (`e2e-test-configuration`); implementing
  composition features (`author-composition`).

## Success criteria

Checks for you before you report, not a report format (charter §4: report what ran). Test
authoring is complete when:

- The test language was detected or chosen, and the scaffold generated (or the existing test
  read)
- The test follows this file, test-model.md and the matching language file
- The fields that matter are asserted, not just existence
- The new assertion was observed to fail before the implementation existed, and to pass after
- The gate passed once the suite was green — the project's own gate if it has one, else
  `verify-configuration`, without a deploy where none is allowed (Phase 6)

## References

- [test-model.md](references/test-model.md) — read for the `CompositionTest` fields, the
  structuring patterns (bundle, matrix, `observedResources` sequences) and the common
  mistakes, before writing your first test in a project.
- [e2e.md](references/e2e.md) — read before writing or changing any `E2ETest`: fields,
  `defaultConditions`, status, credentials per target, the ProviderConfig, Go template, e2e RED.
- [refactoring.md](references/refactoring.md) — read before planning or executing a test
  refactor.
- The language files — the charter's, indexed by its `languages/README.md`; read the one
  Phase 1 names before writing a test (`kcl.md`, `python.md`, `yaml.md`, `go/tests.md` with
  unit tests in `go/functions.md`, `go-templating.md`).
