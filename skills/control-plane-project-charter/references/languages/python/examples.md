# Python: complete function examples

Two whole functions in the SDK layout, and the `upbound.yaml` they assume. The Python index is
[`../python.md`](../python.md).

## Azure network

A ResourceGroup and a VirtualNetwork that references it by selector:

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
        observed_xr = networkv1alpha1.Network(
            **resource.struct_to_dict(req.observed.composite.resource)
        )
        location = observed_xr.spec.location
        name = observed_xr.metadata.name
        tags = {**(dict(observed_xr.spec.tags) if observed_xr.spec.tags else {}), "ManagedBy": "crossplane"}

        # forProvider only; metadata.name only because the tests assert stable names.
        desired_rg = rgv1beta1.ResourceGroup(
            metadata=k8s.ObjectMeta(name=f"rg-{name}"),
            spec=rgv1beta1.Spec(forProvider=rgv1beta1.ForProvider(location=location, tags=tags)),
        )
        resource.update(rsp.desired.resources["rg"], desired_rg)

        desired_vnet = vnetv1beta1.VirtualNetwork(
            metadata=k8s.ObjectMeta(name=f"vnet-{name}"),
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

## Web platform: child XRs and a gated Helm release

Two child XRs, then a Helm ProviderConfig and Release once the cluster is ready, or once the
release already exists. The child `Cluster` XR's own composition writes the Secret
`<cluster-name>-kubeconfig`; a v2 XR publishes no connection details.

```python
# functions/webplatform/function/fn.py
import grpc
from crossplane.function import logging, resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from crossplane.function.proto.v1 import run_function_pb2_grpc as grpcv1

from models.io.k8s.apimachinery.pkg.apis.meta import v1 as k8s
from models.io.crossplane.m.helm.providerconfig import v1beta1 as helmpcv1beta1
from models.io.crossplane.m.helm.release import v1beta1 as releasev1beta1
from models.io.example.platform.webplatform import v1alpha1 as webv1alpha1
from models.io.example.platform.network import v1alpha1 as networkv1alpha1  # network.platform.example.io
from models.io.example.platform.cluster import v1alpha1 as clusterv1alpha1  # cluster.platform.example.io


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
        name = observed_xr.metadata.name

        # Child XRs: no metadata.namespace, Crossplane sets the XR's.
        resource.update(rsp.desired.resources["network"], networkv1alpha1.Network(
            spec=networkv1alpha1.Spec(location=observed_xr.spec.location, cidr="10.0.0.0/16"),
        ))
        resource.update(rsp.desired.resources["cluster"], clusterv1alpha1.Cluster(
            metadata=k8s.ObjectMeta(name=f"{name}-cluster"),  # fixed: the kubeconfig Secret is named after it
            spec=clusterv1alpha1.Spec(
                location=observed_xr.spec.location,
                nodeCount=observed_xr.spec.nodeCount or 2,
            ),
        ))

        # Ready or already exists, so a flapping cluster does not delete the release.
        if is_resource_ready(req, "cluster") or resource_exists(req, "app"):
            resource.update(rsp.desired.resources["helm-config"], helmpcv1beta1.ProviderConfig(
                metadata=k8s.ObjectMeta(name=f"{name}-helm"),
                spec=helmpcv1beta1.Spec(credentials=helmpcv1beta1.Credentials(
                    source="Secret",
                    secretRef=helmpcv1beta1.SecretRef(
                        name=f"{name}-cluster-kubeconfig",
                        namespace=observed_xr.metadata.namespace,  # a spec value: the XR's namespace
                        key="kubeconfig",
                    ),
                )),
            ))
            rsp.desired.resources["helm-config"].ready = fnv1.READY_TRUE  # auto-ready cannot judge it
            resource.update(rsp.desired.resources["app"], releasev1beta1.Release(
                spec=releasev1beta1.Spec(
                    forProvider=releasev1beta1.ForProvider(chart=releasev1beta1.Chart(
                        name="podinfo",
                        repository="https://stefanprodan.github.io/podinfo",
                        version="6.5.0",
                    )),
                    # The project composes this ProviderConfig, so the reference is warranted.
                    providerConfigRef=releasev1beta1.ProviderConfigRef(
                        kind="ProviderConfig", name=f"{name}-helm",
                    ),
                ),
            ))
        return rsp
```

The Helm model classes were checked against a generated `.up/python` tree; the child XR classes
depend on your XRDs.

## upbound.yaml

```yaml
apiVersion: meta.dev.upbound.io/v2alpha1
kind: Project
metadata:
  name: platform-network
spec:
  description: Azure network platform abstraction
  license: Apache-2.0
  maintainer: Platform Team <platform@example.io>
  repository: xpkg.upbound.io/myorg/platform-network
  crossplane:
    version: ">=v2.0.0"
  apiDependencies:
  - type: k8s
    k8s:
      version: v1.33.0                   # the k8s core models (Secret)
  dependsOn:
  - apiVersion: pkg.crossplane.io/v1
    kind: Provider
    package: xpkg.upbound.io/upbound/provider-azure-network
    version: ">=v2.0.0"                  # v2 providers serve the namespaced .m. APIs
  - apiVersion: pkg.crossplane.io/v1
    kind: Provider
    package: xpkg.upbound.io/upbound/provider-family-azure   # ResourceGroup
    version: ">=v2.0.0"
  - apiVersion: pkg.crossplane.io/v1
    kind: Function
    package: xpkg.upbound.io/crossplane-contrib/function-auto-ready
    version: ">=v0.2.1"
```

## pyproject.toml

`up function generate` and `up test generate` write it; do not hand-write one. The single edit
you may need is adding a missing `crossplane-models` line ([`../python.md`](../python.md#layout-sdk-or-embedded)).
