# Crossplane v2 Migration Knowledge Base

> Reference material for the plan-v2-migration skill. Contains terminology glossary, detailed templates, before/after examples, and edge case handling.

## Table of Contents

- [Terminology Glossary](#terminology-glossary)
- [Breaking Changes Reference](#breaking-changes-reference)
- [Migration Checklist Template](#migration-checklist-template)
- [Detection Patterns](#detection-patterns)
- [Dependency Verification](#dependency-verification)
- [Common Edge Cases](#common-edge-cases)

---

## Terminology Glossary

**CRITICAL: Disambiguate these terms to avoid confusion**

| Term | Context | Meaning |
|------|---------|---------|
| **Crossplane v2** | Overall | The new Crossplane version with namespaced resources |
| **XRD apiVersion v2** | XRDs | `apiextensions.crossplane.io/v2` (was `/v1`) |
| **upbound.yaml v2alpha1** | Project config | `meta.dev.upbound.io/v2alpha1` (was `/v1alpha1`) |
| **Provider namespaced** | Providers | Providers with `.m.` in API groups (awsm, azurem, gcpm) |
| **X-prefix** | Resource kinds | v1 convention: `XNetwork`. v2 removes it: `Network` |
| **scope: Namespaced** | XRDs | New required field in v2 XRDs |

### Provider API Group Changes

| v1 Provider | v2 Provider | v1 API Group | v2 API Group |
|-------------|-------------|--------------|--------------|
| aws | awsm | `*.aws.upbound.io` | `*.aws.m.upbound.io` |
| azure | azurem | `*.azure.upbound.io` | `*.azure.m.upbound.io` |
| gcp | gcpm | `*.gcp.upbound.io` | `*.gcp.m.upbound.io` |

### KCL Import Changes

```kcl
# v1 imports
import models.io.upbound.aws.rds.v1beta1 as rds
import models.io.upbound.azure.storage.v1beta1 as storage
import models.io.upbound.gcp.sql.v1beta1 as sql

# v2 imports (note the 'm' suffix)
import models.io.upbound.awsm.rds.v1beta1 as rds
import models.io.upbound.azurem.storage.v1beta1 as storage
import models.io.upbound.gcpm.sql.v1beta1 as sql
```

---

## Breaking Changes Reference

### 1. XRD API Version and Scope

**Before (v1):**
```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: xnetworks.platform.upbound.io
spec:
  claimNames:
    kind: Network
    plural: networks
  names:
    kind: XNetwork
    plural: xnetworks
```

**After (v2):**
```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata:
  name: networks.platform.upbound.io
spec:
  scope: Namespaced  # NEW - required
  names:
    kind: Network    # No X-prefix
    plural: networks
  # claimNames removed entirely
```

### 2. deletionPolicy → managementPolicies

**Before (v1):**
```yaml
deletionPolicy:
  type: string
  enum: [Delete, Orphan]
  default: Delete
```

**After (v2):**
```yaml
managementPolicies:
  type: array
  items:
    type: string
    enum: ["*", Create, Observe, Update, Delete, LateInitialize]
  default: ["*"]
```

**Mapping:**
- `deletionPolicy: Delete` → `managementPolicies: ["*"]`
- `deletionPolicy: Orphan` → `managementPolicies: ["Create", "Observe", "Update", "LateInitialize"]`

### 3. providerConfigRef Structure

**Before (v1):**
```kcl
providerConfigRef.name = "default"
```

**After (v2):**
```kcl
providerConfigRef = {
    kind = "ProviderConfig"  # REQUIRED
    name = "default"
}
```

### 4. Namespace Field Removal

**Before (v1):**
```kcl
passwordSecretRef = {
    name = "secret-name"
    namespace = "default"  # Explicit namespace
    key = "password"
}
```

**After (v2):**
```kcl
passwordSecretRef = {
    name = "secret-name"
    key = "password"
    # namespace removed - inferred from resource namespace
}
```

### 5. compositionSelector Location

**Before (v1):**
```yaml
spec:
  compositionSelector:
    matchLabels:
      provider: aws
  parameters:
    region: us-west-2
```

**After (v2):**
```yaml
spec:
  crossplane:
    compositionSelector:
      matchLabels:
        provider: aws
  parameters:
    region: us-west-2
```

### 6. Connection Secrets Rearchitecture

**CRITICAL**: XRs no longer support built-in `writeConnectionSecretToRef`. Must manually compose Kubernetes Secret resources.

**Before (v1):**
```kcl
# Worked automatically via connectionSecretKeys in XRD
oxr.status.connectionDetails = {
    endpoint = instance.status.atProvider.endpoint
}
```

**After (v2):**
```kcl
import base64
import models.io.k8s.api.core.v1 as corev1

# Must create Secret manually
corev1.Secret{
    metadata = {
        name = "{}-connection".format(oxr.metadata.name)
        namespace = oxr.metadata.namespace
        annotations = {
            "crossplane.io/composition-resource-name" = "connection-secret"
        }
    }
    type = "connection.crossplane.io/v1alpha1"
    data = {
        endpoint = base64.encode(_ocds["db-instance"].Resource?.status?.atProvider?.endpoint or "")
        password = _ocds["db-instance"].ConnectionDetails?.password or ""  # Already base64
    }
}
```

### 7. Directory Naming Convention

**v1 directories (X-prefix):**
```text
functions/xnetwork/
tests/test-xnetwork-basic/
tests/e2etest-xnetwork/
```

**v2 directories (no X-prefix):**
```text
functions/network/
tests/test-network-basic/
tests/e2etest-network/
```

---

## Migration Checklist Template

Write this template to `.agents/plans/CROSSPLANE_V2_MIGRATION.md`:

```markdown
# Crossplane v2 Migration Plan

**Generated**: [timestamp]
**Project**: [project-name]
**Current Version**: v1 (cluster-scoped)
**Target Version**: v2 (namespaced)

## Migration Overview

**Impact Summary:**
- XRDs to update: [count]
- Functions to update: [count]
- Tests to update: [count]
- Examples to update: [count]
- Total tasks: [estimated count]

**Resources affected:**
[List each resource with kind change]

**Breaking changes detected:**
[List major breaking changes found]

---

## Phase 1: Pre-Migration Preparation

### 1.1 Backup Current State
- [ ] Create git branch: `git checkout -b migrate-to-v2`

### 1.2 Update Dependencies

**File**: `upbound.yaml`

- [ ] Update API version:
  ```yaml
  # From: apiVersion: meta.dev.upbound.io/v1alpha1
  # To:
  apiVersion: meta.dev.upbound.io/v2alpha1
  ```

- [ ] Update provider dependencies for v2 compatibility
  [Include specific provider updates from dependency verification]

[If connection secrets detected:]
- [ ] Add k8s API dependency:
  ```yaml
  spec:
    apiDependencies:
    - k8s:
        version: v1.33.0
      type: k8s
  ```

- [ ] Run: `up dep update-cache`
- [ ] Build: `up project build`

---

## Phase 2: XRD Migration

[For each XRD, create subsection with specific changes:]

### 2.N Update XRD: [resource-name]

**File**: `apis/[path]/definition.yaml`

- [ ] Update apiVersion: `v1` → `v2`
- [ ] Add `spec.scope: Namespaced`
- [ ] Remove `claimNames` section
- [ ] Update names (remove X-prefix)
- [ ] Replace deletionPolicy with managementPolicies (if present)
- [ ] Remove connectionSecretKeys (if present)

---

## Phase 3: Function Code Migration

**EXECUTION**: Use `author-composition` skill for each function

[For each function:]

### 3.N Update Function: [function-name]

**File**: `functions/[name]/main.k`

- [ ] Update provider imports (aws → awsm, etc.)
- [ ] Update XR type references (remove X-prefix)
- [ ] Update providerConfigRef to include `kind`
- [ ] Replace deletionPolicy with managementPolicies
- [ ] Remove namespace from secret references
- [ ] Implement manual Secret composition (if using connection secrets)

---

## Phase 4: Composition Updates

[For each composition:]

### 4.N Update Composition: [name]

**File**: `apis/[path]/composition.yaml`

- [ ] Update compositeTypeRef.kind (remove X-prefix)

---

## Phase 5: Example Updates

[For each example:]

### 5.N Update Example: [name]

**File**: `examples/[file].yaml`

- [ ] Update kind (remove X-prefix)
- [ ] Add namespace to metadata
- [ ] Move compositionSelector to spec.crossplane
- [ ] Remove writeConnectionSecretToRef

---

## Phase 6: Test Updates

**EXECUTION**: Use `author-tests` skill for each test

[For each test:]

### 6.N Update Test: [name]

**File**: `tests/[name]/main.k`

- [ ] Update provider imports
- [ ] Update XR kind and add namespace
- [ ] Update assertions for v2 patterns

---

## Phase 7: File Reorganization

### 7.1 Remove X-Prefix from Directories

[If X-prefix directories detected:]

**Function directories:**
- [ ] `git mv functions/x[name] functions/[name]`

**Test directories:**
- [ ] `git mv tests/test-x[name]-* tests/test-[name]-*`
- [ ] `git mv tests/e2etest-x[name] tests/e2etest-[name]`

- [ ] Update composition.yaml function references

> **⚠️ The function directory name IS the published OCI registry path.** Rename a function ONLY to drop the `x`-prefix (v2 requirement). NEVER add a language suffix (`-python`, `-kcl`, `-go`) — there is no such convention. `functionRef.name` and `step` in `composition.yaml` must match the final (unsuffixed) directory name.

---

## Phase 8: Verification

**EXECUTION**: Use `verify-configuration` skill

- [ ] Clean build: `rm -rf .up/ && up project build`
- [ ] Run composition tests: `up test run tests/test-*`
- [ ] Run E2E tests (use `e2e-test-configuration` skill)

---

## Phase 9: Documentation

- [ ] Update README.md with v2 changes
- [ ] Document migration notes

---

## Migration Summary

**Total Tasks**: [count]
**Critical Path Items**: [list]
**Estimated Complexity**: [Low|Medium|High]
```

---

## Detection Patterns

### Detect v1 Configuration

```bash
# Check upbound.yaml for v1 API
grep -q "apiVersion: meta.dev.upbound.io/v1alpha1" upbound.yaml

# Check XRDs for v1 API
find apis -name "definition.yaml" -exec grep -l "apiextensions.crossplane.io/v1" {} \;

# Check for cluster-scoped provider imports (no .m.)
grep -r "\.aws\.\|\.azure\.\|\.gcp\." functions/ upbound.yaml | grep -v "\.m\."
```

### Discover Project Structure

```bash
# Project name
yq '.metadata.name' upbound.yaml

# List all XRDs
find apis -name "definition.yaml" -exec dirname {} \; | sed 's|^apis/||' | sort

# List functions
ls -1d functions/*/ 2>/dev/null | sed 's|functions/||g' | sed 's|/||g'

# Count tests
ls -1d tests/test-*/ 2>/dev/null | wc -l
ls -1d tests/e2etest-*/ 2>/dev/null | wc -l

# Detect X-prefix directories
ls -1d functions/x* tests/test-x* tests/e2etest-x* 2>/dev/null
```

### Analyze XRD Details

```bash
XRD_FILE="apis/[resource]/definition.yaml"

yq '.apiVersion' "$XRD_FILE"
yq '.spec.claimNames' "$XRD_FILE"
yq '.spec.connectionSecretKeys' "$XRD_FILE"
yq '.spec.names.kind' "$XRD_FILE"
```

### Analyze Function Patterns

```bash
FUNC="functions/[name]/main.k"

# Check provider imports
grep "^import models.io.upbound" "$FUNC"

# Check deletionPolicy usage
grep "deletionPolicy" "$FUNC"

# Check providerConfigRef patterns
grep "providerConfigRef" "$FUNC"

# Check connection secrets
grep -E "CompositeConnectionDetails|writeConnectionSecretToRef" "$FUNC"
```

---

## Dependency Verification

If your agent can delegate work to a separate agent, delegate dependency verification so the large marketplace responses stay out of the main context; otherwise do it inline and keep only the report.

### Delegation Prompt Template

```text
Read upbound.yaml and extract all dependencies from spec.dependsOn.

For each PROVIDER:
1. Extract provider name and current version
2. Use WebFetch to check: https://marketplace.upbound.io/providers/upbound/{provider}/{version}#managedResources
3. Look for "Namespace Scoped ({count})" - count > 0 means v2 compatible
4. If count = 0, find a version that IS compatible

For each CONFIGURATION:
1. Extract org, config name, and version
2. Find GitHub repo via marketplace page
3. Check definition.yaml files for: apiVersion v2 AND scope: Namespaced
4. If not found, find a version that IS compatible

Return structured report with verification URLs.
```

### Expected Subagent Output Format

```text
## PROVIDERS

1. provider-aws-s3 (current: v1.14.0)
   ✅ Supports namespaced managed resources
   Count: 42
   Verified: [marketplace-url]

2. provider-azure-storage (current: v0.42.0)
   ❌ Does NOT support namespaced managed resources
   ✅ Recommended: v1.2.0 (verified)
   Verified: [marketplace-url]

## CONFIGURATIONS

1. configuration-aws-network (current: v0.10.0)
   ✅ Supports namespaced XRs
   Verified: [github-url]
```

---

## Common Edge Cases

### Connection Secrets with Multiple Resources

When composing secrets from multiple managed resources:

```kcl
corev1.Secret{
    metadata.name = "{}-connection".format(oxr.metadata.name)
    metadata.namespace = oxr.metadata.namespace
    data = {
        # Primary resource
        endpoint = base64.encode(_ocds["primary"].Resource?.status?.atProvider?.endpoint or "")
        # Secondary resource
        replica_endpoint = base64.encode(_ocds["replica"].Resource?.status?.atProvider?.endpoint or "")
        # Password from connection details
        password = _ocds["primary"].ConnectionDetails?.password or ""
    }
}
```

### Handling Optional Namespace Fields

For backward compatibility during migration:

```yaml
# XRD schema - make namespace optional
passwordSecretRef:
  type: object
  properties:
    namespace:
      type: string
      description: "Deprecated in v2 - namespace is now inferred"
    name:
      type: string
    key:
      type: string
  required:
    - name
    - key
    # namespace no longer required
```

### Multi-Provider Projects

Track each provider family separately:

```text
AWS providers: provider-aws-s3, provider-aws-rds → awsm imports
Azure providers: provider-azure-storage → azurem imports
GCP providers: provider-gcp-sql → gcpm imports
```

---

## Skill Boundaries

### In Scope
- Analyzing v1 configuration package structure
- Detecting all breaking changes
- Generating phase-based migration checklist
- Read-only analysis (no code modifications)

### Out of Scope (Use Other Skills)
- Executing migration → manual or use execute-v2-migration skill
- Writing function code → use author-composition skill
- Writing tests → use author-tests skill
- Running tests → use verify-configuration skill
- E2E testing → use e2e-test-configuration skill

---

## Success Criteria

The skill succeeds when:

1. ✅ v1 configuration correctly detected
2. ✅ All XRDs, functions, tests, examples analyzed
3. ✅ Dependencies verified
4. ✅ File-specific changes enumerated
5. ✅ Phase-based checklist generated
6. ✅ Output written to `.agents/plans/CROSSPLANE_V2_MIGRATION.md`
7. ✅ Summary displayed to user
