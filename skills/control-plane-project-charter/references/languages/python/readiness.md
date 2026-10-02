# Python: Cross-resource references, readiness and secrets

Reading observed resources, gating on readiness without deleting what you already made, and writing a connection secret by hand.

Language-agnostic rules are in [`../../CHARTER.md`](../../../SKILL.md); the Python index is [`../python.md`](../python.md).

---

## Pattern 6: Connection Details (Access by Composition KEY)

```python
from crossplane.function import resource, response

# Inside RunFunction (SDK); embedded: same body in compose(req, rsp).
# rsp = response.to(req) already called.
observed_xr = ...

# Access observed resources by COMPOSITION KEY (the string in rsp.desired.resources["KEY"])
# NOT by the full resource name
if "mysql" in req.observed.resources:          # KEY is "mysql", not "mysql-myplatform-abc"
    observed_mysql_resource = req.observed.resources["mysql"]
    mysql_mr = mysqlv1beta2.FlexibleServer(
        **resource.struct_to_dict(observed_mysql_resource.resource)
    )

    connection_data = {}

    # From spec (always available once resource is created)
    if mysql_mr.spec.forProvider.administratorLogin:
        connection_data["username"] = (
            mysql_mr.spec.forProvider.administratorLogin.encode("utf-8")
        )

    # From atProvider (available once cloud resource exists)
    if mysql_mr.status and mysql_mr.status.atProvider:
        if mysql_mr.status.atProvider.fqdn:
            connection_data["host"] = mysql_mr.status.atProvider.fqdn.encode("utf-8")

    # From connection_details (provider-populated secrets)
    if observed_mysql_resource.connection_details:
        pwd_key = "attribute.administrator_password"
        if pwd_key in observed_mysql_resource.connection_details:
            connection_data["password"] = observed_mysql_resource.connection_details[pwd_key]

    # Propagate to XR
    if connection_data:
        rsp.desired.composite.connection_details.update(connection_data)
```

---

## Pattern 7: ProviderConfig Readiness

For resources that act as ProviderConfigs (Helm, Kubernetes provider), mark ready AFTER update:

```python
from crossplane.function import resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1

# Inside RunFunction (SDK); embedded: same body in compose(req, rsp).
# rsp = response.to(req) already called.
observed_xr = ...
parent_ns = observed_xr.metadata.namespace

helm_provider_config = helmproviderv1beta1.ProviderConfig(
    metadata=k8s.ObjectMeta(name="default"),
    spec=helmproviderv1beta1.Spec(
        credentials=helmproviderv1beta1.Credentials(
            source="Secret",
            secretRef=helmproviderv1beta1.SecretRef(
                name=f"{observed_xr.metadata.name}-kubeconfig",
                namespace=parent_ns,                 # ✅ v2: XR namespace (not crossplane-system)
                key="kubeconfig",
            ),
        ),
    ),
)

resource.update(rsp.desired.resources["helm-provider-config"], helm_provider_config)
rsp.desired.resources["helm-provider-config"].ready = fnv1.READY_TRUE
```

> **Order does not matter here.** `resource.update()` writes only `r.resource`; it never
> touches `r.ready`. Measured on function-sdk-python 0.11.0 and 0.5.0: setting `ready` before or
> after `update()` both leave `READY_TRUE`. Write-then-annotate is a fine habit, but nothing
> depends on it.

> **The readiness enum is `fnv1.READY_TRUE`** (from `crossplane.function.proto.v1.run_function_pb2 as fnv1`) — **not** `resource.READY_TRUE`. The `resource` module has no such symbol; `resource.READY_TRUE` raises `AttributeError` (verified against `crossplane-function-sdk-python` v0.11.0). `fnv1.Ready.READY_TRUE` also works.
>
> **A readiness branch is empty-by-default, not untestable.** A render starts with no observed
> resources *unless the test sets `spec.observedResources`*. So `if <observed is ready>: ....ready = fnv1.READY_TRUE`
> is dead in a test that omits that field and live in one that sets it — write that test. It
> proves your branch logic given the status you wrote; it does not prove a provider ever reports
> that status. For that, `--e2e` or a live apply.

---

## Pattern 8: Safe Conditional Creation

**Problem**: Creating a resource only when its dependency is `Ready` causes deletion when the
dependency temporarily flaps (restarts, reconciles). This triggers cascading deletions.

**Solution**: Create if READY OR ALREADY EXISTS:

