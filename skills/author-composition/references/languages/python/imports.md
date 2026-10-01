# Python: Import paths

Deriving the import path for any Kind, and the class names inside a generated model.

Language-agnostic rules are in [`../../charter.md`](../../charter.md); the Python index is [`../python.md`](../python.md).

---

# Part 2 — Import paths

## Import Path Formula

**Never guess an import path — resolve it.** One command prints the project's layout, the right
import prefix, the exact import line, and the model's class names:

```bash
python3 "$SCRIPTS/probe_project.py" --project <project-root> Bucket StorageBucket
# functions/compose-bucket  layout=embedded  import prefix='.model.'
# Bucket:
#     from .model.io.upbound.m.aws.s3.bucket import v1beta1  <- USE THIS
#       classes (module-qualified, UNPREFIXED): ForProvider, ProviderConfigRef, Spec, Rule, ...
```

The underlying rule is **one rule for XRs and managed resources alike**: reverse the API group,
then append the lowercased Kind — **unless the group's *leftmost* segment already equals it**,
in which case the segment is not repeated. Leftmost matters: after reversal that segment ends
up last in the path, and the generator compares against *that*. `network.platform.example.io`
de-duplicates because the group starts with `network`; the fact that it ends with `io` is
irrelevant.

Rows marked ✓ were observed in a real `.up/python/models`; the rest follow from the generator
and were not observed locally:

| API group + Kind | Model module | |
|---|---|---|
| `platform.example.com` + `StorageBucket` | `com/example/platform/storagebucket/v1alpha1` | Kind appended |
| `s3.aws.m.upbound.io` + `Bucket` | `io/upbound/m/aws/s3/bucket/v1beta1` | Kind appended |
| `azure.m.upbound.io` + `ResourceGroup` | `io/upbound/m/azure/resourcegroup/v1beta1` | Kind appended |
| `network.platform.example.io` + `Subnet` | `io/example/platform/network/subnet/v1alpha1` | Kind appended |
| `network.platform.example.io` + `Network` | `io/example/platform/network/v1alpha1` | **de-duplicated** |

That de-duplication is the trap: it makes one XRD look "group-level" and every sibling Kind in the
same group look different. Do not generalize from a single example — **run the script.**

Fallback without the script:

```bash
find .up/python/models -type d -name storagebucket   # -> com/example/platform/storagebucket
grep '^class ' .up/python/models/com/example/platform/storagebucket/v1alpha1.py
```


## Pattern 1: Import Path Generation

### Rule: reversed API group + lowercased Kind, de-duplicated

```
Input:
  API Group: platform.example.com
  Kind:      StorageBucket
  Version:   v1alpha1

Transformation:
  Group reversed:  com.example.platform
  Append Kind:     com.example.platform.storagebucket
  Version module:  v1alpha1

Output: from models.com.example.platform.storagebucket import v1alpha1
```

**The one wrinkle:** if the group's *last* segment already equals the lowercased Kind, it is not
repeated (the generator compares the group's leftmost segment against the Kind).

| API group | Kind | Module |
|---|---|---|
| `network.platform.example.io` | `Network` | `io/example/platform/network/v1alpha1` (de-duplicated) |
| `network.platform.example.io` | `Subnet` | `io/example/platform/network/subnet/v1alpha1` |

De-duplication is easy to over-generalise from a single example: a `Network` XRD in a
`...network` group collapses, but sibling Kinds in the same group do **not**. The rule is uniform
for XRs, composed child XRs, and MRs alike.

### Don't derive it — resolve it

```bash
python3 "$SCRIPTS/probe_project.py" --project <project-root> StorageBucket Bucket
```

prints the project's layout, the correct import prefix for it, the exact import line (flagging
non-namespaced v1 modules and Kinds defined by more than one group), and the model's class names.

### Real Examples

```python
# XR: platform.example.com/v1alpha1, Kind StorageBucket
from models.com.example.platform.storagebucket import v1alpha1

# XR: network.platform.example.io/v1alpha1, Kind Network (de-duplicated)
from models.io.example.platform.network import v1alpha1 as networkv1alpha1

# MR: s3.aws.m.upbound.io/v1beta1/Bucket (v2 AWS)
from models.io.upbound.m.aws.s3.bucket import v1beta1 as bucketv1beta1

# MR: azure.m.upbound.io/v1beta1/ResourceGroup (v2 Azure)
from models.io.upbound.m.azure.resourcegroup import v1beta1 as rgv1beta1

# MR: network.azure.m.upbound.io/v1beta1/VirtualNetwork (v2 Azure)
from models.io.upbound.m.azure.network.virtualnetwork import v1beta1 as vnetv1beta1

# MR: ec2.aws.m.upbound.io/v1beta1/VPC (v2 AWS)
from models.io.upbound.m.aws.ec2.vpc import v1beta1 as vpcv1beta1

# MR: compute.gcp.m.upbound.io/v1beta1/Network (v2 GCP)
from models.io.upbound.m.gcp.compute.network import v1beta1 as gcpnetv1beta1

# k8s core (for Secrets in v2 manual connection secret pattern)
from models.io.k8s.api.core import v1 as corev1
from models.io.k8s.apimachinery.pkg.apis.meta import v1 as k8s
```

> **Embedded layout:** identical paths with the `.model.` prefix, e.g.
> `from .model.com.example.platform.storagebucket import v1alpha1`.

### Finding Import Paths in Generated Models

After `up project build`, models are at `.up/python/models/`. Use:

```bash
# Find model for a specific resource kind
find .up/python/models -name "*.py" | grep -i "virtualnetwork"

# List all available Azure v2 resource models
find .up/python/models/io/upbound/m/azure -type d | head -20

# Check the actual model file to verify class names
head -30 .up/python/models/io/upbound/m/azure/resourcegroup/v1beta1.py
```
