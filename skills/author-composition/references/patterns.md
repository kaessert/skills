# Composition patterns — what they mean

The language-agnostic half of composition authoring: what each pattern is *for*, when it
applies, and how it fails. The syntax is in the charter's `languages/` files
(`control-plane-project-charter`, indexed by `languages/README.md`), under the same pattern
names. What a v2 managed resource needs, the container boundary, the TDD loop and what a green
run proves are the charter's and are not repeated here.

---

## The object model every language builds

A composition function receives a `RunFunctionRequest` and returns a `RunFunctionResponse`.
Three parts of it matter, and they are identical in every language:

| Part | What it is | The mistake it invites |
|---|---|---|
| `req.observed.composite` | the XR as it currently exists, including `status` | reading it as a plain map when the language gives you a typed object, or vice versa |
| `req.observed.resources` | composed resources **that already exist**, keyed by composition key | assuming it is populated. In a composition test it is `{}` unless the test supplies `observedResources` |
| `rsp.desired.resources["key"]` | what you want to exist, keyed by composition key | treating the key as cosmetic. It becomes `crossplane.io/composition-resource-name`, and Crossplane derives the resource name from it |

**The composition key is an API.** Renaming a key on an existing platform orphans the
resource it used to name: Crossplane sees the old resource as no longer desired and the new
one as new. Choose keys as deliberately as a field name, and treat a rename as a migration.

---

## Pattern: module organisation

**One module per resource domain**, with the entry point doing orchestration only — imports,
parameter extraction, the config object, and calls into the modules. A single flat function
accumulates guard clauses (below), and the guard chain is the failure composition tests
cannot see; splitting by domain keeps each conditional local to the resources it governs.

A single-file function is fine for a genuinely simple composition. The test is whether you
can name the domains; if you can, split.

---

## Pattern: the configuration object

Extract the XR's parameters **once**, into a single object, and pass that to every module.
Each module reaching into the XR itself means a schema change touches every module, and a
defaulted field gets defaulted differently in two places.

Include the core parameters, the feature flags, the lists, and the merged tags. Apply
defaults there, so there is exactly one answer to "what does this field mean when the user
omits it".

---

## Pattern: the guard-clause chain — the failure composition tests cannot see

Template functions are written as a sequence of early returns:

```
if the bucket is not observed yet:        return
if it has no external name yet:           return
if versioning is disabled:                return
```

**Anything appended after those inherits every one of them.** A resource added at the end of
the function silently disappears whenever `versioning: false`, and the test that renders with
versioning enabled passes.

**Give each optional resource its own conditional block** rather than another early return,
and place it above unrelated guards. When you add to an existing function, read the returns
above your insertion point before you write anything.

The matching test: one per input shape, including a **minimal XR that omits every optional
field**. That is the test that catches an unintended guard.

---

## Pattern: conditional creation, and the `ready OR exists` rule

A resource created only when some other resource is ready must **also** be kept when it
already exists:

```
if dependency_is_ready OR resource_already_exists:
    create it
```

Testing only `dependency_is_ready` deletes the resource whenever the dependency briefly goes
un-ready — a cluster restart takes the Helm release with it.

---

## Pattern: references beat status plumbing

When resource B needs an ARN, ID, or name produced by resource A:

| Approach | Cost |
|---|---|
| **`*Ref` / `*Selector` field** — the provider resolves it | single-pass composition, no readiness branch, nothing to test |
| Read A's `status` and write it into B | a second reconcile, a readiness branch, a branch that never executes in a composition test |

**Check for a `*Ref` before writing any status-plumbing logic.** The generated schema lists
them. A DynamoDB `Table` encrypted by a `Key` you also create needs only
`serverSideEncryption.kmsKeyArnRef: {name: <key-name>}` — no status reading at all.

Selectors come in three shapes, and the choice is about coupling:

| Selector | Matches | Use when |
|---|---|---|
| direct `*Ref` by name | the exact resource you named | you created it in this composition and know its key |
| `matchControllerRef` | resources composed by the same XR | you want "the VPC belonging to this XR" without naming it |
| `matchLabels` | anything carrying the labels | crossing composition boundaries — the loosest coupling, and the easiest to break silently |

---

## Pattern: list fields — one resource per element is a decision

An XR field that is a list does **not** imply N resources. The mistake renders perfectly and
fails only at the provider. Before writing the loop, answer three questions about the cloud
API:

1. **Are the elements independent?** Or can two of them conflict — overlapping prefixes,
   overlapping CIDR ranges, duplicate keys?
2. **Does the API want one aggregate object holding N entries**, rather than N objects? S3
   lifecycle is exactly this: one `BucketLifecycleConfiguration` holding N rules.
