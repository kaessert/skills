# Python: Tests

Writing composition and E2E tests in Python: what the suite must contain, how assertions behave, the templates, and the two dump modes.

Language-agnostic rules are in [`control-plane-project-charter`](../../../SKILL.md); the Python index is [`../python.md`](../python.md).

---

# Part 4 — Tests

## Coverage: what the suite must contain

The scaffold generates **one** test, against **one** example XR, asserting **only** composed
resources. That suite is green over a function that crashes on a minimal XR, silently drops
status fields, and never runs its readiness branch. "The tests pass" is not a verification
claim until the suite covers these three shapes.

**1. One test per input shape — including a minimal XR.**
Use the inline `xr` field instead of `xrPath`; you do not need a second example file.

```python
spec=compositiontest.Spec(
    compositionPath="apis/encryptedtables/composition.yaml",
    xrdPath="apis/encryptedtables/definition.yaml",
    # inline XR: only the XRD-required fields, every optional one omitted
    xr={
        "apiVersion": "platform.example.com/v1alpha1",
        "kind": "EncryptedTable",
        "metadata": {"name": "minimal", "namespace": "default"},
        "spec": {"region": "us-west-2", "hashKey": {"name": "id", "type": "S"}},
    },
    timeoutSeconds=120,
    assertResources=[...],
)
```

**In the embedded layout the scaffolded `buildTest()` helper usually takes only
`xrPath`.** Inline `xr` and `xrPath` are mutually exclusive, so you cannot just pass `xr`
alongside it — extend the existing helper with an `xr` parameter rather than duplicating it,
and pass `xrPath=None` explicitly on the inline calls so the two never travel together:

```python
def buildTest(name, *, xrPath=None, xr=None, assertResources=None):
    return compositiontest.CompositionTest(
        metadata=k8s.ObjectMeta(name=name),
        spec=compositiontest.Spec(
            compositionPath="apis/<kind>/composition.yaml",
            xrdPath="apis/<kind>/definition.yaml",
            xrPath=xrPath, xr=xr,
            timeoutSeconds=120,
            assertResources=assertResources or [],
        ),
    )

test_minimal = buildTest("minimal", xrPath=None, xr={...})
```

This is where "the user wrote the obvious minimal manifest" bugs live. An XRD object with
`default: {}` generates `Optional[Kms] = {}`, and Pydantic does not coerce defaults — so the
field is a plain `dict` when omitted and a model when set, and no single access style is
correct. The shipped example usually sets every optional field, so this branch never renders.

**2. One test per observed-state branch.**
Code gated on `req.observed.resources` or on readiness **never executes** when
`observedResources` is empty — it is unexercised, not merely unasserted. Supply the observed
state explicitly:

```python
observedResources=[
    {
        "apiVersion": "kms.aws.m.upbound.io/v1beta1",
        "kind": "Key",
        "metadata": {
            "name": "x-key",
            "namespace": "default",
            "annotations": {
                # REQUIRED. It is what keys the resource into req.observed.resources["key"],
                # and the renderer rejects the whole test without it:
                #   encountered composed resource without required
                #   "crossplane.io/composition-resource-name" annotation
                "crossplane.io/composition-resource-name": "key",
                "crossplane.io/external-name": "1111",
            },
        },
        "spec": {"forProvider": {"region": "us-west-1"}},
        "status": {
            "atProvider": {"arn": "arn:aws:kms:...:key/1111"},
            # Without conditions the resource is observed but NOT ready, which is its own
            # useful test case. Add this block to drive the ready branch.
            "conditions": [
                {"type": "Ready", "status": "True", "reason": "Available",
                 "lastTransitionTime": "2026-01-01T00:00:00Z"},
                {"type": "Synced", "status": "True", "reason": "ReconcileSuccess",
                 "lastTransitionTime": "2026-01-01T00:00:00Z"},
            ],
        },
    },
],
```

