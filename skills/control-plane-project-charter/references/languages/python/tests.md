# Python: Tests

Writing composition and E2E tests in Python: coverage in Python, how assertions behave, the templates, and the two dump modes.

Language-agnostic rules are in [`control-plane-project-charter`](../../../SKILL.md); the Python index is [`../python.md`](../python.md).

---

# Part 4 — Tests

## Coverage in Python

What the suite must contain — a minimal XR, one test per observed-state branch, every status
field asserted on the composite, absence guarded through `resourceRefs` — and how to report it
is language-agnostic: [`charter/evidence.md` § Coverage](../../charter/evidence.md#coverage-what-the-suite-must-contain).
This section is how each part is written in Python.

**1. A minimal XR, inline:**

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

The Python bug the minimal XR catches: an XRD object with `default: {}` generates
`Optional[Kms] = {}`, and Pydantic does not coerce defaults — so the field is a plain `dict`
when omitted and a model when set, and no single access style is correct.

**2. Observed state** — code gated on `req.observed.resources` or on readiness:

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

Two cases, *observed but not ready* and *observed and ready*, are what separate
`is_resource_ready` from `resource_exists` in your assertions.

**3. Status on the composite.** In Python the clobbering write is a `resource.update()` that
writes `{"status": {...}}` more than once: all but the last are dropped.

**4. Absence through `resourceRefs`** on the composite:

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

Copy the list out of `render.log` rather than retyping or reasoning about it: why the
generated names are safe to hardcode and why the order is the renderer's is in
[`charter/evidence.md`](../../charter/evidence.md).

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
4. No `exclude={"spec": {"deletionPolicy"}}`: the `.m.` Spec has no `deletionPolicy` field, so
   the exclusion does nothing. For `managementPolicies`: `exclude_unset=True` keeps whatever you *did* set. If you set
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

### Asserting a `providerConfigRef` equal to the model default
The `.m.` models default `providerConfigRef` to `{kind: ClusterProviderConfig, name: default}`. Up
to function-sdk-python 0.12.0 (`up function generate` pins 0.11.0), `resource.update()` dumps with
`exclude_defaults`, so a function that sets exactly that value renders **without** the field and
an assertion on it fails. From 0.13.0 `exclude_unset` keeps an explicit value.
**Right:** do not set or assert the default at all (charter §5). A non-default `providerConfigRef`
the project asks for serializes under every version.
