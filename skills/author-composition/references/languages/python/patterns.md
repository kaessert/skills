# Python: Composition function patterns

The function bootstrap, what a v2 managed resource needs, and the data-shape patterns that bite in Python: tag maps, `resource.update()` semantics, optional XRD objects, namespace propagation, and designing an XRD that generates clean models.

Language-agnostic rules are in [`../../charter.md`](../../charter.md); the Python index is [`../python.md`](../python.md).

---

## Pattern 2: Function Bootstrap (SDK `RunFunction` + struct_to_dict)

The SDK function is a gRPC `FunctionRunner` class. Parse the observed XR with
`struct_to_dict` as the first step inside
`RunFunction`, right after `rsp = response.to(req)`:

```python
# functions/network/function/fn.py
import grpc
from crossplane.function import logging, resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from crossplane.function.proto.v1 import run_function_pb2_grpc as grpcv1

from models.io.k8s.apimachinery.pkg.apis.meta import v1 as k8s
from models.io.upbound.m.azure.resourcegroup import v1beta1 as rgv1beta1
from models.io.upbound.m.azure.network.virtualnetwork import v1beta1 as vnetv1beta1
from models.io.example.platform.network import v1alpha1 as networkv1alpha1


class FunctionRunner(grpcv1.FunctionRunnerService):
    """A FunctionRunner handles gRPC RunFunctionRequests."""

    def __init__(self):
        self.log = logging.get_logger()

    async def RunFunction(
        self, req: fnv1.RunFunctionRequest, _: grpc.aio.ServicerContext
    ) -> fnv1.RunFunctionResponse:
        rsp = response.to(req)

        # REQUIRED: struct_to_dict converts protobuf Struct → Python dict.
        # Without this, newer Up CLI versions fail with attribute access errors.
        observed_xr = networkv1alpha1.Network(
            **resource.struct_to_dict(req.observed.composite.resource)
        )

        location = observed_xr.spec.location
        tags = dict(observed_xr.spec.tags) if observed_xr.spec.tags else {}
        # ...build managed resources, resource.update(...), then:
        return rsp
```

**Why struct_to_dict**: `req.observed.composite.resource` is a
`google.protobuf.Struct` — it always has been, in every version of the function SDK, so this
is not a CLI-version question. `struct_to_dict` converts it to a plain dict.

**The failure is loud, not silent.** `Kind(**req.observed.composite.resource)` *does* unpack
the top level (Struct exposes `keys()`/`__getitem__`), but the nested values are still
`Struct`, and Pydantic fails at construction with:

```
AttributeError: get
```

That message names nothing useful, which is why it is worth recognising. (The other
`AttributeError` — `'Struct' object has no attribute 'spec'` — comes from touching
`req.observed.composite.resource.spec` directly, not from the `**` form.)

> **Embedded layout:** the same body lives in `def compose(req, rsp):` inside
> `functions/network/main.py` (no class; `rsp` is a parameter, so you skip
> `rsp = response.to(req)`), with `.model.` import prefixes.

---

## Pattern 3: What a v2 managed resource needs

