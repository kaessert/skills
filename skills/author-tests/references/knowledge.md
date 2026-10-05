# Test Authoring Knowledge Base (language-agnostic)

The object model, patterns, and mistakes that apply to Crossplane configuration tests **regardless of language**. For syntax, see the per-language references: kcl.md (`control-plane-project-charter` `languages/kcl.md`), python.md (`control-plane-project-charter` `languages/python.md`), yaml.md (`control-plane-project-charter` `languages/yaml.md`).

## Table of Contents

- [The Test Object Model](#the-test-object-model)
- [Provider API Versions](#provider-api-versions)
- [Patterns](#patterns)
  - [Resource-Focused Bundle](#resource-focused-bundle)
  - [Parameterized Test Matrix](#parameterized-test-matrix)
  - [Sequential Testing with observedResources](#sequential-testing-with-observedresources)
- [Common Mistakes](#common-mistakes)
- [Refactoring workflow](#refactoring-workflow)
- [Refactoring Plan Template](#refactoring-plan-template)

---

## The Test Object Model

Every test - in any language - produces one of two objects under `apiVersion: meta.dev.upbound.io/v1alpha1`. KCL/Python builders and raw YAML all render to exactly this shape.

### CompositionTest (fast, local, no cloud)

| Field | Meaning |
|-------|---------|
| `metadata.name` | Test name (unique within its directory) |
| `spec.compositionPath` | Path to the composition under test (e.g. `apis/<xr>/composition.yaml`) |
| `spec.xrdPath` | Path to the XRD (`apis/<xr>/definition.yaml`) |
| `spec.xr` | The XR under test, defined **inline** (recommended). Some layouts use `xrPath` instead |
| `spec.validate` | Keep `false` - the scaffold default, and what the training labs use. (Set on every generated test; leave it `false`.) |
| `spec.timeoutSeconds` | **≥60** |
| `spec.assertResources` | Expected rendered resources. Assert **all critical fields**, not just names. Matches the **composite** as well as composed resources - include the XR with a `status` block to assert composition outputs (see knowledge pitfall 9) |
| `spec.observedResources` | Optional. Pre-existing resources (with mocked `status`) fed into the render - used to test dependency ordering and status-driven branches |

### E2ETest (real cloud lifecycle)

Field table, defaults, what `defaultConditions` accepts and what an `E2ETest` cannot assert: [e2e.md](e2e.md).

---

## Provider API Versions

**ALL Upbound providers expose BOTH API surfaces:**

| API Type | Format | Use in tests |
|----------|--------|--------------|
| **Namespaced** | `aws.m.upbound.io/v1beta1` | Always |
| Cluster-scoped | `aws.upbound.io/v1beta1` | Never |

What the `.m.` groups are: `control-plane-project-charter` §5. How the `.m.` is expressed depends on language (import path for KCL, Python and Go, `apiVersion` string for YAML) — see the per-language references.

### Provider credentials (E2E `extraResources`)

Which credential source works on which target (web identity only on a Spaces control plane, a static
`source: Secret` with `secretRef` on a local one), the AWS credentials-file format and the `UP_*` variable:
[e2e.md](e2e.md#credentials-depend-on-the-target).

### Two ProviderConfig kinds (v2)

v2 has two provider-config kinds:

| Kind | Scope | `namespace`? |
|------|-------|--------------|
| `ClusterProviderConfig` | Cluster-scoped | **none** (omit it) |
| `ProviderConfig` | Namespaced | **required** (`namespace: default`) |

**A managed resource with no `providerConfigRef` is defaulted by the API server to
`{kind: ClusterProviderConfig, name: default}`** - so `ClusterProviderConfig` is what an E2E test
should create (and what the generated E2E tests do create). Only when a composition deliberately
sets `providerConfigRef.kind: ProviderConfig` must the test create a namespaced `ProviderConfig`
in the XR's namespace instead. A mismatch here leaves the managed resource with **no status
conditions and no events at all** - inert, with nothing to debug.

---

## Patterns

These are ways of *structuring* tests. Each per-language reference shows the concrete syntax.

### Resource-Focused Bundle

Group 3-5 related tests in one directory that share a base spec (composition/xrd path, timeout, validate) and vary only the XR config and expected resources. Reduces duplication and keeps related scenarios (basic, feature-enabled, feature-disabled) together. Syntax: KCL spread / Python helper / YAML `---` documents.

### Parameterized Test Matrix

When you have 5+ near-identical variants (one per flag/region/size), generate them from a data list instead of copy-pasting. Guarantees consistency. KCL and Python can build these programmatically; YAML lists them out explicitly (still fine, just verbose).

### Sequential Testing with observedResources

Test resource **dependencies** and **status-driven branches** without real cloud, by feeding `observedResources` with mocked `status` into the render:

- Test N asserts the resources that render given the observed state of prior resources.
- Set `validate: false` for these - you are deliberately mocking status the schema would not populate.
- Mock only the status fields the composition actually reads (e.g. `status.atProvider.state: deployed`, a condition `type: Ready, status: "True"`, or a provider-specific status contract like `status.eks.clusterArn`).

This is how you verify "resource B only renders once resource A is Ready" and "the XR surfaces field X once the observed endpoint is known". See the real multi-step examples in yaml.md (`control-plane-project-charter` `languages/yaml.md`).

---

## Common Mistakes

Language-neutral mistakes. (KCL import-syntax and Python dump-mode mistakes live in their own references.)

### 1. Wrong ProviderConfig authentication
**Wrong:** Hardcoded long-lived keys inlined in the test.
**Right:** Web identity / injected identity (`source: Upbound`) on a Spaces control plane; otherwise (e.g. a local one) a `source: Secret` ProviderConfig whose value is sourced from a **`UP_`-prefixed** env var into `stringData` (the training-lab pattern; the prefix is what gets it into a KCL or Python generation container, and keeps a Go test portable). Never commit real keys.

### 2. Stale or missing crossplane block (E2E)
**Wrong:** Copying a pinned `version:` from an old example (rots immediately).
**Right:** Track a channel (`autoUpgrade.channel: Stable` or `Rapid`, no pinned version) — recommended, what real configs use, and a fine default.
**Right:** Or pin a **current** UXP version deliberately when you need determinism: `version: <current>` plus `autoUpgrade.channel`.

### 3. Guessed composed-resource names
**Wrong:** `name: test-vpc` (a guess).
**Right:** The exact generated name from `up composition render` (e.g. `vpc-test-vpc`).

### 4. Timeouts that don't fit
**Wrong:** `timeoutSeconds: 30` (composition) or an E2E timeout too small for what you provision.
**Right:** ≥60 for composition; size E2E to the real resources - a couple of Azure resources ≈ 900s, a full EKS cluster + add-ons ≈ 3600-5400s.

### 5. Missing `namespace: default` (v2)
**Wrong:** XR without a namespace, or a namespaced `ProviderConfig` without one.
**Right:** `namespace: default` on the XR, and on the `ProviderConfig` kind (namespaced). `ClusterProviderConfig` is cluster-scoped - omit namespace there.

### 6. Existence-only assertions
**Wrong:** Asserting a resource exists but none of its fields.
**Right:** Assert every critical field - region, CIDRs, chart name/version/repo, and the `forProvider` config. Don't assert `providerConfigRef` or `managementPolicies` unless the project's spec or API sets them: by default they are API-server defaults the composition does not set (`control-plane-project-charter` §5), and in Python `exclude_unset=True` keeps them out anyway.

### 7. A composed resource with no assertion at all
`assertResources` is a *partial, positive* check: it verifies the resources you list and ignores every other resource the composition emits. Adding a managed resource to a function and re-running the suite therefore **passes without testing anything** - verified: a whole extra MR plus new `spec` fields left a 2-test suite at 2/2 PASS with assertions untouched.
**Right:** Every resource a composition can emit needs an assertion, including ones behind a condition (give those their own test with the triggering XR/observed state).
**Right:** Cross-check against reality with `up test run "tests/<t>" --function-logs`, then read `_output/composition_test/<ts>/<test>/render.log` - it lists the rendered XR and every composed resource.

### 8. `skipDelete: true` in E2E
**Wrong:** Leaves real cloud resources running and costing money.
**Right:** Always `skipDelete: false`.

---

## Refactoring workflow

### Planning

1. Analyze `tests/` directory structure
2. Identify duplication and consolidation opportunities
3. Create `.agents/tasks/REFACTOR_TESTS.md` with prioritized items ([template](#refactoring-plan-template))
4. DO NOT execute - inform user how to proceed

### Executing
1. Check for `.agents/tasks/REFACTOR_TESTS.md`
2. If missing: do the Planning steps above and stop there; report the plan rather than
   executing it (charter §1: never block on a question nobody can answer)
3. Execute ONLY the highest priority unchecked item
4. **Run the gate once the suite is green**, as in SKILL.md's "The gate, after the loop": the
   project's own gate if it has one, else `verify-configuration` for the build and the whole
   suite. E2E or a deploy only where the project, the user or your instructions allow it
   (charter §9)
5. Mark item complete with date
6. Report completion and next item

## Refactoring Plan Template

Create at `.agents/tasks/REFACTOR_TESTS.md`:

```markdown
# Test Refactoring Plan

Last updated: YYYY-MM-DD

## High Priority

- [ ] **P1: [Title]** - [Description] (reduces [metric] by [amount])
- [ ] **P2: [Title]** - [Description]

## Medium Priority

- [ ] **P3: [Title]** - [Description]
- [ ] **P4: [Title]** - [Description]

## Low Priority

- [ ] **P5: [Title]** - [Description]

## Completed

- [x] **P0: Initial analysis** - Identified refactoring opportunities (YYYY-MM-DD)
```

### 9. Assuming you cannot assert the composite's own `status`
`assertResources` is named for composed resources and typed
`Optional[List[Dict[str, Any]]]`, so it looks like composed resources are all it takes.
**It matches the rendered composite too.** Drop the XR itself into `assertResources`
with a `status` block and composition outputs become testable.

**Wrong:** Concluding "the CompositionTest model has no `assertComposite`/`assertStatus` field,
so composition outputs cannot be verified" - and then leaving `assertResources=[]` on
the very test written to cover status propagation. Observed: a status-propagation test
that exercised the code path and asserted nothing.
**Right:** Assert the composite:
```python
assertResources=[
    {
        "apiVersion": "platform.example.com/v1alpha1",
        "kind": "EncryptedTable",
        "metadata": k8s.ObjectMeta(name="user-sessions", namespace="default")
                       .model_dump(by_alias=True, exclude_unset=True),
        "status": {"tableName": "user-sessions", "kmsKeyId": "1111-..."},
    },
]
```
Verified by mutating one expected value, which fails with an exact field path and a diff:
```text
* status.kmsKeyId: Invalid value: "1111-...": Expected value: "MY-OWN-DELIBERATE-MUTATION"
--- expected
+++ actual
-  kmsKeyId: MY-OWN-DELIBERATE-MUTATION
+  kmsKeyId: 1111-...
```
Any XR whose `status` is populated from observed resources needs this - it is the only
programmatic check on composition outputs.

### 10. Partial for objects, exact for lists — and the two fail differently
Pitfall 7 is about whole resources going unasserted. Inside a resource the rule splits, and
the split is not intuitive:

| What you assert | Behaviour |
|---|---|
| An **object**/mapping | partial, at every depth. Two keys asserted against ten rendered: **passes**. The surplus is never reported. |
| A **list** | exact. Two entries asserted against five rendered: **fails**, with `lengths of slices don't match`. Order matters too. |

Verified against the assertion engine (`sliceNode.Assert` compares `len` before comparing
elements) and reproduced end to end.

So the two mistakes are opposite:

**Wrong:** Asserting two keys of a ten-key mapping and concluding the mapping is correct — a
superset match is exactly what a passing partial assertion means.
**Wrong:** Asserting a two-entry subset of a five-entry list expecting a lenient pass — you get a
confusing length error instead.

**Right:** For a **list**, assert the whole thing, in order. That is also what makes the count part
of the test.
**Right:** For a **mapping**, if the *exact* key set is the property under test, that property is not
expressible in `assertResources`. Read the rendered object out of `render.log`
(`--function-logs`), or assert something that changes when a surplus key appears.
**Right:** State plainly which you did. "Asserted the keys I expect are present" and "confirmed these
are the only keys emitted" are different claims.

### 11. Designing coverage without reading the XRD's defaults
A test's input is not the XR you wrote — it is the XR **after the XRD's defaults have been
applied**. A field you deliberately omitted to exercise the "unset" branch is not unset if
the XRD gives it a `default`, and the branch you meant to cover never runs.

Read the XRD before choosing the shapes to test:

```bash
yq '.spec.versions[].schema.openAPIV3Schema.properties.spec' apis/<kind>/definition.yaml \
  | grep -nE 'default:|required:|enum:'
```

**Wrong:** "The minimal XR omits `retentionDays`, so this test covers the no-retention branch."
**Right:** Check first. If the XRD defaults `retentionDays: 30`, no XR can omit it, that branch is
unreachable from the API, and the honest coverage note says so — or the default is the bug.