3. **Is there an account- or region-scoped limit** that N elements would breach?

`control-plane-project-charter` §6 has the rule classes and where they are written down. If
the models cannot answer, say which API-level rule you could not confirm rather than
assuming independence.

Upjet gives some list fields misleadingly **singular** names — `attribute`,
`globalSecondaryIndex`. Read the generated type, not the field name.

---

## Pattern: namespace propagation

With a namespaced XR, Crossplane sets every composed resource's `metadata.namespace` to the
XR's, overwriting whatever the function set: managed resources, child XRs, and a `Secret` or
`ConfigMap` you compose yourself alike. So omit it (`control-plane-project-charter` §5).

You choose a namespace in two cases only: a **cluster-scoped XR**, whose composed resources
keep the namespace the function sets, and an object **embedded inside `forProvider`** (the
`manifest` of a provider-kubernetes `Object`), which nothing fills in.

---

## Pattern: connection details

**Access observed resources by composition key**, not by the resource's rendered name. The
key is the string you used in `rsp.desired.resources["key"]`; the rendered name is derived
and includes a hash suffix.

In v2 there is no `writeConnectionSecretsToNamespace` on the composition. To surface
credentials, compose the `Secret` yourself (it lands in the XR's namespace), gathering values
from the observed resources' connection details.

**That branch does not execute in a composition test.** It reads observed state, and a local
render has none. Cover it with `observedResources` in a test, or say it is unverified.

---

## Pattern: ProviderConfig readiness

`function-auto-ready` cannot judge a ProviderConfig you compose (a Helm or Kubernetes
ProviderConfig pointing at a cluster you just created), or anything else it cannot judge, so
the function must mark it ready explicitly or the XR never becomes ready.
Whether the flag is set before or after writing the resource makes no difference (measured on
function-sdk-python 0.11.0 and 0.5.0).

---

## Pattern: flexible maps

Tags, labels and annotations are user-supplied key-value maps. Two things go wrong:

1. **The XRD declares them with fixed `properties` instead of `additionalProperties`.** Every
   key the user did not supply materialises as a null, which typed languages reject at parse
   time — and it is what a schema inferred from an example always produces. Write the XRD:

   ```yaml
   tags:
     type: object
     additionalProperties:
       type: string
   ```

2. **The value is passed straight through** as the language's schema object rather than a
   plain map. Convert explicitly before assigning it.

**Label values must also be Kubernetes-legal** — no `/` or `:`, max 63 characters. Sanitize
user-supplied tags before using them as labels.

---

## Pattern: merging

Where a language offers a merge (KCL's `|`, a spread, a dict update), **the later operand
wins**: defaults first, specifics last.

Some "update" operations are *replacements* at the nested level rather than deep merges, so
two successive writes to `status` leave only the second. Write one call with all the keys.
See the language file.

---

## Naming

`{type}-{resourceName}-{qualifier}` — e.g. `subnet-web-public-a`. Predictable keys make
`render.log` readable, which is the thing you actually debug against. Keep them stable: a
rename is a migration (top of this file).

---

## Reviewing function code, and a green test with a misbehaving resource

**When shown function code** — reviewing it, or checking your own before you report:
1. Check the language's required bootstrap is present.
2. Check imports resolve against the probe or the generated schemas, and match the project's
   generation: `.m.` paths in a v2 project (binding rule 5).
3. Judge `providerConfigRef`, `managementPolicies` and MR `metadata.namespace` by the review
   rule in `control-plane-project-charter` §5: removable unless the project's spec or API sets
   them.
4. Check flexible maps are converted to a plain map type.
5. Check the guard-clause order — does a return above the new resource gate it unintentionally?
6. Check a composed ProviderConfig is marked ready explicitly.

**When a test passes but the resource misbehaves on a control plane:**
1. Read the render (`control-plane-project-charter` `charter/evidence.md`) — the test may never
   have asserted the resource.
2. Look for a `providerConfigRef` whose `kind` and name match no object that exists; the
   symptoms are in `charter/v2-resources.md`.
3. Check the guard-clause chain and readiness branches; neither is exercised locally.

Language-specific error messages — Pydantic validation, KCL type errors, TypeScript
compilation — are in the matching `languages/` file.

---

## Migrating a function to v2

The language-neutral v1→v2 changes are in `plan-v2-migration`'s `breaking-changes.md`
reference; the spelling per language is in `languages/`. Two points belong to the function itself:

- Add the language's XR-parsing bootstrap where it is required (the language file says
  whether).
- Never rename a function to add a language suffix: the function name is the published
  registry path.
