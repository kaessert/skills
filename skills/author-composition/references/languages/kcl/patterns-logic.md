# KCL: conditionals, comprehensions and references

Conditional resources, list comprehensions, selector-based references, type merging, optional fields, and multi-branch logic.

Structure and the entry point are in [`patterns.md`](patterns.md); language-agnostic rules are in [`../../charter.md`](../../charter.md).

---

## Pattern 6: Conditional Resource Creation

### Simple Conditional

```kcl
generateResource = lambda config: {str: any} -> [any] {
    [
        Provider.Resource{...}
    ] if config.enableFeature else []
}
```

### Multiple Conditions

```kcl
generateResource = lambda config: {str: any} -> [any] {
    [
        Provider.Resource{...}
    ] if config.enableFeature and len(config.items) > 0 and not config.useExisting else []
}
```

### Full Example

```kcl
_generateGateway = lambda config: {str: any} -> [any] {
    """Generate gateway only if enabled and region is specified"""
    [
        ec2v1beta1.InternetGateway{
            metadata = config.metadata("igw") | {
                name = "igw-${config.resourceName}"
                labels = config.sanitizeLabels(config.tags)
            }
            spec = {
                forProvider = {
                    region = config.region
                    vpcIdSelector = { matchControllerRef = True }
                    tags = config.tags | { Name = "igw-${config.resourceName}" }
                }
            }
        }
    ] if config.createGateway and config.region else []
}
```

**Key Principle**: Always end with `else []` to return empty list when conditions not met.

---

## Pattern 7: List Comprehension

### Basic List Comprehension

```kcl
_generateItems = lambda config: {str: any} -> [any] {
    [
        Provider.Item{
            metadata = config.metadata("item-${i}") | {
                name = "item-${config.resourceName}-${i}"
            }
            spec = {
                forProvider = {
                    value = itemValue
                }
            }
        }
        for i, itemValue in config.items
    ] if len(config.items) > 0 else []
}
```

### Round-Robin Distribution (Availability Zones)

```kcl
_generateSubnets = lambda config: {str: any} -> [any] {
    """
    Distributes subnets across zones using round-robin (modulo).
    Example: 6 subnets across 3 zones = 2 subnets per zone
    """
    [
        ec2v1beta1.Subnet{
            metadata = config.metadata("subnet-${i}") | {
                name = "subnet-${config.resourceName}-${config.zones[i % len(config.zones)]}"
                labels = config.sanitizeLabels(config.tags) | {
                    "zone": config.zones[i % len(config.zones)]
                    "index": str(i)
                }
            }
            spec = {
                forProvider = {
                    availabilityZone = config.zones[i % len(config.zones)]
                    cidrBlock = cidr
                    region = config.region
                    vpcIdSelector = { matchControllerRef = True }
                    tags = config.tags | {
                        Name = "subnet-${config.resourceName}-${config.zones[i % len(config.zones)]}"
                    }
                }
            }
        }
        for i, cidr in config.subnetCidrs
    ] if len(config.subnetCidrs) > 0 and len(config.zones) > 0 else []
}
```

### Key Techniques

- Use index iteration: `for i, item in items`
- Modulo for round-robin: `zones[i % len(zones)]`
- Label resources for later selection
- Always check list lengths before iteration

---

## Pattern 8: Selector-Based Resource References

**Never hardcode resource IDs. Always use selectors.**

### Three Types of Selectors

#### 1. Controller Reference (Same XR)

```kcl
parentResourceSelector = {
    matchControllerRef = True
}
```

Use when: Resource references its parent composite resource

#### 2. Label Matching

```kcl
relatedResourceSelector = {
    matchLabels = {
        "resource-type": "compute"
        "zone": "us-west-2a"
    }
}
```

Use when: Resource references sibling resources created by same composition

#### 3. Combined (Controller + Labels)

```kcl
specificResourceSelector = {
    matchControllerRef = True
    matchLabels = {
        "resource-type": "storage"
    }
}
```

Use when: Need to narrow selection within same XR

### Example: Route Table Association

```kcl
_generateRouteTableAssociations = lambda config: {str: any} -> [any] {
    [
        ec2v1beta1.RouteTableAssociation{
            metadata = config.metadata("rta-${i}") | {
                name = "rta-${config.resourceName}-${i}"
            }
            spec = {
                forProvider = {
                    region = config.region
                    # Reference route table by controller
                    routeTableIdSelector = {
                        matchControllerRef = True
                    }
                    # Reference specific subnet by labels
                    subnetIdSelector = {
                        matchLabels = {
                            "zone": config.zones[i]
                            "index": str(i)
                        }
                    }
                }
            }
        }
        for i in range(len(config.zones))
    ] if len(config.zones) > 0 else []
}
```

### Why Selectors?

- Crossplane resolves references dynamically at runtime
- No circular dependencies or ordering issues
- Type-safe resource relationships
- Supports matching multiple resources

---

## Pattern 9: Type Merging with Pipe Operator

**Pattern**: Use `|` operator to merge configurations (right overwrites left)

### Order Matters

`defaults | overrides | finalValues`

### Spec Composition

```kcl
spec = {
    forProvider = {
        region = config.region
        customField = config.value
    }
}
```

