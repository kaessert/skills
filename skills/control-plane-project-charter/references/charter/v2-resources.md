# Crossplane v2 resources: the detail

Authoring the XRD, what the CRD defaults do to a render, and choosing a ProviderConfig. [`../CHARTER.md` §5](../../SKILL.md#5-crossplane-v2-what-a-composed-resource-actually-needs) states the rules; this carries the tables, the skeleton and the evidence.

---

## Why `.m.` is "modern", not "namespaced"

Crossplane's own upgrade guide is the source, and it is easy to misread:

> The `.m.` indicates modern namespaced managed resources.
> — *Crossplane docs, "Upgrade to Crossplane v2"*

"Modern" is the adjective on `.m.`; "namespaced managed resources" is what the modern groups
mostly contain. The decisive counter-example is `ClusterProviderConfig`, which is
`scope=Cluster` and lives in the `.m.` family — in the bare `aws.m.upbound.io`, the parent of
the `rds.aws.m.upbound.io`-style managed-resource groups. If `.m.` itself meant "namespaced",
"use the `.m.` group" and "use a `ClusterProviderConfig`" would contradict each other.

---

### Write the XRD yourself

The XRD is the one project file you should author directly rather than generate. `up xrd
generate` infers a schema from a single example manifest, and an example cannot express the
things that matter: it has no way to say which fields are required, what the defaults are, that
a map is open-ended, or that a `status` exists at all. §10 lists what it drops. Everything it
gets wrong is something you would have to find and repair by reading its output line by line,
which is more work than writing the file.

Writing it directly is also what produces a *better* generated model. The same API, hand-written
versus inferred:

| | inferred from an example | written directly |
|---|---|---|
| a required field | `Optional[str] = None` | `region: str` |
| `retentionDays: 90` | `Optional[float] = None` — no default, and `number` not `integer` | `Optional[int] = 90` |
| `tags: {team: platform}` | fixed properties, one per key the example happened to use | `Optional[Dict[str, str]]` |
| `status` | absent | modelled |

`up project build` generates the models from whatever XRD is on disk, so a hand-written one
needs no extra step.

This is the skeleton — every line of it load-bearing for v2, and none of it guessable from the
project templates, which are v1 (§10):

```yaml
apiVersion: apiextensions.crossplane.io/v2      # v2, and there is still no v2 Composition
kind: CompositeResourceDefinition
metadata:
  name: xstoragebuckets.platform.example.com    # <plural>.<group>
spec:
  scope: Namespaced                             # v2 replaces claimNames; do not write claimNames
  group: platform.example.com
  names:
    kind: XStorageBucket
    plural: xstoragebuckets
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
              parameters:
                type: object
                properties:
                  region: {type: string}
                  retentionDays: {type: integer, default: 90}
                  tags:                          # an open-ended map, not fixed properties
                    type: object
                    additionalProperties: {type: string}
                required: [region]
            required: [parameters]
          status:                                # model it, or your function cannot report
            type: object
            properties:
              bucketArn: {type: string}
```

Keep writing the example XR first — it is the render input for tests and the fast tier, and
drafting the API a user will actually write is what keeps the schema honest. Just do not
derive the schema from it.

Three things that are false, and are stated confidently often enough to be worth naming:

- "Family providers use different APIs than single providers"
- "The `.m.` stands for monolithic" — or for "naMespaced"
- "`provider-aws-iam` can't use namespaced ProviderConfig"

The import or type path that reaches these APIs is language-specific: see
[`languages/`](../languages/). Run `up project build` after a provider version change to
regenerate models.

---

## What the CRD defaults do to a render

> **These are CRD schema defaults, so whether a render shows them depends on the language.**
> `up test run` and `crossplane render` have no API server, so no CRD defaulting happens at
> render time. Two separate things then decide what you see — what `up`'s schema generator
> bakes into the model, and what the language's serializer emits:
>
> | Models | `managementPolicies` | `providerConfigRef` | Reaches the render? |
> |---|---|---|---|
> | Python | materialized (`= ['*']`) | materialized (`default_factory`) | **No** — `resource.update()` drops model defaults you never assigned (`exclude_defaults` on SDK 0.5.0/0.11.0, `exclude_unset` on 0.14.0) |
> | KCL | materialized (`= ["*"]`) | not materialized | `managementPolicies` yes |
> | Go | not materialized | not materialized | no |
>
> So a Python render reliably shows neither, and a KCL render reliably shows
> `managementPolicies`. **Both are correct, and neither tells you what the API server will
> fill in on a real control plane.** Never "fix" a function because a render shows or omits
> them, and never add them to an *expected* resource in a test — the test-side dump keeps
> what you set, so the assertion then fails against a render that correctly omits it.
>
> Both fields come from the same place: the embedded `ManagedResourceSpec` struct in
> crossplane-apis v2 (`core/v2/resource_namespace.go`), which every namespaced provider MR
> inlines. They are not two mechanisms.

> **Do not set `providerConfigRef.kind: "ProviderConfig"` reflexively.** That selects a
> *namespaced* ProviderConfig in the resource's own namespace — an object nothing in your
> project creates unless you created it.
>
> Two cautions about the evidence:
>
> - **You will find `kind: ProviderConfig` in the project templates**, in E2E tests and in
>   `examples/providerconfig.yaml`. Every current template is a Crossplane **v1** project
>   (see §10), where `ProviderConfig` is the *cluster-scoped* kind. Do not read them as a v2
>   precedent.
> - **`up test generate --e2e` creates no ProviderConfig at all** — it emits
>   `extraResources: []` in every language. If a test needs one, you add it.
>
> The failure mode: crossplane-runtime cannot resolve the reference, so `Connect` fails. Expect
> `Synced=False` and a `CannotConnectToProvider` warning event carrying "cannot get referenced
> ProviderConfig" — a resource that has been observed but not yet reconciled will show blank
> conditions, which is easy to mistake for silence. Either way the composition suite passes,
> and nothing fails until it is on a real control plane.

**Set `providerConfigRef` only when the platform genuinely has more than one credential**,
and then make `kind` match an object that exists:

| `kind` | Selects | When |
|---|---|---|
| `ClusterProviderConfig` | cluster-scoped config, shared by all namespaces | the v2 default; name it explicitly to pick a non-`default` one |
| `ProviderConfig` | namespaced config in the resource's namespace | per-namespace credentials — **only if you also create that ProviderConfig**, in that namespace |

Some languages make `kind` a *required* field when you construct a `providerConfigRef`
object. That is a constraint on constructing the object, not a reason to construct it.

**Grep your own function before you report.** Two checks, because one regex cannot do both:

```bash
# 1. The two fields that should never be hardcoded on a managed resource.
grep -rnE 'providerConfigRef|managementPolicies' functions/

# 2. An assignment to a namespace field — not the word "namespace", which appears in
#    every honest comment explaining why the field is deliberately absent.
grep -rnE '(metadata\.)?namespace\s*[:=]' functions/
```

**"No output" is not the pass condition.** A well-commented function legitimately mentions
these fields — the comment explaining why `namespace` is deliberately absent contains the word
`namespace`. Judge each hit: a hardcoded value on a managed resource is a defect; a
parameterised, deliberate opt-in is not. Note also that `grep -r` does not follow the `model`
symlink into the generated schemas — keep it that way, or the output is thousands of lines.