`observedResources` is typed `List[Dict[str, Any]]`, so use plain dicts rather than the
generated models — `Condition.lastTransitionTime` is a `datetime`, and serialising one into
the test manifest is a wire-format gamble you do not need to take.

Writing *observed but not ready* and *observed and ready* as two cases is what separates
`is_resource_ready` from `resource_exists` in your assertions; with only the ready case, a
function that never checks readiness passes.

**3. Assert every `status` field the function writes, on the composite.**
`assertResources` matches the composite (see [`control-plane-project-charter` §8](../../../SKILL.md#8-a-green-run-is-not-evidence)). Without this, a
`resource.update()` that clobbers nested keys — writing `{"status": {...}}` more than once
drops all but the last — passes silently, and you blame the provider.

Other inline fields worth knowing, all `Optional`: `composition` and `xrd` (inline instead of
`*Path`), `extraResources`, `context`, and `functionCredentialsPath`.

**Asserting that something is NOT composed.** `assertResources` is positive-only for
objects: it cannot name a resource and say "not this", and there is no `assertAbsent`. A test
that renders the omitted-field case and lists the resources that *should* exist proves the
render succeeded — it does **not** prove the conditional resource was skipped. Do not report
it as if it did.

There are two ways to close that gap, and the first is an automated guard:

```python
# On the composite. resourceRefs is a LIST, and lists are matched exactly in length and
# order, so a surplus resource fails this assertion even though nothing asserts the
# resource itself. This is what catches `if cond:` accidentally becoming `if True:`.
"spec": {"crossplane": {"resourceRefs": [
    # Copied verbatim out of a render. Yours will differ — do not retype these.
    {"apiVersion": "s3.aws.m.upbound.io/v1beta1", "kind": "BucketPublicAccessBlock",
     "name": "example-73dd10b7cb62"},
    {"apiVersion": "s3.aws.m.upbound.io/v1beta1", "kind": "BucketVersioning",
     "name": "example-6f55c6f6ac57"},
    {"apiVersion": "s3.aws.m.upbound.io/v1beta1", "kind": "Bucket",
     "name": "example-bucket"},   # a name the function set itself
]}},
```

Two things that example is showing you, both from a real render:

- **Hardcoding a generated name here is safe.** A render synthesizes a deterministic uid, so
  those hashes are identical on every run — verified across repeated runs and a mutation run
  ([`control-plane-project-charter` §8](../../../SKILL.md#8-a-green-run-is-not-evidence)). §5's warning that
  generated names are unstable is about a live control plane, not a render.
- **The order is the renderer's**, and it is neither alphabetical nor creation order — the
  `Bucket` everything else depends on comes *last*. Copy the list out of `render.log` rather
  than reasoning about it. An upstream reordering breaks this assertion loudly, which is the
  safe direction to fail.

The second is the render output, which is also how you obtain that list:

```bash
up test run "tests/<t>" --function-logs
# then read the FULL list of rendered resources:
cat _output/composition_test/<ts>/<test>/render.log
```

Reading the whole log to eyeball what is missing is error-prone. Reduce it to the set of
resource names the composition actually emitted, and the absence is unambiguous:

```bash
grep -h "composition-resource-name:" _output/composition_test/<ts>/<test>/render.log \
  | sort | uniq -c
```

That prints one line per composed resource. For the no-rules case it should show exactly
`bucket`, `pab` and `sse` and **no** `lifecycle` entry — quote that output in your summary,
because it is the evidence, and the sorted list makes a surplus resource just as visible as
a missing one.

**`--function-logs` is required for this — without it nothing is written at all.** Verified:
a run with no `--function-logs` creates no `_output/composition_test` directory, so
`--output-dir` is inert on its own; it only relocates output that `--function-logs` causes
to exist. And neither works with `--e2e`.

So for a conditional resource, do all three:

1. A test for the omitted case asserting the resources that *should* be there. This catches
   crashes on that branch — the common failure — and is a real regression guard.
2. A **`resourceRefs` assertion on the composite**, which turns absence into a real automated
   guard: a surplus resource fails the list comparison.
3. A read of `render.log` confirming the conditional resource is absent, quoted in your
   summary — that is where you get the `resourceRefs` order from anyway.

Report it accurately. With a `resourceRefs` assertion: *"test 4 covers the
omitted-lifecycleRules branch; the composite's resourceRefs assertion fails if a lifecycle
resource appears."* Without one: *"absence was confirmed once by reading render.log and is
not asserted by the suite."* Never *"validates that no lifecycle resource is created"* unless
something actually fails when one is.

**Out of scope for any composition test.** Assertions are partial-positive, so a *stray*
field — an external-name annotation on a resource whose external name the provider assigns —
is never flagged. That class fails only on a live control plane.

## The two dump modes (CRITICAL)

Python tests are Pydantic objects serialized to the test object model. Which dumps you control
depends on the layout:

| | SDK layout | Embedded layout |
|---|---|---|
| **Each asserted resource** | `.model_dump(by_alias=True, exclude_unset=True)` — only the fields you explicitly set are compared (partial assertion) | same |
| **The top-level test object** | you dump it: `.model_dump(by_alias=True, exclude_none=True)`, then `print(yaml.dump({"items": [...]}))` | **the runner does it** (`exclude_defaults=True, by_alias=True` plus None-stripping). You dump nothing |

`by_alias=True` is load-bearing, not decoration: the generated model declares
`validate_: Optional[bool] = Field(None, alias='validate')`, so without it the field serializes
as `validate_` and the runner does not see it.

> The asserted-resource mode is a **convention**, not something the scaffold demonstrates — the
> CLI templates ship `assertResources=[]`, and real projects vary (one embedded project uses
> `model_dump(exclude_unset=True)` with no `by_alias`). `exclude_unset` is still the right
> choice, because it is what keeps the assertion partial.

Assertion rules:
1. Tests **INCLUDE** `apiVersion` and `kind` on asserted resources (unlike function resource creation).
2. Use the `.m.` suffix in `apiVersion` for v2 resources.
3. Include `namespace` in v2 metadata.
4. Exclude fields that vary. `exclude={"spec": {"deletionPolicy"}}` is **v1-only** — the `.m.`
   v2 Spec has no `deletionPolicy` field at all, so the exclusion is inert on a v2 resource;
   keep it only if the project still asserts against non-namespaced models.
   For `managementPolicies`: `exclude_unset=True` keeps whatever you *did* set. If you set
   `["*"]` on an expected resource it stays in the dump and the assertion then fails against a
   render that correctly omits it. The fix is not to set it.
5. **NEVER exclude** `writeConnectionSecretToRef` - it's an API contract.

**Templates:** [`test-templates.md`](test-templates.md) has the annotated composition-test and
E2E-test scaffolds.

---

## Python-Specific Mistakes

### Wrong dump mode
**Wrong:** Using `exclude_none=True` on asserted resources (compares too much) or `exclude_unset=True` on the top-level test.
**Right:** Asserted resources: `exclude_unset=True`. Top-level test: `exclude_none=True`.

### Imports don't resolve
**Wrong:** Running `up test generate` before `.up/python` exists.
**Right:** `up project build` first, so `crossplane-models` is wired into `pyproject.toml`.

### Excluding an API contract
**Wrong:** `exclude={"spec": {"writeConnectionSecretToRef"}}`.
**Right:** Never exclude `writeConnectionSecretToRef`.

### `providerConfigRef` name "default" silently stripped
The provider models default `providerConfigRef` to `{kind: ClusterProviderConfig, name: default}`, and the function SDK serializes with `exclude_defaults=True` - so a resource whose `providerConfigRef.name` is exactly `default` renders **without** the field, and the assertion won't match.
**Wrong:** `providerConfigRef=...ProviderConfigRef(kind="ClusterProviderConfig", name="default")`
**Right:** Use a non-default name (e.g. `azure-provider`) in both the XR/example and the assertion so the field is serialized.
