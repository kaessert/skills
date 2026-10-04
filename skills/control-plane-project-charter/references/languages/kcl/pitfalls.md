# KCL: pitfalls

The KCL mistakes that render green and break later, plus a worked interaction.

Language-agnostic rules are in [`control-plane-project-charter`](../../../SKILL.md); the KCL index is [`../kcl.md`](../kcl.md).

---

## Common Pitfalls Reference

### Pitfall 1: Missing Type Imports

**Problem**: Runtime errors when accessing XR fields

**Solution**:
```kcl
import models.io.upbound.platform.myxrd.v1alpha1 as myxrd
oxrSpec = myxrd.MyResource.spec{**oxr.spec}
```

### Pitfall 2: Missing Empty List Alternative

**Problem**: Function returns `None` instead of empty list

**Solution**:
```kcl
[Resource{...}] if condition else []
```

### Pitfall 3: Label Value Violations

**Problem**: Kubernetes rejects invalid labels

**Solution**:
```kcl
labels = config.sanitizeLabels(config.tags)
```

### Pitfall 4: Hardcoded Resource References

**Problem**: Circular dependencies, fragile links

**Solution**:
```kcl
# WRONG
parentId = "resource-123"

# RIGHT
parentIdSelector = { matchControllerRef = True }
```


### Pitfall 5: Adding "Crossplane v2 required fields" that v2 already supplies

**Problem**: A resource renders and tests green, then never reconciles on a real control plane.

**Cause**: an explicit `providerConfigRef = { kind = "ProviderConfig", name = "default" }` —
a reference to a namespaced ProviderConfig nothing creates. See
[`control-plane-project-charter` §5](../../../SKILL.md#5-crossplane-v2-what-a-composed-resource-actually-needs).

**Solution**: delete it, along with `managementPolicies = ["*"]` and any `metadata.namespace`
on managed resources — unless the project's spec or API sets them (charter §5).

### Pitfall 6: Unsafe Optional Field Access

**Problem**: Runtime errors on undefined fields

**Solution**:
```kcl
value = oxrSpec.field if oxrSpec.field != None else default
optionalValue = item?.optionalField
```

### Pitfall 7: Missing Metadata Annotations

**Problem**: Crossplane cannot track resources

**Solution**:
```kcl
metadata = config.metadata("unique-resource-id") | {...}
```

### Pitfall 8: Incorrect Merge Order

**Problem**: Defaults override specific values

**Solution**:
```kcl
# WRONG - specific tags get overwritten
tags = {Name = "my-resource"} | config.tags

# RIGHT - specific tags override defaults
tags = config.tags | {Name = "my-resource"}
```

---

## Example Interaction

**User**: "I want to create a composition that generates database instances with optional read replicas."

**Recommended Structure**:

```text
functions/database/
├── main.k              # Entry point
├── kcl.mod
├── instance.k          # Primary database instance
├── replicas.k          # Read replica generation (Pattern 7)
├── security.k          # Security groups
└── monitoring.k        # Monitoring and alerts
```

**Key Patterns to Apply**:
- Pattern 6: Conditional creation for replicas
- Pattern 7: List comprehension for multiple replicas
- Pattern 8: Selectors for replica → primary reference
- Pattern 10: Optional fields for replica configuration

---
