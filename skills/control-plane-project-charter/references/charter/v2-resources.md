# Crossplane v2 resources: the detail

What `.m.` means, the verified behaviour behind §5's field table, authoring the XRD, what the
CRD defaults do to a render, choosing a ProviderConfig, and what a missing one looks like.
[`control-plane-project-charter` §5](../../SKILL.md#5-crossplane-v2-what-a-composed-resource-actually-needs) states the rules.

---

## The `.m.` API groups

**`.m.` is for *modern*, not "naMespaced"** (Crossplane's upgrade guide: "The `.m.` indicates
modern namespaced managed resources"). The groups hold the namespaced managed resources *and*
the cluster-scoped `ClusterProviderConfig` they default to, in the bare `aws.m.upbound.io` — so
the "namespaced" reading cannot be right.

---

## The verified behaviour behind §5's field table

| Field | Verified behaviour |
|---|---|
| `metadata.namespace` | **If the XR is namespaced**, Crossplane overwrites it with the XR's namespace (`if xr.GetNamespace() != "" { cd.SetNamespace(...) }`), so a function setting a *different* namespace is silently overridden, not merged with. A **cluster-scoped** XR is the exception — its composed resources keep the namespace the function sets, which is how a cluster XR targets one. (A namespaced XR composing a cluster-scoped kind is a hard error, not a namespace question.) |
| `managementPolicies` | The namespaced MR spec carries `+kubebuilder:default={"*"}`, so the API server fills it in, and that default deletes the external resource with the MR. Never write `["*"]` yourself. Set it only for a different policy — `["Create","Observe","Update","LateInitialize"]` to orphan on delete — or when the project's API exposes it as a parameter. |
| `deletionPolicy` | The namespaced MR spec has no such field. To orphan, use `managementPolicies` (above); to delete, set nothing. A v1 API's `deletionPolicy` parameter maps the same way (`plan-v2-migration`). |
| `providerConfigRef` | The same struct, the same way: `+kubebuilder:default={"kind":"ClusterProviderConfig","name":"default"}`. |
| `metadata.name` | Unless set, Crossplane generates `<prefix>-<sha256(xr-uid + composition-resource-name)[:12]>`, where the prefix comes from the `crossplane.io/composite` label, truncated to 63 chars. Deterministic for one XR instance, **not** across re-creations — and it falls back to a random 5-char suffix when the composition-resource-name annotation or the controller ownerRef is missing. Inside a *render* it is fully deterministic and safe to assert — see [`evidence.md`](evidence.md). |

---

## Authoring the XRD

§5 says to write the XRD rather than infer it with `up xrd generate`;
[`generators.md`](generators.md) lists what inference drops. The difference carries into the
model `up project build` generates from it — the same API, inferred versus written:

| | inferred from an example | written directly |
|---|---|---|
| a required field | `Optional[str] = None` | `region: str` |
| `retentionDays: 90` | `Optional[float] = None` — no default, and `number` not `integer` | `Optional[int] = 90` |
| `tags: {team: platform}` | fixed properties, one per key the example happened to use | `Optional[Dict[str, str]]` |
| `status` | absent | modelled |

`up project build` generates the models from whatever XRD is on disk, so a hand-written one
needs no extra step.

The skeleton for a **new** API. Every line matters for v2, and the project templates do not show
it, because they are v1 ([`generators.md`](generators.md)):

```yaml
apiVersion: apiextensions.crossplane.io/v2      # v2, and there is still no v2 Composition
kind: CompositeResourceDefinition
metadata:
  name: storagebuckets.platform.example.com     # <plural>.<group>
spec:
  scope: Namespaced                             # v2 replaces claimNames; do not write claimNames
  group: platform.example.com
  names:
    kind: StorageBucket                         # no X prefix on a new API
    plural: storagebuckets
  versions:
  - name: v1alpha1
    served: true
    referenceable: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              region: {type: string}
              retentionDays: {type: integer, default: 90}
              tags:                              # an open-ended map, not fixed properties
                type: object
                additionalProperties: {type: string}
            required: [region]
          status:                                # model it, or your function cannot report
            type: object
            properties:
              bucketArn: {type: string}
```

The fields sit directly under `spec` here, as in author-configuration-package's XRD template and
the function templates (`xr.Spec.Region` in Go). Nesting them under `spec.parameters`, as many
existing APIs do, is equally valid: the project's spec and its existing XRDs decide, and the
function and the tests follow the XRD.

An existing v1 API keeps its Kind when migrated, `X` prefix included: a new Kind is a new API
([`xrd-design.md`](xrd-design.md)).

Keep writing the example XR first — it is the render input for tests and the fast tier, and
drafting the API a user will actually write keeps the schema honest. Just do not derive the
schema from it.

Three claims that are false:

- "Family providers use different APIs than single providers"
- "The `.m.` stands for monolithic" (it is *modern*, above)
- "`provider-aws-iam` can't use namespaced ProviderConfig"

The import or type path that reaches these APIs is language-specific: see
[`languages/`](../languages/). Run `up project build` after a provider version change to
regenerate models.

---

## What the CRD defaults do to a render

`managementPolicies` and `providerConfigRef` are CRD schema defaults. `up test run` and
`crossplane render` have no API server, so no CRD defaulting happens at render time, and what a
render shows depends on two things: what `up`'s schema generator bakes into the model, and what
the language's serializer emits.

| Models | `managementPolicies` | `providerConfigRef` | Reaches the render? |
|---|---|---|---|
| Python | materialized (`= ['*']`) | materialized (`default_factory`) | **No** — `resource.update()` drops model defaults you never assigned (`exclude_defaults` on SDK 0.5.0/0.11.0, `exclude_unset` on 0.14.0) |
| KCL | materialized (`= ["*"]`) | not materialized | `managementPolicies` yes |
| Go | not materialized | not materialized | no |

So a Python render shows neither, and a KCL render shows `managementPolicies`. Both are
correct, and neither tells you what the API server fills in on a real control plane. Never
"fix" a function because a render shows or omits them, and never add them to an *expected*
resource in a test — the test-side dump keeps what you set, so the assertion then fails against
a render that correctly omits it.

Both fields come from the same place: the embedded `ManagedResourceSpec` struct in
crossplane-apis v2 (`core/v2/resource_namespace.go`), which every namespaced provider MR inlines.

---

## Choosing a ProviderConfig

**Omit `providerConfigRef` if and only if `ClusterProviderConfig/default` exists and is the
right one.** That is the common case. Otherwise set it — when the platform has several
credentials, when its single `ClusterProviderConfig` is not named `default` (omitting the
reference there leaves every resource unreconciled), and when the project's spec or API sets
one. Then make `kind` match an object that exists:

| `kind` | Selects | When |
|---|---|---|
| `ClusterProviderConfig` | cluster-scoped config, shared by all namespaces | the v2 default; name it explicitly to pick a non-`default` one |
| `ProviderConfig` | namespaced config in the resource's namespace | per-namespace credentials — **only if a `ProviderConfig` of that name exists in, or is created in, the XR's namespace** |

Do not set `kind: ProviderConfig` because you found it elsewhere:

- **The project templates use `kind: ProviderConfig`** — in E2E tests and in
  `examples/providerconfig.yaml`. They are Crossplane **v1** projects, where `ProviderConfig` is
  the cluster-scoped kind. They are no v2 precedent.
- **`up test generate --e2e` creates no ProviderConfig at all** — it emits `extraResources: []`
  in every language. If a test needs one, you add it (author-tests' `e2e.md` reference).

Some languages make `kind` a *required* field when you construct a `providerConfigRef`
object. That is a constraint on constructing the object, not a reason to construct it.

---

## Symptom of a missing or wrong ProviderConfig

The composition suite passes either way; only a control plane shows it. Read the managed
resource with `kubectl describe <kind> <name> -n <ns>` — conditions **and** events:

| You see | It means |
|---|---|
| `Synced=False` and a `CannotConnectToProvider` warning event (`cannot get referenced ProviderConfig …` from Upbound providers) | the reference names a ProviderConfig that does not exist, or the wrong `kind`. Check with `kubectl get clusterproviderconfig,providerconfig -A` |
| blank conditions | observed but not reconciled yet. Wait, then read it again |
| no conditions and no events, for minutes | nothing is reconciling the kind: the provider is not installed or not healthy (`kubectl get providers.pkg.crossplane.io`, `INSTALLED` and `HEALTHY`), its pod is not running, or the MR's CRD is not established (`kubectl get crd <plural>.<group>`). Check the ProviderConfig too, but it is not what causes the silence |

---

## Grep your own function before you report

Two checks, because one regex cannot do both:

```bash
# 1. The two fields that are not hardcoded on a managed resource unless the project sets them.
grep -rnE 'providerConfigRef|managementPolicies' functions/

# 2. An assignment to a namespace field — not the word "namespace", which appears in
#    every honest comment explaining why the field is deliberately absent.
grep -rnE '(metadata\.)?namespace\s*[:=]' functions/
```

"No output" is not the pass condition. A well-commented function mentions these fields. Judge
each hit: a hardcoded value on a managed resource is a defect; a parameterised, deliberate
opt-in, or a value the project's spec requires, is not (§5). Legitimate namespace hits are a
cluster-scoped XR choosing one, and objects embedded inside `forProvider`, such as a
provider-kubernetes `Object` manifest. `grep -r` does not follow the `model` symlink into the
generated schemas — keep it that way, or the output is thousands of lines.
