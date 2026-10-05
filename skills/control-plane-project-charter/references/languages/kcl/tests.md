# KCL: tests

Composition and E2E test templates in KCL, and the test-structure patterns.

Language-agnostic rules are in [`control-plane-project-charter`](../../../SKILL.md); the KCL index is [`../kcl.md`](../kcl.md).

---

# Part 3 — Tests

## Composition Test Template

```kcl
"""
<Feature Name> Composition Test

Tests <feature description>:
- <Specific behavior 1>
- <Specific behavior 2>
"""

import models.io.upbound.awsm.v1beta1 as awsmv1beta1
import models.io.upbound.awsm.ec2.v1beta1 as ec2v1beta1
import models.io.upbound.dev.meta.v1alpha1 as metav1alpha1

_items = [
    metav1alpha1.CompositionTest{
        metadata.name: "test-<resource>-<feature>"
        spec = {
            compositionPath: "../../apis/<resource>/composition.yaml"
            xrdPath: "../../apis/<resource>/definition.yaml"
            timeoutSeconds: 60  # MUST be ≥60
            validate: False

            # Define XR inline (RECOMMENDED)
            xr: {
                apiVersion: "aws.platform.upbound.io/v1alpha1"
                kind: "<Kind>"
                metadata: {
                    name: "test-<name>"
                    namespace: "default"
                }
                spec: {
                    region: "us-west-2"
                    tags: {
                        Environment: "test"
                        ManagedBy: "upbound"
                    }
                }
            }

            # Assert expected managed resources.
            # CRITICAL: use exact generated names (find with: up composition render)
            assertResources: [
                ec2v1beta1.<ResourceKind>{
                    metadata: {
                        name: "<exact-generated-name>"
                    }
                    spec: {
                        # No providerConfigRef or managementPolicies: v2 defaults them.
                        # Assert them only if the function sets them (charter §5).
                        forProvider: {
                            region: "us-west-2"
                            # Assert ALL critical fields
                            tags: {
                                Environment: "test"
                                ManagedBy: "upbound"
                            }
                        }
                    }
                }
            ]
        }
    }
]
items = _items
```

## E2E test

```kcl
"""
E2E Test: <Feature Name>

Validates <feature> with real AWS resources: create, Ready, delete.
"""

import models.io.upbound.awsm.v1beta1 as awsmv1beta1
import models.io.upbound.dev.meta.v1alpha1 as metav1alpha1

_items = [
    metav1alpha1.E2ETest{
        metadata.name: "e2etest-<resource>-<feature>"
        spec = {
            crossplane = { autoUpgrade.channel = "Stable" }  # or a deliberately pinned current version
            defaultConditions: ["Ready"]  # condition types; add "Synced" only to gate on sync
            timeoutSeconds: 1800          # size to the real resources
            cleanupTimeoutSeconds: 600
            skipDelete: False

            manifests: [
                {
                    apiVersion: "aws.platform.upbound.io/v1alpha1"
                    kind: "<Kind>"
                    metadata: { name: "e2e-test-<name>", namespace: "default" }
                    spec: { region: "us-west-2", tags: { Environment: "e2e-test" } }
                }
            ]

            extraResources: [
                # Cluster-scoped, so no metadata.namespace: the default every composed MR falls back to.
                awsmv1beta1.ClusterProviderConfig{
                    metadata.name: "default"
                    spec.credentials: {
                        source: "Upbound"
                        upbound.webIdentity.roleARN: "arn:aws:iam::123456789012:role/<role>"
                    }
                }
            ]
        }
    }
]
items = _items
```

Which `credentials` block a target needs (web identity on a Space, a `UP_*` Secret on a local
control plane) is in author-tests' `e2e.md` reference. On another cloud only these change:

| | Azure | GCP |
|---|---|---|
| Import | `models.io.upbound.azurem.v1beta1 as azuremv1beta1` | `models.io.upbound.gcpm.v1beta1 as gcpmv1beta1` |
| `ClusterProviderConfig` web identity | `upbound.webIdentity.clientID` | `upbound.federation.{providerID, serviceAccount}`, plus `spec.projectID` |
| Provider field names your XR usually mirrors | `location`, `tags` | `region`, `project`, `labels` (lowercase keys) |

## Pattern: Resource-Focused Bundle (KCL syntax)

Share a base spec with `**` spread; keep 3-5 related scenarios in one file.

