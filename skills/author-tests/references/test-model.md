# The test model, patterns and common mistakes (language-agnostic)

The object model, structuring patterns and mistakes that apply to Crossplane configuration
tests in every language. The syntax is in the charter's `languages/` files
(`control-plane-project-charter`, indexed by `languages/README.md`); writing an `E2ETest` is
[e2e.md](e2e.md).

- [The test object model](#the-test-object-model)
- [Patterns](#patterns)
- [Common mistakes](#common-mistakes)
  1. [Guessed composed-resource names](#1-guessed-composed-resource-names)
  2. [A composed resource with no assertion at all](#2-a-composed-resource-with-no-assertion-at-all)
  3. [Assuming you cannot assert the composite's own status](#3-assuming-you-cannot-assert-the-composites-own-status)
  4. [Partial for objects, exact for lists](#4-partial-for-objects-exact-for-lists--and-the-two-fail-differently)
  5. [Designing coverage without reading the XRD's defaults](#5-designing-coverage-without-reading-the-xrds-defaults)

---

## The test object model

Every test, in any language, produces one of two objects under
`apiVersion: meta.dev.upbound.io/v1alpha1`. KCL, Python and Go builders and raw YAML all
render to exactly this shape.

### CompositionTest (fast, local, no cloud)

| Field | Meaning |
|-------|---------|
| `metadata.name` | Test name (unique within its directory) |
| `spec.compositionPath` | Path to the composition under test (e.g. `apis/<xr>/composition.yaml`) |
| `spec.xrdPath` | Path to the XRD (`apis/<xr>/definition.yaml`); its defaults reach the render |
| `spec.xr` | The XR under test, defined **inline** (recommended). Some layouts use `xrPath` instead; the two are mutually exclusive |
| `spec.validate` | `false`, the scaffold default; leave it |
| `spec.timeoutSeconds` | **≥60** |
| `spec.assertResources` | Expected rendered resources. Assert the fields, not just existence. Matches the **composite** as well as composed resources ([mistake 3](#3-assuming-you-cannot-assert-the-composites-own-status)) |
| `spec.observedResources` | Optional. Pre-existing resources (with mocked `status`) fed into the render, to test dependency ordering and status-driven branches |

### E2ETest (real cloud lifecycle)

Fields, defaults, credentials, the ProviderConfig it creates, and what it cannot assert:
[e2e.md](e2e.md).

Managed resources in either kind follow binding rule 5; how the `.m.` group is spelled
(import path or `apiVersion` string) is in the language file.

---

## Patterns

Ways of *structuring* tests. Each language file shows the syntax.

### Resource-focused bundle

Group 3-5 related tests in one directory that share a base spec (composition/XRD path,
timeout, validate) and vary only the XR and the expected resources: basic, feature-enabled,
feature-disabled. Syntax: KCL spread, a Python helper, YAML `---` documents.

### Parameterized test matrix

With 5+ near-identical variants (one per flag, region or size), generate them from a data
list instead of copy-pasting. KCL, Python and Go build these programmatically; YAML lists them
out (fine, just verbose).

### Sequential testing with observedResources

Test resource **dependencies** and **status-driven branches** without a cloud, by feeding
`observedResources` with mocked `status` into the render:

- Test N asserts what renders given the observed state of prior resources.
- Keep `validate: false`: you are deliberately mocking status the schema would not populate.
- Mock only the status fields the composition reads (e.g. `status.atProvider.state: deployed`,
  a condition `type: Ready, status: "True"`, or a provider-specific contract like
  `status.eks.clusterArn`). What a mock needs to be observed at all (the annotation, and for a
  namespaced XR its namespace and the render's name) and the condition rules: the charter's
  `charter/evidence.md`, "Coverage".

This verifies "resource B only renders once resource A is Ready" and "the XR surfaces field X
once the observed endpoint is known". Examples: the charter's language file for your test
language (Go: `languages/go/tests.md`, `status-from-observed-bucket`; YAML: `languages/yaml.md`).

---

## Common mistakes

Language-neutral mistakes beyond the rules in SKILL.md. KCL import-syntax and Python
dump-mode mistakes live in their language files.

### 1. Guessed composed-resource names

**Wrong:** `name: test-vpc` (a guess).
**Right:** omit `metadata.name` when a kind appears once in the render; when it appears more
than once, assert each by the name copied from the render, which is deterministic there
(charter `charter/evidence.md`).

### 2. A composed resource with no assertion at all

`assertResources` is a *partial, positive* check: it verifies the resources you list and
ignores every other resource the composition emits. Adding a managed resource to a function
and re-running the suite **passes without testing anything** (verified: a whole extra MR plus
new `spec` fields left a 2-test suite at 2/2 PASS).
**Right:** Every resource a composition can emit needs an assertion, including ones behind a
condition (give those their own test with the triggering XR or observed state). Cross-check
against the render, read as charter `charter/evidence.md` says; asserting the composite's
`spec.crossplane.resourceRefs` makes a surplus resource fail.

### 3. Assuming you cannot assert the composite's own `status`

`assertResources` is named for composed resources and typed
`Optional[List[Dict[str, Any]]]`, so it looks like composed resources are all it takes.
**It matches the rendered composite too.** Drop the XR itself into `assertResources` with a
`status` block and composition outputs become testable.

**Wrong:** concluding "the CompositionTest model has no `assertComposite`/`assertStatus`
field, so composition outputs cannot be verified", and leaving `assertResources=[]` on the
test written to cover status propagation.
**Right:** assert the composite:
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
Any XR whose `status` is populated from observed resources needs this — it is the only
programmatic check on composition outputs.

### 4. Partial for objects, exact for lists — and the two fail differently

Mistake 2 is about whole resources going unasserted. Inside a resource the rule splits
(charter §8):

| What you assert | Behaviour |
|---|---|
| An **object**/mapping | partial, at every depth. Two keys asserted against ten rendered: **passes**. The surplus is never reported. |
| A **list** | exact. Two entries asserted against five rendered: **fails**, with `lengths of slices don't match`. Order matters too. |

Verified against the assertion engine (`sliceNode.Assert` compares `len` before comparing
elements) and reproduced end to end. So the two mistakes are opposite:

**Wrong:** asserting two keys of a ten-key mapping and concluding the mapping is correct.
**Wrong:** asserting a two-entry subset of a five-entry list expecting a lenient pass.

**Right:** for a **list**, assert the whole thing, in order; that also makes the count part of
the test.
**Right:** for a **mapping** whose *exact* key set is the property under test, that property is
not expressible in `assertResources`. Read the rendered object out of the render, or assert
something that changes when a surplus key appears.
**Right:** state which you did. "Asserted the keys I expect are present" and "confirmed these
are the only keys emitted" are different claims.

### 5. Designing coverage without reading the XRD's defaults

A test's input is not the XR you wrote — it is the XR **after the XRD's defaults have been
applied**. A field you omitted to exercise the "unset" branch is not unset if the XRD gives it
a `default`, and the branch you meant to cover never runs.

Read the XRD before choosing the shapes to test:

```bash
yq '.spec.versions[].schema.openAPIV3Schema.properties.spec' apis/<kind>/definition.yaml \
  | grep -nE 'default:|required:|enum:'
```

**Wrong:** "The minimal XR omits `retentionDays`, so this test covers the no-retention branch."
**Right:** check first. If the XRD defaults `retentionDays: 30`, no XR can omit it, that branch
is unreachable from the API, and the honest coverage note says so — or the default is the bug.
