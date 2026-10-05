# KCL: function structure

Module layout, the entry point, a domain module, and the helpers every resource uses. The KCL
index is [`../kcl.md`](../kcl.md); conditionals, comprehensions and references are in
[`patterns-logic.md`](patterns-logic.md).

## Module layout

```text
functions/<composition-name>/
├── main.k        # entry point: read the XR, build the config, call the modules
├── kcl.mod       # dependencies and module metadata
├── network.k     # one module per domain: VPCs, subnets, gateways
├── security.k    # security groups, policies
└── storage.k     # buckets, volumes
```

- `main.k` orchestrates and nothing else.
- One module per domain; private functions start with `_`.
- A single `main.k` is fine for a small function. Split when it grows.

## Entry point (`main.k`)

```kcl
import models.io.upbound.platform.myxrd.v1alpha1 as myxrd   # your XR: models.io.<reversed-group>.<version>
import network
import security
import storage

oxr = option("params").oxr      # observed composite resource
ocds = option("params").ocds    # observed composed resources, keyed by composition resource name
dxr = option("params").dxr      # desired composite resource
dcds = option("params").dcds    # desired composed resources

# The key every composed resource is stored under; Crossplane tracks the resource by it.
_metadata = lambda name: str -> any {
    { annotations = { "krm.kcl.dev/composition-resource-name" = name }}
}

# Kubernetes label values: 63 characters, alphanumerics and - _ .
_sanitizeLabels = lambda tags: {str:str} -> {str:str} {
    {k: v.replace("/", "-").replace(":", "-")[:63] for k, v in tags}
}

# Typed access to the XR. A missing field is a type error here, not a runtime surprise.
_oxrMeta = myxrd.MyResource.metadata{**oxr.metadata}
_oxrSpec = myxrd.MyResource.spec{**oxr.spec}

# One config object for every module: fewer signatures, one place to change.
_config = {
    metadata = _metadata
    sanitizeLabels = _sanitizeLabels
    resourceName = _oxrMeta.name
    region = _oxrSpec.region
    cidrBlock = _oxrSpec.cidrBlock
    createVPC = _oxrSpec.createVPC if _oxrSpec.createVPC not in [None, Undefined] else True
    zones = _oxrSpec.zones or []
    tags = _oxrSpec.tags or {}
}

# items is the output, and a top-level name is immutable: never assign it twice.
items = network.generateNetworkResources(_config) \
    + security.generateSecurityResources(_config) \
    + storage.generateStorageResources(_config)
```

`items` is what function-kcl reads. Name every other top-level variable with a leading `_`:
reassigning a top-level name fails with `ImmutableError … Can not change the value of 'items',
because it was declared immutable`.

**An absent field is `Undefined`, not `None`** (measured with kcl 0.10.4, typed and untyped
access alike), so `x if x != None else default` never applies the default: it yields `Undefined`
and the field silently disappears. Test both, as `createVPC` does above. `x or default` is fine
where a falsy value may take the default (strings, lists, maps), never for a boolean.

## A domain module (`network.k`)

```kcl
"""Network resources: VPC, subnets, gateways."""
import models.io.upbound.awsm.ec2.v1beta1 as ec2v1beta1

_generateVPC = lambda config: {str: any} -> [any] {
    [
        ec2v1beta1.VPC{
            metadata = config.metadata("vpc") | {
                labels = config.sanitizeLabels(config.tags)
            }
            spec.forProvider = {
                region = config.region
                cidrBlock = config.cidrBlock
                enableDnsHostnames = True
                tags = config.tags | { Name = "vpc-${config.resourceName}" }
            }
        }
    ] if config.createVPC else []
}

# The public entry point main.k calls. Always returns a list, empty when nothing applies.
generateNetworkResources = lambda config: {str: any} -> [any] {
    _generateVPC(config) + _generateSubnets(config)
}
```

Every resource sets `forProvider` and nothing else unless the project asks
([charter §5](../../../SKILL.md#5-crossplane-v2-what-a-composed-resource-actually-needs)), and
merges `config.metadata("<key>")` into its metadata: the key is the composition resource name,
so it must be unique per resource and stable across runs (renaming it orphans the live resource).
Set `metadata.name` only when the resource needs a stable external name.
