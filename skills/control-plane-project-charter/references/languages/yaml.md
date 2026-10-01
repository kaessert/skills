# YAML

Raw-YAML **tests** with real-world examples. There are no YAML composition functions — YAML
is a test-only language here, and its independence from the function language is the point.

The language-agnostic rules — the TDD loop, what a v2 managed resource needs, the container
boundary, what a green run proves, reporting discipline — are in
[the charter](../../SKILL.md) and are **not** repeated here. Read the charter first; this
file only tells you how YAML expresses it.

| | |
|---|---|
| Scaffold a test | `up test generate <n> --language yaml` (add `--e2e`) |
| Run one | `up test run "tests/<n>"` |

## Why YAML

YAML tests are the simplest and most decoupled option - no imports, no toolchain, no model generation. **The test language is independent of the composition language:** a Python or KCL composition project can (and often does) use raw YAML tests. `configuration-aws-ctp` is Python functions with YAML tests. Prefer YAML when you want tests that read like the rendered output and don't need programmatic generation.

Key differences from KCL/Python:
- **No imports.** Namespacing lives directly in the `apiVersion` string (e.g. `s3.aws.m.upbound.io/v1beta1`, `kubernetes.m.crossplane.io/v1alpha1`, `helm.m.crossplane.io/v1beta1`).
- **Multiple tests per file** are separated by `---` documents.
- Assertions are partial by structure: assert only the fields you list; the renderer must produce at least those.

## Composition Test (real example)

Multiple `CompositionTest` documents in one `test.yaml`. Each renders the composition against an XR fixture and asserts composed resources.

```yaml
# tests/test-controlplane/test.yaml
apiVersion: meta.dev.upbound.io/v1alpha1
kind: CompositionTest
metadata:
  name: basic
spec:
  compositionPath: apis/ctp/composition.yaml
  xrdPath: apis/ctp/definition.yaml
  validate: false
  timeoutSeconds: 60
  xr:
    apiVersion: aws.platform.upbound.io/v1alpha1
    kind: ControlPlane
    metadata:
      name: test-cp
    spec:
      parameters:
        id: test-cp
        region: us-east-1
        version: "1.34"
        nodes:
          count: 2
          instanceType: t3.small
  assertResources:
  - apiVersion: aws.platform.upbound.io/v1alpha1
    kind: Network
    metadata:
      name: test-cp
  - apiVersion: aws.platform.upbound.io/v1alpha1
    kind: EKS
    metadata:
      name: test-cp
  # Assert critical fields, not just existence - here the Release's chart + values.
  - apiVersion: helm.m.crossplane.io/v1beta1
    kind: Release
    metadata:
      name: test-cp-uxp
    spec:
      forProvider:
        chart:
          version: "2.2.1-up.1"
---
apiVersion: meta.dev.upbound.io/v1alpha1
kind: CompositionTest
metadata:
  name: backup-enabled          # feature-enabled variant, same directory
spec:
  compositionPath: apis/ctp/composition.yaml
  xrdPath: apis/ctp/definition.yaml
  validate: false
  timeoutSeconds: 60
  xr:
    apiVersion: aws.platform.upbound.io/v1alpha1
    kind: ControlPlane
    metadata:
      name: test-cp
    spec:
      parameters:
        id: test-cp
        region: us-east-1
        version: "1.34"
        nodes: { count: 2, instanceType: t3.small }
        backup:
          enabled: "yes"
          location: arn:aws:s3:::my-backup-bucket
  assertResources:
  # Namespaced provider API in the apiVersion string (.m.).
  - apiVersion: s3.aws.m.upbound.io/v1beta1
    kind: Bucket
    metadata:
      name: test-cp-backup-bucket
    spec:
      forProvider:
        region: us-east-1
  - apiVersion: kubernetes.m.crossplane.io/v1alpha1
    kind: Object
    metadata:
      name: test-cp-backup-config
    spec:
      forProvider:
        manifest:
          spec:
            objectStorage:
              credentials:
                source: InjectedIdentity
```

