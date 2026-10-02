# KCL: composition function patterns

Module layout, the entry point, and the KCL syntax for each composition pattern.

Language-agnostic rules are in [`../../CHARTER.md`](../../../SKILL.md); the KCL index is [`../kcl.md`](../kcl.md).

---

## Pattern 1: Module Organization

**When to use**: Every composition function

### Structure

```text
functions/<composition-name>/
├── main.k              # Entry point - orchestration only
├── kcl.mod             # Dependencies and module metadata
├── <domain1>.k         # Module for domain 1 (e.g., network.k)
├── <domain2>.k         # Module for domain 2 (e.g., storage.k)
└── <domain3>.k         # Module for domain 3 (e.g., security.k)
```

### Key Principles

- **main.k is orchestration only**: Parameter extraction, config building, module coordination
- **One module per domain**: Each .k file handles one logical resource type
- **Public/Private conventions**: Private functions start with `_`
- **Single responsibility**: Each module has one clear purpose

### Example Module Naming

| Module | Purpose |
|--------|---------|
| `network.k` | VPCs, subnets, gateways |
| `security.k` | Security groups, policies |
| `storage.k` | S3, EBS, storage accounts |
| `compute.k` | EC2, VMs, instances |
| `database.k` | RDS, SQL databases |

**Note**: For simple projects, a single `main.k` file is acceptable. Split when complexity grows.

---

## Pattern 2: Entry Point Structure (main.k)

### Canonical Template

```kcl
# ========================================
# 1. IMPORTS - Type Models
# ========================================
import models.io.upbound.awsm.ec2.v1beta1 as ec2v1beta1
import models.io.upbound.platform.myxrd.v1alpha1 as myxrd
import models.k8s.apimachinery.pkg.apis.meta.v1 as metav1

# Import your modules
import network
import security
import storage

# ========================================
# 2. ACCESS COMPOSITION PARAMETERS
# ========================================
oxr = option("params").oxr      # observed composite resource
ocds = option("params").ocds    # observed composed resources
dxr = option("params").dxr      # desired composite resource
dcds = option("params").dcds    # desired composed resources

# ========================================
# 3. HELPER FUNCTIONS
# ========================================
_metadata = lambda name: str -> any {
    """Creates metadata with composition resource name annotation (CRITICAL)"""
    { annotations = { "krm.kcl.dev/composition-resource-name" = name }}
}

_sanitizeLabels = lambda tags: {str:str} -> {str:str} {
    """Sanitizes label values for Kubernetes constraints"""
    {k: v.replace("/", "-").replace(":", "-")[:63] for k, v in tags}
}

# ========================================
# 4. EXTRACT PARAMETERS FROM XR
# ========================================
oxrMeta = myxrd.MyResource.metadata{**oxr.metadata}
oxrSpec = myxrd.MyResource.spec{**oxr.spec}

resourceName = oxrMeta.name
region = oxrSpec.region
enableFeature = oxrSpec.enableFeature if oxrSpec.enableFeature != None else False
tags = oxrSpec.tags or {}
items = oxrSpec.items or []

# ========================================
# 5. BUILD CONFIGURATION OBJECT
# ========================================
config = {
    # Helper functions
    metadata = _metadata
    sanitizeLabels = _sanitizeLabels

    # Extracted parameters
    resourceName = resourceName
    region = region
    enableFeature = enableFeature
    tags = tags
    items = items
}

# ========================================
# 6. GENERATE RESOURCES (ORCHESTRATION)
# ========================================
items = \
    network.generateNetworkResources(config) + \
    security.generateSecurityResources(config) + \
    storage.generateStorageResources(config)
```

### Key Points

- Clear section separation with comments
- Helper functions defined before use
- Typed model extraction for safety
- Single configuration object passed to all modules
- One-line orchestration at the end

---

## Pattern 3: Module Structure

### Canonical Template

