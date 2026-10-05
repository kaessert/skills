# Python: tests

How composition-test assertions are written and dumped in Python. What a suite must contain, and
why, is in [`charter/evidence.md`](../../charter/evidence.md#coverage-what-the-suite-must-contain);
this file is the Python syntax for it. Templates are in [`test-templates.md`](test-templates.md);
the Python index is [`../python.md`](../python.md).

## The coverage shapes in Python

**A minimal XR, inline** (only the XRD-required fields):

```python
spec=compositiontest.Spec(
    compositionPath="apis/encryptedtables/composition.yaml",
    xrdPath="apis/encryptedtables/definition.yaml",
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

The embedded scaffold's `buildTest()` helper usually takes only `xrPath`. `xr` and `xrPath` are
mutually exclusive, so extend the helper with an `xr` parameter rather than duplicating it, and
pass `xrPath=None` on the inline calls:

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

**Observed state**, for code gated on `req.observed.resources` or on readiness. Use plain dicts:
`observedResources` is typed `List[Dict[str, Any]]`, and the generated `Condition` model's
`lastTransitionTime` is a `datetime` you do not want to serialize yourself.

```python
observedResources=[{
    "apiVersion": "kms.aws.m.upbound.io/v1beta1",
    "kind": "Key",
    "metadata": {
        "name": "x-key",
        "namespace": "default",
        "annotations": {
            "crossplane.io/composition-resource-name": "key",   # required: keys req.observed.resources["key"]
            "crossplane.io/external-name": "1111",
        },
    },
    "spec": {"forProvider": {"region": "us-west-1"}},
    "status": {
        "atProvider": {"arn": "arn:aws:kms:...:key/1111"},
        # Omit conditions for the "observed but not ready" case.
        "conditions": [
            {"type": "Ready", "status": "True", "reason": "Available",
             "lastTransitionTime": "2026-01-01T00:00:00Z"},
            {"type": "Synced", "status": "True", "reason": "ReconcileSuccess",
             "lastTransitionTime": "2026-01-01T00:00:00Z"},
        ],
    },
}],
```

**Status on the composite.** In Python the write that loses fields is more than one
`resource.update(rsp.desired.composite, {"status": …})` ([`patterns.md`](patterns.md)).

**Absence through `resourceRefs`** on the composite. Copy the list out of `render.log`; it is
matched exactly in length and order:

```python
"spec": {"crossplane": {"resourceRefs": [
    {"apiVersion": "s3.aws.m.upbound.io/v1beta1", "kind": "BucketPublicAccessBlock",
     "name": "example-73dd10b7cb62"},
    {"apiVersion": "s3.aws.m.upbound.io/v1beta1", "kind": "BucketVersioning",
     "name": "example-6f55c6f6ac57"},
    {"apiVersion": "s3.aws.m.upbound.io/v1beta1", "kind": "Bucket",
     "name": "example-bucket"},   # a name the function set itself
]}},
```

## The two dump modes

Python tests are Pydantic objects serialized into the test object model. Which dumps you control
depends on the layout:

| | SDK layout | Embedded layout |
|---|---|---|
| Each asserted resource | `.model_dump(by_alias=True, exclude_unset=True)`: only fields you set are compared, so the assertion stays partial | same |
| The top-level test object | you dump it: `.model_dump(by_alias=True, exclude_none=True)`, then `print(yaml.dump({"items": [...]}))` | the runner does it (`exclude_defaults=True, by_alias=True`, plus None-stripping); you dump nothing |

`by_alias=True` is load-bearing: the model declares `validate_: Optional[bool] =
Field(None, alias='validate')`, and without it the field serializes as `validate_`, which the
runner ignores. The CLI templates ship `assertResources=[]`, so the asserted-resource mode is a
convention; projects vary (one embedded project uses `exclude_unset=True` without `by_alias`).
`exclude_unset` is what keeps the assertion partial.

## Assertion rules

1. Asserted resources carry `apiVersion` and `kind`, unlike resources a function builds.
2. `metadata.namespace` is optional on an expectation: the render carries the XR's namespace,
   and assertions are partial.
3. Do not set `managementPolicies=["*"]` on an expected resource: `exclude_unset` keeps what you
   set, and the assertion then fails against a render that correctly omits it. No
   `exclude={"spec": {"deletionPolicy"}}` either: the `.m.` Spec has no such field.
4. Never exclude `writeConnectionSecretToRef`: it is an API contract.

## Python-specific mistakes

| Mistake | Fix |
|---|---|
| `exclude_none=True` on asserted resources (compares too much), or `exclude_unset=True` on the top-level test | asserted resources `exclude_unset=True`; top-level test `exclude_none=True` |
| `up test generate` before `.up/python` exists: imports do not resolve | `up project build` first, so `crossplane-models` is wired into `pyproject.toml` |
| A function sets, and a test asserts, `providerConfigRef` equal to the model default `{kind: ClusterProviderConfig, name: default}` | up to function-sdk-python 0.12.0 (`up function generate` pins 0.11.0) `resource.update()` dumps with `exclude_defaults`, so that value is missing from the render and the assertion fails; from 0.13.0 `exclude_unset` keeps it. Do not set or assert the default (charter §5); a non-default `providerConfigRef` the project asks for serializes under every version |
