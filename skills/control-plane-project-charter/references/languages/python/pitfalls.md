# Python: Pitfalls, debugging and v1 to v2

The mistakes that produce a green run and a broken platform, how to read the failures, and what changes when moving a Python function from v1 to v2.

Language-agnostic rules are in [`control-plane-project-charter`](../../../SKILL.md); the Python index is [`../python.md`](../python.md).

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Wrong import path | `ModuleNotFoundError` | Run `python3 "$SCRIPTS/probe_project.py" --project <project-root> <Kind>` — never derive it by hand. Reversed group + lowercased Kind, de-duplicated when the group's **leftmost** segment already equals the Kind |
| No `struct_to_dict` | `AttributeError: get` at model construction — an unhelpful message, not a silent failure, and not version-dependent | Wrap in `resource.struct_to_dict()` |
| Several `resource.update(..., {"status": {...}})` calls | XR reports only the last field; `status.conditions` may vanish. Renders fine, tests green | `resource.update` clobbers nested keys (protobuf `Struct.update`). Write **one** call with all keys — Pattern 4b above |
| `xr.spec.<obj>.get(...)` or `.attr` on an optional XRD object | `AttributeError` on half your inputs: `'Kms' object has no attribute 'get'`, or `'dict' object has no attribute 'enableKeyRotation'` | `default: {}` in the XRD generates `Optional[Kms] = {}` and Pydantic does not coerce defaults, so it is a `dict` when absent and a model when set. Normalise first; drop `default: {}` — Pattern 4c |
| Only one example XR, which sets every optional field | The absent-field branch never renders, so it ships broken | Add a minimal XR (required fields only) as its own test case |
| Setting `providerConfigRef` at all | Resource never reconciles on a live control plane; composition test still passes | Omit it — namespaced MRs default to `ClusterProviderConfig/default`. `kind="ProviderConfig"` points at a namespaced config nothing creates |
| Setting `metadata.namespace` on MRs | Harmless but misleading noise | Omit it — Crossplane propagates the XR's namespace to every composed resource |
| Tags are a model, not a dict | Pydantic validation error downstream | The XRD used fixed `properties` instead of `additionalProperties` — fix the XRD (Pattern 10). `dict(tags) if tags else {}` works either way, but under the correct schema it is a no-op, not a fix |
| Fixed XRD properties for tags | `Input should be a valid string [input_value=None]` | Use `additionalProperties: type: string` |
| ProviderConfig ready before update | Resource not marked ready | Call `.ready = fnv1.READY_TRUE` AFTER `resource.update()` (the `Ready` enum lives in `fnv1`/`run_function_pb2` — **there is no `resource.READY_TRUE`**) |
| Observed resource by full name | `KeyError` or silent miss | Use composition KEY: `req.observed.resources["mysql"]` |
| Conditional by `is_ready` only | Resource deleted when dep flaps | Add `or resource_exists(req, "key")` |
| Readiness logic not exercised by composition test | Green test, then failure on the real control plane | Supply `observedResources` with `status.conditions` — the branch **is** reachable locally. See "Readiness branches need `observedResources`" above |
| Setting `managementPolicies=["*"]` | On a function: nothing, it matches the default. On an **expected** resource in a test: `exclude_unset=True` *keeps* it, and the assertion then fails against a render that correctly omits it | Omit it. `exclude_unset` only keeps it out while you do not set it |
| Wrong `.m.` placement | API not found | `azure.m.upbound.io` not `azurem.upbound.io` |
| Prefixed nested classes | Render crash: `ResourceGroupSpec`/`VirtualNetworkForProvider` don't exist | Nested classes are **unprefixed & module-qualified**: `rgv1beta1.Spec`, `rgv1beta1.ForProvider`, `rgv1beta1.ProviderConfigRef` — never `<Kind>Spec`/`<Kind>ForProvider` (datamodel-codegen names them generically per module) |
| New resource "verified" by a green test | Works locally, missing on the control plane | `assertResources` ignores resources you didn't list. Read `_output/composition_test/<ts>/<test>/render.log` **and** add the resource to the assertions |
| Resource appended after a guard clause | Resource silently absent for some inputs | The template's `return`-based guards gate everything below them. Give the new resource its own `if` block (see *Watch the early-return chain*) |
| Converting a function to the other layout | Build breaks on imports | Match the project: embedded uses `.model.` + `def compose(req, rsp)`, SDK uses `models.` + `RunFunction`. Run the probe script to see which |
| Non-namespaced (v1) model imported | Resource applies to the wrong API, `ProviderConfig` mismatch | Use the `.m.` path (`io.upbound.m.aws...`). The probe script flags v1 modules explicitly |