```kcl
"""
Module: <domain>.k

Description:
    Generates <domain> resources for the composition.
    Handles <specific responsibilities>.
"""

# ========================================
# IMPORTS
# ========================================
import models.io.upbound.awsm.ec2.v1beta1 as ec2v1beta1

# ========================================
# PRIVATE HELPER FUNCTIONS (start with _)
# ========================================
_calculateValue = lambda input: int -> int {
    """Helper function description"""
    input * 2
}

# ========================================
# PRIVATE RESOURCE GENERATORS (start with _)
# ========================================
_generateVPC = lambda config: {str: any} -> [any] {
    """
    Generates VPC resource.

    Args:
        config: Configuration object containing:
            - metadata: Metadata helper function
            - resourceName: Name of the resource
            - region: Target region

    Returns:
        List containing VPC resource, or empty list if disabled
    """
    [
        ec2v1beta1.VPC{
            metadata = config.metadata("vpc") | {
                name = "vpc-${config.resourceName}"
                labels = config.sanitizeLabels(config.tags)
            }
            spec = {
                forProvider = {
                    region = config.region
                    cidrBlock = config.cidrBlock
                    enableDnsHostnames = True
                    tags = config.tags | { Name = "vpc-${config.resourceName}" }
                }
            }
        }
    ] if config.createVPC else []
}

# ========================================
# PUBLIC API (no underscore)
# ========================================
generateNetworkResources = lambda config: {str: any} -> [any] {
    """
    Generates all network resources.

    Args:
        config: Configuration object

    Returns:
        List of all network resources
    """
    _generateVPC(config) + \
    _generateSubnets(config) + \
    _generateGateway(config)
}
```

### Key Points

- Module docstring at top
- Section separation with comments
- Private functions prefixed with `_`
- Comprehensive docstrings (Args, Returns)
- Public API function for main.k to call
- Always return lists (empty if disabled)

---

## Pattern 4: Configuration Object

### Why Use It

- Reduces coupling between modules
- Simplifies function signatures
- Provides single source of truth
- Makes refactoring easier

### Template

```kcl
config = {
    # Helper Functions
    metadata = _metadata
    sanitizeLabels = _sanitizeLabels

    # Core Parameters
    resourceName = resourceName
    region = region

    # Feature Flags
    enableFeature = enableFeature
    createSubResource = createSubResource

    # Lists/Collections
    items = items
    zones = zones

    # Tags/Labels
    tags = tags
    resourceSpecificTags = resourceSpecificTags
}
```

### Usage

```kcl
# Pass to all modules
items = module1.generateResources(config) + \
        module2.generateResources(config)

# Modules access via: config.resourceName, config.enableFeature, etc.
```

---

## Pattern 5: Helper Functions

### 1. Metadata Annotation Helper (MANDATORY)

```kcl
_metadata = lambda name: str -> any {
    """
    Creates metadata with composition resource name annotation.
    CRITICAL: This annotation is required for Crossplane to track resources.
    """
    { annotations = { "krm.kcl.dev/composition-resource-name" = name }}
}

# Usage: EVERY resource MUST use this
metadata = config.metadata("unique-resource-id") | {
    name = "actual-kubernetes-name"
    labels = {...}
}
```

**Why Critical**: Crossplane uses this annotation to uniquely identify resources within the composition, enabling updates and deletions.

### 2. Label Sanitization Helper

```kcl
_sanitizeLabels = lambda tags: {str:str} -> {str:str} {
    """
    Sanitizes tag values for Kubernetes label constraints:
    - 63 characters maximum
    - Alphanumeric, '-', '_', '.' only
    - Must start/end with alphanumeric
    """
    {k: v.replace("/", "-").replace(":", "-")[:63] for k, v in tags}
}

# Usage: Apply to any user-provided tags
labels = config.sanitizeLabels(config.tags)
```


## Pattern 5.3: what a v2 managed resource needs

See [`../CHARTER.md` §5](../../../SKILL.md#5-crossplane-v2-what-a-composed-resource-actually-needs).
In KCL that reduces to: write `spec.forProvider` and stop.

```kcl
spec = {
    forProvider = {
        # Resource-specific configuration — the only part you own
    }
}
```

There is **no third "default spec" helper.** Older versions of this guide told you to add
`_defaultSpec = { providerConfigRef = { kind = "ProviderConfig", name = "default" }, managementPolicies = ["*"] }`
to every managed resource. Don't — the charter has the verified behaviour and the live-control-plane
evidence.

---

**Continued:** [`patterns-logic.md`](patterns-logic.md) — conditional creation, list
comprehensions, selector-based references, type merging, optional fields, and multi-branch
logic.