See [`../charter.md` §5](../../charter.md#5-crossplane-v2-what-a-composed-resource-actually-needs).
In Python that reduces to: construct the resource with `spec=SomeSpec(forProvider=ForProvider(...))`
and set nothing else.

```python
desired_resource = SomeResource(
    spec=SomeSpec(
        forProvider=ForProvider(...),   # this is the part you own
    ),
)
resource.update(rsp.desired.resources["key"], desired_resource)
```

The Pydantic models make `kind` a *required* field of `ProviderConfigRef`. That is a
constraint on constructing the object, not a reason to construct it.

---

## Pattern 4: Tags / Labels Conversion

**It depends entirely on how the XRD declared the field**, and the common advice is stated
too strongly.

With `additionalProperties: {type: string}` — the schema Pattern 10 tells you to use — codegen
emits `tags: Optional[Dict[str, str]] = None`. The value is **already a plain dict**, and
`dict(...)` is a harmless no-op rather than a fix.

`dict(...)` is only load-bearing when the XRD declared **fixed properties**, which makes
codegen emit a model class. That schema is the actual defect; fix the XRD (Pattern 10).

```python
# Works under either schema, and is what to write when you are not sure:
tags = dict(observed_xr.spec.tags) if observed_xr.spec.tags else {}

# ✅ ALSO CORRECT - with extra default tags merged
base_tags = dict(observed_xr.spec.tags) if observed_xr.spec.tags else {}
tags = {**base_tags, "ManagedBy": "crossplane", "Platform": platform_name}
```

**XRD schema must use `additionalProperties` (not fixed properties):**

```yaml
# ✅ CORRECT - flexible map, Python-compatible
spec:
  properties:
    tags:
      type: object
      additionalProperties:
        type: string

# ❌ WRONG - fixed properties generate None for missing keys → Pydantic fails
spec:
  properties:
    tags:
      type: object
      properties:
        Environment:
          type: string
        Team:
          type: string
```

**Error symptom of wrong schema**: `Input should be a valid string [input_value=None]`

---

## Pattern 4b: `resource.update()` is NOT a merge — it clobbers nested keys

`resource.update()` delegates to protobuf `Struct.update`, and protobuf **clears a
sub-struct before writing a nested dict**. The name says merge; the behaviour is replace.

```python
from google.protobuf.struct_pb2 import Struct
s = Struct()
s.update({"status": {"a": 1}})
s.update({"status": {"b": 2}})
# -> {'status': {'b': 2.0}}      # 'a' is GONE
```

So the natural way to propagate several XR outputs silently keeps only the last one:

```python
# WRONG — three of these four writes are discarded
resource.update(rsp.desired.composite, {"status": {"kmsKeyArn": arn}})
resource.update(rsp.desired.composite, {"status": {"kmsKeyId": key_id}})
resource.update(rsp.desired.composite, {"status": {"tableName": name}})
resource.update(rsp.desired.composite, {"status": {"tableArn": table_arn}})
```

```python
# RIGHT — one call, one dict
resource.update(rsp.desired.composite, {
    "status": {
        "kmsKeyArn": arn,
        "kmsKeyId": key_id,
        "tableName": name,
        "tableArn": table_arn,
    },
})
```

**Why this is hard to catch:** it does not crash and does not fail validation. The
composition renders, composed resources are correct, and the suite is green — the XR just
reports three of its four outputs as absent, and you blame the provider. It also wipes
anything else already under `status`, including `status.conditions`.

Assert the composite's `status` in a composition test so this has a regression guard —
`assertResources` matches the composite (see Part 4).

---

## Pattern 4c: An optional XRD object is a `dict` when absent and a model when present

> ### Read this gate before applying this pattern
>
> **This affects exactly one case, and defending against it elsewhere produces dead code.**
> Open the generated XR model and look at the field's declaration:
>
> ```bash
> # NOTE: --fields on an XR prints its Spec fields, but only one level deep. A nested
> # spec.parameters needs the model itself:
> #   .up/python/models/<reversed-group>/<kind>/<version>.py
> ```
>
> | Generated declaration | What you get | How to read it |
> |---|---|---|
> | `kms: Optional[Kms] = {}` | `dict` when absent, `Kms` when set | **normalise first** — this pattern applies |
> | `kms: Optional[Kms] = None` | `None` when absent, `Kms` when set | `xr.spec.kms.field if xr.spec.kms else <default>` |
> | `rules: Optional[List[Rule]] = None` | `None` when absent, `list[Rule]` when set | `for r in (xr.spec.rules or []): r.prefix` |
>
> Only a **non-`None` default in the generated file** triggers this. Everything else is
> fully typed and the model is authoritative.
>
> **Anti-pattern — dead defensive code.** Against a typed field, none of this can ever fire:
>
> ```python
> # WRONG: params.lifecycleRules is Optional[List[LifecycleRule]] — always models or None
> if hasattr(params, "lifecycleRules") and params.lifecycleRules:      # hasattr: always True
>     for rule in params.lifecycleRules:
>         d = rule.model_dump() if not isinstance(rule, dict) else rule  # never a dict
> ```
>
> ```python
> # RIGHT: typed access
> for rule in (params.lifecycleRules or []):
>     prefix = rule.prefix
> ```
>
> `hasattr` on a Pydantic model field is always `True`. `isinstance(x, dict)` on a typed
> list element is always `False`. Reserve dict handling for genuinely untyped input —
> `resource.struct_to_dict()` output, `context`, and fields the table above marks.

A nested XRD object with `default: {}` generates `kms: Optional[Kms] = {}`. **Pydantic does
not validate or coerce default values** (`validate_default=False`), so the declared type is
wrong exactly when the caller omits the field:

```python
Spec().kms                                 # -> {}        <class 'dict'>
Spec(kms={"enableKeyRotation": False}).kms # -> Kms(...)   <class 'Kms'>
```

There is therefore **no single access style that is correct**:

```python
cfg = xr.spec.kms or {}
cfg.get("enableKeyRotation", True)   # crashes when the field IS set  (Kms has no .get)
cfg.enableKeyRotation                # crashes when the field is ABSENT (dict has no attr)
```

Both halves of this trap are easy to write, and each is correct for half the inputs.

Fix it in two places:

1. **In the function** — normalise before reading:
   ```python
   raw = xr.spec.kms
   kms = raw if isinstance(raw, xrv1alpha1.Kms) else xrv1alpha1.Kms(**(raw or {}))
   rotation = kms.enableKeyRotation if kms.enableKeyRotation is not None else True
   ```
2. **In the XRD** — drop `default: {}` from object-typed properties. It buys nothing: the
   API server applies nested defaults once the object exists, and so does `up test run`
   ([`../charter.md` §2](../../charter.md#2-discover-do-not-interview)).

**Where this actually bites — and where it does not.** `up test run` applies the XRD's
structural defaults whenever the test sets `xrdPath`, so `encryption: {}` is materialised into
a model *before* your function runs and the `dict` branch never executes. A real API server
does the same. So a "minimal XR" test case does **not** catch this; a suite can be green with
the naked `params.encryption.enabled` still in place.

It bites only where nothing applies the XRD:

| Render path | XRD applied? | `default: {}` arrives as |
|---|---|---|
| `up test run` with `xrdPath` set | yes | a model |
| `up test run` with no `xrdPath` | no | a `dict` — **this is the branch that crashes** |
| bare `crossplane render`, `run_function.py` | no | a `dict` |
| a real control plane | yes | a model |

If every test in your suite sets `xrdPath`, the normalisation in step 1 is dead code — drop
`default: {}` from the XRD and skip it. If you need the guard, the test that proves it is one
with `xrdPath` deliberately unset.

---

## Pattern 5: Namespace Propagation

In Crossplane v2 every composed resource lands in the parent XR's namespace. **For managed
resources this is automatic — don't write it.** Verified in `render.log`: composed MRs whose
function never set a namespace still render with the XR's namespace.

```python
# functions/webplatform/function/fn.py — inside RunFunction (SDK); embedded: same
# body in compose(req, rsp). rsp = response.to(req) already called.
observed_xr = platformv1alpha1.WebPlatform(
    **resource.struct_to_dict(req.observed.composite.resource)
)
parent_ns = observed_xr.metadata.namespace  # only needed for the cases below

# Managed Resource → namespace is propagated for you, so omit it
resource_group = rgv1beta1.ResourceGroup(
    spec=rgv1beta1.Spec(...),
)
```

`parent_ns` is still needed in two cases:

**1. Objects you construct that aren't composed resources of this XR** — most commonly a Secret
you compose yourself (Pattern 9), where the namespace is part of the object.

**2. Composed child XRs.** Automatic propagation is verified for managed resources; for a child XR
setting it explicitly is harmless, so keep it rather than assume:

```python
# Composed XR (child platform resource)
network_xr = networkv1alpha1.Network(
    metadata=k8s.ObjectMeta(
        name=f"network-{observed_xr.metadata.name}",
        namespace=parent_ns,
    ),
    spec=networkv1alpha1.Spec(
        location=observed_xr.spec.location,
        cidr="10.0.0.0/16",
    ),
)
resource.update(rsp.desired.resources["network"], network_xr)
```

Then confirm what actually landed by reading `render.log` from
`up test run "tests/<t>" --function-logs`.

---

## Pattern 10: XRD Schema Design for Python

### Flexible Maps (tags, labels, annotations)

```yaml
# ✅ Use additionalProperties for any flexible key-value field
spec:
  properties:
    tags:
      type: object
      additionalProperties:
        type: string
      description: "Resource tags to apply"
    labels:
      type: object
      additionalProperties:
        type: string
```

### Common Field Types

```yaml
spec:
  properties:
    # String with enum constraint
    size:
      type: string
      enum: [small, medium, large]
      default: small

    # Integer with bounds
    nodeCount:
      type: integer
      minimum: 1
      maximum: 100

    # String with format validation
    cidr:
      type: string
      pattern: '^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$'

    # Nested object (use fixed properties ONLY when all keys are known and required)
    backup:
      type: object
      properties:
        enabled:
          type: boolean
          default: false
        retentionDays:
          type: integer
          default: 7
      required: [enabled]

    # Array of strings
    subnets:
      type: array
      items:
        type: string
```

### v2 XRD Structure Template

```yaml
apiVersion: apiextensions.crossplane.io/v2         # v2 - not v1
kind: CompositeResourceDefinition
metadata:
  name: xnetworks.network.platform.example.io
spec:
  scope: Namespaced                                  # REQUIRED in v2
  group: network.platform.example.io
  names:
    kind: Network                                    # X prefix optional in v2
    plural: xnetworks
  # claimNames: REMOVED in v2
  # connectionSecretKeys: REMOVED in v2 - use manual Secrets
  versions:
  - name: v1alpha1
    served: true
    referenceable: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              location:
                type: string
                description: "Azure region"
              tags:
                type: object
                additionalProperties:
                  type: string
            required: [location]
```