---

## Common Debugging Patterns

### Pydantic Validation Errors

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ResourceGroup
spec.forProvider.tags.Environment
  Input should be a valid string [input_value=None, input_type=NoneType]
```

**Fix**: Change XRD schema from fixed properties to `additionalProperties: type: string`
Then regenerate models: `up project build`

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Spec
  Extra inputs are not permitted [input_value=...]
```

**Fix**: Check provider version in `upbound.yaml` matches what you expect.
Regenerate models after updating: `up project build`

### Import Errors

```
ModuleNotFoundError: No module named 'models.io.example.platform.network.network'
```

**Fix**: The Kind segment is de-duplicated when the group's **leftmost** segment already equals the
lowercased Kind (group `network.platform.example.io`, Kind `Network`):
```python
# WRONG - "network" repeated
from models.io.example.platform.network.network import v1alpha1
# CORRECT - de-duplicated
from models.io.example.platform.network import v1alpha1
```
A sibling Kind in that same group is **not** de-duplicated
(`from models.io.example.platform.network.subnet import v1alpha1`). Don't infer the rule from one
resource — run `python3 "$SCRIPTS/probe_project.py" --project <project-root> <Kind>`.

```
ModuleNotFoundError: No module named 'models'
```

**Fix**: The `crossplane-models` package isn't installed. Ensure `.up/python` exists
(run `up project build` / `up dependency add`) and that `crossplane-models @ file:...`
is listed in the function/test `pyproject.toml`. (In the embedded layout the models
come from the `model` symlink instead, imported as `from .model.io...`.)

### struct_to_dict Errors

```
AttributeError: 'Struct' object has no attribute 'spec'
```

**Fix**: Add `resource.struct_to_dict()` wrapper:
```python
# WRONG
observed_xr = networkv1alpha1.Network(**req.observed.composite.resource)
# CORRECT
observed_xr = networkv1alpha1.Network(
    **resource.struct_to_dict(req.observed.composite.resource)
)
```

### Test Assertion Failures

```
AssertionError: Expected ResourceGroup not found in composed resources
```

**Debug steps**:
1. Render the composition manually to see actual output:
   ```bash
   up composition render apis/composition.yaml examples/xnetwork/example.yaml
   ```
2. Check if resource name matches: `name="rg-example-network"` vs actual `name="rg-mynetwork"`
3. Check `apiVersion` in test includes `.m.` suffix for v2

---

## Quick Reference: v1 → v2 Python Migration

| Change | v1 | v2 |
|--------|----|----|
| Azure import | `from models.io.upbound.azure.resources...` | `from models.io.upbound.m.azure.resources...` |
| AWS import | `from models.io.upbound.aws.ec2...` | `from models.io.upbound.m.aws.ec2...` |
| GCP import | `from models.io.upbound.gcp.compute...` | `from models.io.upbound.m.gcp.compute...` |
| XR parse | `XKind(**req.observed.composite.resource)` | `XKind(**resource.struct_to_dict(...))` |
| providerConfigRef | `{name: "default"}` | **remove it** — namespaced MRs default to `ClusterProviderConfig/default` |
| deletionPolicy | `deletionPolicy=rgv1beta1.Spec.DeletionPolicy.Delete` | **remove it** — `managementPolicies: ["*"]` is the default; only set it for a non-default policy such as `["Create","Observe","Update","LateInitialize"]` (orphan on delete) |
| metadata | `ObjectMeta(name="rg-...")` | unchanged — namespace is propagated automatically, don't add it |
| apiVersion in tests | `azure.upbound.io/v1beta1` | `azure.m.upbound.io/v1beta1` |
| XRD apiVersion | `apiextensions.crossplane.io/v1` | `apiextensions.crossplane.io/v2` |
| XRD scope | (implicit cluster) | `scope: Namespaced` |
| Connection secrets | `connectionSecretKeys` in XRD | Manual Secret composition in function |
| Helm secret namespace | `crossplane-system` | XR namespace (`parent_ns`) |

> The table above covers the **v1 → v2 API** migration; the SDK vs embedded layout
> (up v0.50.0+) is an orthogonal axis — see the note at the top of this file and
> "SDK vs embedded" in Part 1.