## Sequential test with observedResources (real example)

Feed a mocked `status` for a prior resource; assert what renders as a result. Keep `validate: false` (as the scaffold does) - these tests mock status the schema would not populate.

```yaml
apiVersion: meta.dev.upbound.io/v1alpha1
kind: CompositionTest
metadata:
  name: k8gb-lbcontroller-podidentity
spec:
  compositionPath: apis/ctp/composition.yaml
  xrdPath: apis/ctp/definition.yaml
  validate: false
  timeoutSeconds: 60
  xr:
    apiVersion: aws.platform.upbound.io/v1alpha1
    kind: ControlPlane
    metadata:
      name: test-cp
    spec:
      parameters:
        id: test-cp
        region: us-east-1
        version: "1.34"
        nodes: { count: 2, instanceType: t3.small }
        k8gb:
          enabled: "yes"
  observedResources:
  # EKS cluster name/account come from the observed EKS XR status contract.
  - apiVersion: aws.platform.upbound.io/v1alpha1
    kind: EKS
    metadata:
      name: test-cp
      namespace: default
      annotations:
        crossplane.io/composition-resource-name: eks-cluster
    status:
      eks:
        clusterArn: arn:aws:eks:us-east-1:123456789012:cluster/test-cp-abc12345
  # Pod Identity association Ready -> controller scales up.
  - apiVersion: eks.aws.m.upbound.io/v1beta1
    kind: PodIdentityAssociation
    metadata:
      name: test-cp-lb-controller-pia
      namespace: default
      annotations:
        crossplane.io/composition-resource-name: lb-controller-pia
    status:
      conditions:
      - type: Ready
        status: "True"
  assertResources:
  - apiVersion: eks.aws.m.upbound.io/v1beta1
    kind: PodIdentityAssociation
    metadata:
      name: test-cp-lb-controller-pia
    spec:
      forProvider:
        clusterName: test-cp-abc12345
        serviceAccount: aws-load-balancer-controller
```

## E2E Test (real example)

A single `E2ETest` document per file. Note the real config tracks a **channel** with no pinned version, uses `["Ready"]`, and sizes the timeout to a real EKS cluster.

```yaml
# tests/e2etest-controlplane/test.yaml
apiVersion: meta.dev.upbound.io/v1alpha1
kind: E2ETest
metadata:
  name: controlplane-with-backup
spec:
  crossplane:
    autoUpgrade:
      channel: Stable          # channel only - no pinned version
  defaultConditions:
  - Ready
  timeoutSeconds: 3600         # sized to EKS provisioning + UXP install
  cleanupTimeoutSeconds: 1200
  extraResources:
  - apiVersion: aws.m.upbound.io/v1beta1
    kind: ProviderConfig
    metadata:
      name: default
      namespace: default        # REQUIRED for v2
    spec:
      credentials:
        source: Upbound         # web/injected identity, never static keys
        upbound:
          webIdentity:
            roleARN: arn:aws:iam::609897127049:role/solutions-e2e-provider-aws
  manifests:
  - apiVersion: aws.platform.upbound.io/v1alpha1
    kind: ControlPlane
    metadata:
      name: e2e-test-cp
    spec:
      parameters:
        id: e2e-test-cp
        region: us-east-1
        version: "1.34"
        nodes: { count: 2, instanceType: t3.small }
        backup:
          enabled: "yes"
          location: arn:aws:s3:::upbound-e2e-test-cp-backup
  skipDelete: false
```

## Tips

- **Document your intent in comments.** Real configs use leading comments to explain what each test proves and what it deliberately does NOT cover - do the same; it makes tests self-documenting.
- **`E2ETest` cannot assert arbitrary status fields.** If a value only appears on `status`, assert reaching `Ready` and verify the status manually (or cover it in a composition test with `observedResources`).

## Go / go-templating

See [`go.md`](go.md).
