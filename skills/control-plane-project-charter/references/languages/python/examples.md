# Python: Complete function examples

Two full functions, plus the project files they assume.

Language-agnostic rules are in [`control-plane-project-charter`](../../../SKILL.md); the Python index is [`../python.md`](../python.md).

---

## Complete Function Example: Azure Network (v2)

Full SDK implementation showing all patterns together:

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

        # Pattern 2: struct_to_dict bootstrap — the wire type is always a protobuf Struct
        observed_xr = networkv1alpha1.Network(
            **resource.struct_to_dict(req.observed.composite.resource)
        )

        # Extract from XR spec
        location = observed_xr.spec.location
        platform_name = observed_xr.metadata.name

        # Pattern 4: Tags conversion (Pydantic model → Python dict)
        base_tags = dict(observed_xr.spec.tags) if observed_xr.spec.tags else {}
        tags = {**base_tags, "ManagedBy": "crossplane"}

        # Pattern 3: forProvider only — v2 supplies namespace/policies/providerConfig
        desired_rg = rgv1beta1.ResourceGroup(
            metadata=k8s.ObjectMeta(
                name=f"rg-{platform_name}",                  # namespace: propagated automatically
            ),
            spec=rgv1beta1.Spec(
                forProvider=rgv1beta1.ForProvider(
                    location=location,
                    tags=tags,
                ),
            ),
        )
        resource.update(rsp.desired.resources["rg"], desired_rg)

        # Pattern 3: forProvider only
        desired_vnet = vnetv1beta1.VirtualNetwork(
            metadata=k8s.ObjectMeta(
                name=f"vnet-{platform_name}",                # namespace: propagated automatically
            ),
            spec=vnetv1beta1.Spec(
                forProvider=vnetv1beta1.ForProvider(
                    location=location,
                    addressSpace=[observed_xr.spec.cidr],
                    resourceGroupNameSelector=vnetv1beta1.ResourceGroupNameSelector(
                        matchControllerRef=True,
                    ),
                    tags=tags,
                ),
            ),
        )
        resource.update(rsp.desired.resources["vnet"], desired_vnet)

        return rsp
```

---

## Complete Function Example: Web Platform with Conditional Resources (v2)

```python
# functions/webplatform/function/fn.py
import grpc
from crossplane.function import logging, resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from crossplane.function.proto.v1 import run_function_pb2_grpc as grpcv1

from models.io.example.platform.webplatform import v1alpha1 as webv1alpha1
from models.io.example.platform.network import v1alpha1 as networkv1alpha1
from models.io.example.platform.compute import v1alpha1 as aksv1alpha1
from models.io.k8s.api.core import v1 as corev1
from models.io.k8s.apimachinery.pkg.apis.meta import v1 as k8s


def resource_exists(req: fnv1.RunFunctionRequest, key: str) -> bool:
    return key in req.observed.resources


def is_resource_ready(req: fnv1.RunFunctionRequest, key: str) -> bool:
    observed = req.observed.resources.get(key)
    if not observed or not observed.resource:
        return False
    ready = resource.get_condition(observed.resource, "Ready")
    synced = resource.get_condition(observed.resource, "Synced")
    return ready.status == "True" and synced.status == "True"


class FunctionRunner(grpcv1.FunctionRunnerService):
    """A FunctionRunner handles gRPC RunFunctionRequests."""

    def __init__(self):
        self.log = logging.get_logger()

    async def RunFunction(
        self, req: fnv1.RunFunctionRequest, _: grpc.aio.ServicerContext
    ) -> fnv1.RunFunctionResponse:
        rsp = response.to(req)

        observed_xr = webv1alpha1.WebPlatform(
            **resource.struct_to_dict(req.observed.composite.resource)
        )

        platform_name = observed_xr.metadata.name
        parent_ns = observed_xr.metadata.namespace           # Pattern 5: namespace propagation

        # Always create Network XR (no dependency)
        network = networkv1alpha1.Network(
            metadata=k8s.ObjectMeta(
                name=f"network-{platform_name}",
                namespace=parent_ns,                          # Pattern 5
            ),
            spec=networkv1alpha1.Spec(
                location=observed_xr.spec.location,
                cidr="10.0.0.0/16",
            ),
        )
        resource.update(rsp.desired.resources["network"], network)

        # Always create AKS XR (depends on Network but XR system handles ordering)
        aks = aksv1alpha1.AKS(
            metadata=k8s.ObjectMeta(
                name=f"aks-{platform_name}",
                namespace=parent_ns,                          # Pattern 5
            ),
            spec=aksv1alpha1.Spec(
                location=observed_xr.spec.location,
                nodeCount=observed_xr.spec.nodeCount or 2,
            ),
        )
        resource.update(rsp.desired.resources["aks"], aks)

        # Pattern 8: Safe conditional creation - create Helm release only after AKS exists
        if is_resource_ready(req, "aks") or resource_exists(req, "app-helm-release"):
            # Extract kubeconfig from AKS connection details
            kubeconfig = b""
            if "aks" in req.observed.resources:
                aks_cds = req.observed.resources["aks"].connection_details
                kubeconfig = aks_cds.get("kubeconfig", b"")

            if kubeconfig:
                # Pattern 9: Manual connection secret
                kubeconfig_secret = corev1.Secret(
                    metadata=k8s.ObjectMeta(
                        name=f"{platform_name}-kubeconfig",
                        namespace=parent_ns,                   # Pattern 5
                    ),
                    type="Opaque",
                    stringData={"kubeconfig": kubeconfig.decode("utf-8")},
                )
                resource.update(rsp.desired.resources["kubeconfig-secret"], kubeconfig_secret)

        return rsp
```

---

## upbound.yaml v2 Template

```yaml
apiVersion: meta.dev.upbound.io/v2alpha1
kind: Project
metadata:
  name: platform-network
spec:
  description: "Azure Network platform abstraction"
  license: Apache-2.0
  maintainer: Platform Team <platform@example.io>
  repository: xpkg.upbound.io/myorg/platform-network
  crossplane:
    version: ">=v2.0.0"
  apiDependencies:
  - type: k8s
    k8s:
      version: v1.33.0                               # Required for Secret models in E2E
  dependsOn:
  - apiVersion: pkg.crossplane.io/v1
    kind: Provider
    package: xpkg.upbound.io/upbound/provider-azure-network
    version: ">=v2.0.0"                              # v2.x required for namespaced MRs
  - apiVersion: pkg.crossplane.io/v1
    kind: Provider
    package: xpkg.upbound.io/upbound/provider-azure-resources
    version: ">=v2.0.0"
  - apiVersion: pkg.crossplane.io/v1
    kind: Function
    package: xpkg.upbound.io/crossplane-contrib/function-auto-ready
    version: ">=v0.2.1"
```

---

## pyproject.toml (SDK layout)

`up function generate` and `up test generate` write it; do not hand-write one. The single edit
you may need: if `.up/python` did not exist at generate time, the `dependencies` list lacks
`"crossplane-models @ file:./../../.up/python"`. Add that line, run `up project build`, and
re-run `setup_venv.py` ([`../python.md`](../python.md)).