### Tag Merging (Multi-Level)

```kcl
tags = config.baseTags | config.resourceTypeTags | {
    Name = "resource-name"
    ManagedBy = "crossplane"
}
# Order: base tags → type-specific tags → resource-specific tags
```

### Metadata Composition

```kcl
metadata = config.metadata("resource-id") | {
    name = "kubernetes-name"
    labels = config.sanitizeLabels(config.tags)
    annotations = {
        "custom.io/annotation": "value"
    }
}
```

**Key Principle**: Start with defaults/base, then add specific overrides, then final required values.

---

## Pattern 10: Optional Field Handling

### Three Techniques

#### 1. Ternary with None Check

```kcl
value = oxrSpec.field if oxrSpec.field != None else defaultValue
boolValue = oxrSpec.flag if oxrSpec.flag != None else False
```

#### 2. Optional Field Access Operator (`?`)

```kcl
# Safe access - returns None if field doesn't exist
value = config.item?.optionalField

# Conditional dict merging for optional fields
spec = {
    requiredField = config.required
} | ({optionalField = config.item.optional} if config.item?.optional else {})
```

#### 3. Conditional Dict Merging for Multiple Optional Fields

```kcl
spec = {
    forProvider = {
        # Always present
        region = config.region
        name = config.name
    } | ({fromPort = rule.fromPort} if rule?.fromPort else {}) \
      | ({toPort = rule.toPort} if rule?.toPort else {}) \
      | ({protocol = rule.protocol} if rule?.protocol else {})
}
```

### Full Example: Security Group Rule

```kcl
_generateSecurityGroupRule = lambda config, rule: any -> any {
    """Generate security group rule with optional port fields"""
    ec2v1beta1.SecurityGroupRule{
        metadata = config.metadata("sgr-${rule.id}") | {
            name = "sgr-${config.resourceName}-${rule.id}"
        }
        spec = {
            forProvider = {
                # Required fields
                type = rule.type
                cidrBlocks = rule.cidrBlocks
                region = config.region
                securityGroupIdSelector = { matchControllerRef = True }
            } | ({fromPort = rule.fromPort} if rule?.fromPort else {}) \
              | ({toPort = rule.toPort} if rule?.toPort else {}) \
              | ({protocol = rule.protocol} if rule?.protocol else {})
        }
    }
}
```

---

## Pattern 11: Complex Conditional Logic

### Nested Conditionals (Strategy Selection)

```kcl
_generateResources = lambda config: {str: any} -> [any] {
    """Generate resources with strategy selection"""
    # Strategy 1: Distributed (one per zone)
    [
        Provider.Resource{
            metadata = config.metadata("resource-${i}") | {
                name = "resource-${config.resourceName}-${config.zones[i]}"
                labels = {"zone": config.zones[i]}
            }
            spec = {
                forProvider = {
                    zone = config.zones[i]
                    region = config.region
                }
            }
        }
        for i in range(len(config.zones))
    ] if config.strategy == "distributed" and len(config.zones) > 0 else [
        # Strategy 2: Single shared resource
        Provider.Resource{
            metadata = config.metadata("resource-0") | {
                name = "resource-${config.resourceName}-shared"
            }
            spec = {
                forProvider = {
                    zone = config.zones[0]
                    region = config.region
                }
            }
        }
    ] if config.strategy == "shared" and len(config.zones) > 0 else []
}
```

### Imperative Logic (Complex Scenarios)

Use when list comprehensions become unwieldy (3+ nested conditions):

```kcl
_generateComplexResources = lambda config: {str: any} -> [any] {
    """
    Use imperative logic when list comprehensions become unwieldy.
    Better for readability with 3+ nested conditions.
    """
    resources = []

    # Condition group 1
    if config.enableFeature1 and len(config.items) > 0:
        resources += [
            Provider.ResourceType1{
                metadata = config.metadata("type1") | {
                    name = "type1-${config.resourceName}"
                }
                spec = {
                    forProvider = { region = config.region }
                }
            }
        ]

    # Condition group 2 with sub-strategies
    if config.enableFeature2:
        if config.strategy == "distributed":
            resources += [
                Provider.ResourceType2{
                    metadata = config.metadata("type2-${i}") | {
                        name = "type2-${config.resourceName}-${i}"
                    }
                    spec = {
                        forProvider = {
                            zone = config.zones[i]
                            region = config.region
                        }
                    }
                }
                for i in range(len(config.zones))
            ]
        else:
            resources += [
                Provider.ResourceType2{
                    metadata = config.metadata("type2-shared") | {
                        name = "type2-${config.resourceName}-shared"
                    }
                    spec = {
                        forProvider = { region = config.region }
                    }
                }
            ]

    # Condition group 3
    if config.enableFeature3 and not config.useExisting:
        resources += [
            Provider.ResourceType3{
                metadata = config.metadata("type3") | {
                    name = "type3-${config.resourceName}"
                }
                spec = {
                    forProvider = { region = config.region }
                }
            }
        ]

    resources
}
```

### When to Use Imperative

- 3+ nested conditions
- Multiple strategy branches
- Building resources incrementally
- Readability > brevity

---
