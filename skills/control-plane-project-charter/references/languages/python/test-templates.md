# Python: test templates

The composition-test and E2E-test scaffolds, annotated. What the suite must *contain* is in [`tests.md`](tests.md).

Language-agnostic rules are in [`../../CHARTER.md`](../../../SKILL.md); the Python index is [`../python.md`](../python.md).

---

## Composition Test Template (`tests/test-<n>/test/__main__.py`)

```python
import yaml
from models.io.upbound.dev.meta.compositiontest import v1alpha1 as compositiontest
from models.io.k8s.apimachinery.pkg.apis.meta import v1 as k8s
from models.io.upbound.m.azure.resourcegroup import v1beta1 as rgv1beta1
from models.io.upbound.m.azure.network.virtualnetwork import v1beta1 as vnetv1beta1

# Expected ResourceGroup assertion
expected_rg = rgv1beta1.ResourceGroup(
    apiVersion="azure.m.upbound.io/v1beta1",          # include in tests, .m. for v2
    kind="ResourceGroup",
    metadata=k8s.ObjectMeta(
        name="rg-example-network",
        namespace="default",                           # v2: namespace in test metadata
    ),
    spec=rgv1beta1.Spec(
        forProvider=rgv1beta1.ForProvider(
            location="West Europe",
            tags={"Environment": "dev"},
        ),
    ),
)

# Expected VirtualNetwork assertion
expected_vnet = vnetv1beta1.VirtualNetwork(
    apiVersion="network.azure.m.upbound.io/v1beta1",  # verify version in .up/python/models
    kind="VirtualNetwork",
    metadata=k8s.ObjectMeta(name="vnet-example", namespace="default"),
    spec=vnetv1beta1.Spec(
        forProvider=vnetv1beta1.ForProvider(
            location="West Europe",
            addressSpace=["10.0.0.0/16"],
        ),
    ),
)

# Compose the test
test_network = compositiontest.CompositionTest(
    metadata=k8s.ObjectMeta(name="test-xnetwork", namespace="default"),
    spec=compositiontest.Spec(
        compositionPath="apis/xnetworks/composition.yaml",
        xrPath="examples/xnetwork/example.yaml",
        xrdPath="apis/xnetworks/definition.yaml",
        timeoutSeconds=120,
        validate=False,  # scaffold/lab default
        assertResources=[
            # asserted resources: exclude_unset=True (partial match)
            expected_rg.model_dump(by_alias=True, exclude_unset=True, exclude={"spec": {"deletionPolicy"}}),
            expected_vnet.model_dump(by_alias=True, exclude_unset=True, exclude={"spec": {"deletionPolicy"}}),
            # `assertResources` matches the COMPOSITE too - this is how you assert
            # composition outputs. There is no `assertComposite`/`assertStatus` field,
            # and its absence does NOT mean composite assertions are unsupported.
            {
                "apiVersion": "platform.example.com/v1alpha1",
                "kind": "XNetwork",
                "metadata": k8s.ObjectMeta(name="test-xnetwork", namespace="default")
                               .model_dump(by_alias=True, exclude_unset=True),
                "status": {"vnetId": "/subscriptions/.../virtualNetworks/test-xnetwork"},
            },
        ],
    ),
)

# Top-level test: exclude_none=True. Runner expects an "items" array.
output = {"items": [test_network.model_dump(by_alias=True, exclude_none=True)]}
print(yaml.dump(output))
```

> **Embedded layout:** `tests/test-<n>/main.py` with `.model.` import prefixes (e.g.
> `from .model.io.upbound.dev.meta.compositiontest import v1alpha1`) and a
> `model -> ../../.up/python/models` symlink. **Define the test objects at module level and
> print nothing.** The runner (`uptest-pyrunner`) walks the module with `inspect.getmembers`
> and collects every object that has both `apiVersion` and `kind`, then wraps them in `items`
> itself.
>
> **Do not end the module with `items = [test.model_dump(...)]`.** A list of plain dicts has
> no `apiVersion` attribute, so the runner skips it and the generated `test.yaml` comes out
> empty.
>
> **Gotcha from the same mechanism:** the runner collects *any* module-level object with
> `apiVersion` and `kind`, so `from .resources import observed_bucket` emits that Bucket into
> `test.yaml` as a bogus test item. Use `from . import resources` — which is what the project
> templates do — and reference `resources.observed_bucket`.