```python
def resource_exists(req: fnv1.RunFunctionRequest, composition_key: str) -> bool:
    """True if the resource was already created (exists in observed state)."""
    return composition_key in req.observed.resources

def is_resource_ready(req: fnv1.RunFunctionRequest, composition_key: str) -> bool:
    """True if the resource is synced and ready."""
    observed = req.observed.resources.get(composition_key)
    if not observed or not observed.resource:
        return False
    ready = resource.get_condition(observed.resource, "Ready")
    synced = resource.get_condition(observed.resource, "Synced")
    return ready.status == "True" and synced.status == "True"


# Inside RunFunction (SDK); embedded: same body in compose(req, rsp).
# rsp = response.to(req) already called.
# ... create AKS cluster ...
resource.update(rsp.desired.resources["aks-cluster"], desired_aks)

# SAFE: Create Helm release only when AKS is ready OR Helm release already exists
if is_resource_ready(req, "aks-cluster") or resource_exists(req, "helm-release"):
    helm_release = helmproviderv1beta1.Release(...)
    resource.update(rsp.desired.resources["helm-release"], helm_release)
```

**Anti-pattern (causes deletion)**:
```python
# ❌ WRONG - deletes helm-release whenever AKS restarts
if is_resource_ready(req, "aks-cluster"):
    resource.update(rsp.desired.resources["helm-release"], helm_release)
```

---

## Pattern 9: Manual Connection Secret (v2)

v2 removes automatic `connectionSecretKeys` from XRDs. Functions must create Secrets manually.

```python
from models.io.k8s.api.core import v1 as corev1

# Inside RunFunction (SDK); embedded: same body in compose(req, rsp).
# rsp = response.to(req) already called.
observed_xr = ...
parent_ns = observed_xr.metadata.namespace
platform_name = observed_xr.metadata.name

# Gather connection data from observed resources
connection_data = {}

if "mysql" in req.observed.resources:
    observed_mysql = req.observed.resources["mysql"]
    mysql_mr = mysqlv1beta2.FlexibleServer(
        **resource.struct_to_dict(observed_mysql.resource)
    )
    if mysql_mr.status and mysql_mr.status.atProvider and mysql_mr.status.atProvider.fqdn:
        connection_data["host"] = mysql_mr.status.atProvider.fqdn

# Create the connection Secret in the XR's namespace
if connection_data:
    connection_secret = corev1.Secret(
        metadata=k8s.ObjectMeta(
            name=f"{platform_name}-connection",
            namespace=parent_ns,                     # ✅ XR namespace
            labels={
                "crossplane.io/composite": platform_name,
            },
        ),
        type="connection.crossplane.io/v1alpha1",
        stringData=connection_data,                 # Plain text - k8s auto-base64
    )
    resource.update(rsp.desired.resources["connection-secret"], connection_secret)
```

**XRD v2 config** (no connectionSecretKeys):
```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
spec:
  scope: Namespaced
  # connectionSecretKeys REMOVED in v2 - use manual Secret composition
```

---

## Verify what you actually rendered

[`../CHARTER.md` §8](../../../SKILL.md#8-a-green-run-is-not-evidence) explains why a green suite
is not evidence. These are the Python-specific artifacts that are.

**1. Read the render.** This is the ground truth for what the function emits:

```bash
up test run "tests/test-<name>" --function-logs
# -> Test artifacts written to _output/composition_test/<timestamp>
```

| File | Contains |
|---|---|
| `_output/composition_test/<ts>/<test>/render.log` | the rendered XR (incl. `spec.crossplane.resourceRefs`) and **every** composed resource as applied |
| `_output/composition_test/<ts>/<test>/<function>.log` | that function's container logs — where a Python traceback or `self.log` output lands |

Read `render.log` and confirm each resource you intended is present, with the fields you meant.
Add `--debug` to also stream it to stderr.

**2. Add the new resource to `assertResources`.** Until you do, it is untested — see Part 4
for the assertion syntax. The XR's `status.conditions` message in `render.log`
(`Unready resources: bucket, lifecycle, pab, and 2 more`) is a quick checklist of what rendered.

### Watch the early-return chain

Template functions are written as a sequence of guard clauses:

```python
if "bucket" not in req.observed.resources:
    return                      # nothing observed yet
if "crossplane.io/external-name" not in observed_bucket.metadata.annotations:
    return                      # external name not assigned yet
if not params.versioning:
    return                      # versioning disabled
```

Anything you **append at the end inherits every guard above it** — a resource added after the
`versioning` check silently disappears whenever `versioning: false`, and no composition test will
tell you. When a new resource has its own condition, give it its own `if` block rather than adding
another `return`, and place it above unrelated guards.

### Readiness branches need `observedResources` — they are not untestable

Composition tests render with only the observed resources you hand them, and the list is
empty unless the test sets `spec.observedResources`. So a branch gated on `is_ready` or on
`req.observed.resources` is dead in a test that omits that field, and **reachable in one that
sets it**. Write that test.

What it proves is narrower than it looks: your branch logic, given the status you wrote into
the fixture. It does not prove a provider ever reports that status — for that, `--e2e` or a
real control plane.