```kcl
import models.io.upbound.dev.meta.v1alpha1 as metav1alpha1
import models.io.upbound.<provider>.<apiGroup>.v1beta1 as <apiGroup>v1beta1

_baseSpec = {
    compositionPath: "../../apis/<resource>/composition.yaml"
    xrdPath: "../../apis/<resource>/definition.yaml"
    timeoutSeconds: 60
    validate: False
}

_test_basic = metav1alpha1.CompositionTest {
    metadata.name: "test-<resource>-basic"
    spec: {
        **_baseSpec
        xr: {
            apiVersion: "aws.platform.upbound.io/v1alpha1"
            kind: "<Resource>"
            metadata: { name: "test-<resource>", namespace: "default" }
            spec: { region: "us-west-2", tags: { Environment: "test", ManagedBy: "upbound" } }
        }
        assertResources: [
            <apiGroup>v1beta1.<Kind>{
                metadata: { name: "<resource>-test" }
                spec: {
                    forProvider: { region: "us-west-2" }
                }
            }
        ]
    }
}

_test_disabled = metav1alpha1.CompositionTest {
    metadata.name: "test-<resource>-disabled"
    spec: {
        **_baseSpec
        xr: {
            apiVersion: "aws.platform.upbound.io/v1alpha1"
            kind: "<Resource>"
            metadata: { name: "test-<resource>-disabled", namespace: "default" }
            spec: { region: "us-west-2", enabled: False, tags: { Environment: "test", ManagedBy: "upbound" } }
        }
        assertResources: [ /* fewer resources */ ]
    }
}

items = [_test_basic, _test_disabled]
```

## Pattern: Parameterized Test Matrix (KCL syntax)

Generate variants from data with a lambda for guaranteed consistency.

```kcl
import models.io.upbound.dev.meta.v1alpha1 as metav1alpha1

_baseSpec = {
    compositionPath: "../../apis/<resource>/composition.yaml"
    xrdPath: "../../apis/<resource>/definition.yaml"
    timeoutSeconds: 60
    validate: False
}

_variants = [
    { name: "variant1", flag: "enableVariant1", config: {} }
    { name: "variant2", flag: "enableVariant2", config: {} }
]

buildVariantTest = lambda v {
    metav1alpha1.CompositionTest {
        metadata.name: "test-<resource>-${v.name}"
        spec: {
            **_baseSpec
            xr: {
                apiVersion: "aws.platform.upbound.io/v1alpha1"
                kind: "<Resource>"
                metadata: { name: "test-${v.name}", namespace: "default" }
                spec: {
                    region: "us-west-2"
                    "${v.flag}": True
                    **v.config
                    tags: { Environment: "test", Variant: v.name }
                }
            }
            assertResources: [ /* variant-specific resources */ ]
        }
    }
}

items = [buildVariantTest(v) for v in _variants]
```

## Pattern: Sequential Testing with observedResources (KCL layout)

Split reusable pieces across files in one test directory:

```
tests/test-<resource>-sequence/
├── main.k         # Test definitions
├── resources.k    # Reusable resource definitions
├── conditions.k   # Shared condition sets
└── kcl.mod
```

**conditions.k** - shared ready conditions:
```kcl
import datetime

readyConditions = [
    { reason: "Available", status: "True", type: "Ready", lastTransitionTime: datetime.now("%Y-%m-%dT%H:%M:%SZ") }
    { reason: "ReconcileSuccess", status: "True", type: "Synced", lastTransitionTime: datetime.now("%Y-%m-%dT%H:%M:%SZ") }
]
```

**main.k** - each step feeds the prior resource's mocked status forward:
```kcl
import models.io.upbound.dev.meta.v1alpha1 as metav1alpha1
import resources
import conditions

_baseSpec = {
    compositionPath: "../../apis/<resource>/composition.yaml"
    xrdPath: "../../apis/<resource>/definition.yaml"
    timeoutSeconds: 60
    validate: False  # sequential tests mock status
}

_xr = {
    apiVersion: "aws.platform.upbound.io/v1alpha1"
    kind: "<Resource>"
    metadata: { name: "test-<resource>", namespace: "default" }
    spec: { region: "us-west-2" }
}

_test1 = metav1alpha1.CompositionTest {
    metadata.name: "sequence-0-initial"
    spec: { **_baseSpec, xr: _xr, assertResources: [resources.resource1] }
}

_test2 = metav1alpha1.CompositionTest {
    metadata.name: "sequence-1-resource1-ready"
    spec: {
        **_baseSpec
        xr: _xr
        observedResources: [
            { **resources.resource1, status: { atProvider: { id: "id1" }, conditions: conditions.readyConditions } }
        ]
        assertResources: _test1.spec.assertResources + [resources.resource2]
    }
}

items = [_test1, _test2]
```

## KCL-Specific Mistakes

### Wrong import (cluster-scoped)
**Wrong:** `import models.io.crossplane.kubernetes.v1alpha1`
**Right:** `import models.io.crossplane.kubernetesm.v1alpha1` (note the `m`)

### Forgetting the final assignment
**Wrong:** Defining `_items` but never assigning it.
**Right:** End the file with `items = _items` (the runner reads `items`).