---

## E2E Test Template (`tests/e2etest-<n>/test/__main__.py`)

The `E2ETest` spec has **no** `compositionPath`/`xrPath`/`xrdPath`. It uses `manifests` (resources under test) + `extraResources` (prerequisites: ProviderConfig and any credential Secret). Prefer web identity; the example below shows a static-Secret ProviderConfig for the case where a project requires one (credential Secrets use `stringData` - plain text, Kubernetes auto-base64-encodes).

```python
import os
import yaml
from models.io.k8s.api.core import v1 as corev1
from models.io.k8s.apimachinery.pkg.apis.meta import v1 as k8s
from models.io.upbound.dev.meta.e2etest import v1alpha1 as e2etest
from models.io.upbound.m.azure.clusterproviderconfig import v1beta1 as pcv1beta1
from models.io.example.platform.network import v1alpha1 as networkv1alpha1

# UP_-prefixed: only these cross into the generation container. See
# CHARTER.md section 7. Indexing, not .get, so a missing value fails here
# rather than at the provider twenty minutes later.
azure_creds = os.environ["UP_AZURE_CREDENTIALS"]

# Credential Secret - stringData is plain text.
azure_secret = corev1.Secret(
    apiVersion="v1",
    kind="Secret",
    metadata=k8s.ObjectMeta(name="azure-creds", namespace="crossplane-system"),
    stringData={"credentials": azure_creds},
)

# The ProviderConfig the XR references.
provider_config = pcv1beta1.ClusterProviderConfig(
    apiVersion="azure.m.upbound.io/v1beta1",
    kind="ClusterProviderConfig",
    metadata=k8s.ObjectMeta(name="azure-provider"),
    spec=pcv1beta1.Spec(
        credentials=pcv1beta1.Credentials(
            source="Secret",
            secretRef=pcv1beta1.SecretRef(
                name="azure-creds", namespace="crossplane-system", key="credentials",
            ),
        ),
    ),
)

# The XR under test (mirror your examples/<xr>/example.yaml).
network_xr = networkv1alpha1.Network(
    apiVersion="network.platform.example.io/v1alpha1",
    kind="Network",
    metadata=k8s.ObjectMeta(name="example-network", namespace="default"),
    spec=networkv1alpha1.Spec(
        location="West Europe",
        cidr="10.0.0.0/16",
        tags={"Environment": "dev"},
    ),
)
# No providerConfigRef on the XR. A v2 XR model has no such field — `spec` is
# ['crossplane', 'parameters'] — so `networkv1alpha1.ProviderConfigRef(...)` raises
# AttributeError, and passing it as a dict is silently dropped. Composed managed resources
# default to ClusterProviderConfig/default on their own.

test_e2e = e2etest.E2ETest(
    metadata=k8s.ObjectMeta(name="e2etest-xnetwork"),
    spec=e2etest.Spec(
        crossplane=e2etest.Crossplane(
            autoUpgrade=e2etest.AutoUpgrade(channel="Stable"),  # track a channel
        ),
        defaultConditions=["Ready"],
        extraResources=[                    # prerequisites - applied first
            azure_secret.model_dump(by_alias=True, exclude_none=True),
            provider_config.model_dump(by_alias=True, exclude_none=True),
        ],
        manifests=[                         # resources under test (≥1 required)
            network_xr.model_dump(by_alias=True, exclude_none=True),
        ],
        skipDelete=False,
        timeoutSeconds=4500,                # size to the real resources
    ),
)

output = {"items": [test_e2e.model_dump(by_alias=True, exclude_none=True)]}
print(yaml.dump(output))
```

**If asserting on k8s `Secret`/core models, add the k8s API dependency to `upbound.yaml`:**
```yaml
spec:
  apiDependencies:
  - type: k8s
    k8s:
      version: v1.33.0
```
