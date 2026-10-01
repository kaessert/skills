# Composition patterns — what they mean

The language-agnostic half of composition authoring: what each pattern is *for*, when it
applies, and how it fails. The syntax for every one of them is in
[`languages/`](languages/); the rules that bind this skill are in
[`charter.md`](charter.md).

Nothing here is repeated from the charter. If you are looking for what a v2 managed resource
needs, the container boundary, the TDD loop, or what a green run proves, that is the charter.

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
one as new. Choose keys as deliberately as you would choose a field name, and treat a rename
as a migration.

---

## Pattern: module organisation

**One module per resource domain**, with the entry point doing orchestration only — imports,
parameter extraction, the config object, and calls into the modules.

This matters more than it looks. A single flat function accumulates guard clauses (below),
and the guard chain is the failure mode that composition tests cannot see. Splitting by
domain keeps each conditional local to the resources it actually governs.

A single-file function is fine for a genuinely simple composition. The test is whether you
can name the domains; if you can, split.

Syntax: [`kcl.md` Pattern 1-3](languages/kcl.md), [`python.md` Part 3](languages/python.md),
[`typescript.md` Part 3](languages/typescript.md).

---

## Pattern: the configuration object

Extract the XR's parameters **once**, into a single object, and pass that to every module.
The alternative — each module reaching into the XR itself — means a schema change touches
every module, and a defaulted field gets defaulted differently in two places.

Include in it: the core parameters, the feature flags, the lists, and the merged tags. That
object is also the natural place to apply defaults, so there is exactly one answer to "what
does this field mean when the user omits it".

---

## Pattern: the guard-clause chain — the failure composition tests cannot see

Template functions are written as a sequence of early returns:

```
if the bucket is not observed yet:        return
if it has no external name yet:           return
if versioning is disabled:                return
```

**Anything appended after those inherits every one of them.** A resource added at the end of
the function silently disappears whenever `versioning: false` — and no composition test will
tell you, because the test that renders with versioning enabled passes.

**Give each optional resource its own conditional block** rather than adding another early
return, and place it above unrelated guards. When you add to an existing function, read the
returns above your insertion point before you write anything: that is where this bug is
introduced, every time.

The corresponding test rule: one test per input shape, including a **minimal XR that omits
every optional field**. That is the test that catches an unintended guard.

---

## Pattern: conditional creation, and the `ready OR exists` rule

A resource created only when some other resource is ready must **also** be kept when it
already exists:

```
if dependency_is_ready OR resource_already_exists:
    create it
```

Testing only `dependency_is_ready` deletes the resource whenever the dependency briefly goes
un-ready — a cluster restart takes the Helm release with it. This is a real outage pattern,
not a theoretical one.

---

## Pattern: references beat status plumbing

When resource B needs an ARN, ID, or name produced by resource A, there are two ways to do it
and only one is good:

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

An XR field that is a list does **not** imply N resources. This is the single most expensive
design mistake in this skill's history, because it renders perfectly and fails only at the
provider.

Before writing the loop, answer three questions about the specific cloud API:

1. **Are the elements independent?** Or can two of them conflict — overlapping prefixes,
   overlapping CIDR ranges, duplicate keys?
2. **Does the API want one aggregate object holding N entries**, rather than N objects? S3
   lifecycle is exactly this: one `BucketLifecycleConfiguration` holding N rules, not N
   configurations.
3. **Is there an account- or region-scoped limit** that N elements would breach?

[`charter.md` §6](charter.md#6-the-provider-schema-is-a-lower-bound-not-the-constraint-set)
has the full rule classes and where they are written down. If you cannot establish the answer
from the models, say which API-level rule you were unable to confirm rather than assuming
independence.

**A related trap:** Upjet gives some list fields misleadingly **singular** names —
`attribute`, `globalSecondaryIndex`. Reading the field name alone will convince you it holds
one value. Read the generated type.

---

## Pattern: namespace propagation

Crossplane v2 propagates the XR's namespace to every composed resource. So:

- **Managed resources**: omit `metadata.namespace` entirely. Confirmed in `render.log` — MRs
  the function never gave a namespace still come out namespaced.
- **Composed child XRs**: same. The namespace follows.
- **Kubernetes objects you compose yourself** (a `Secret`, a `ConfigMap`): these are the one
  legitimate case for setting a namespace, because you are choosing where the object lands.

---

## Pattern: connection details

**Access observed resources by composition key**, not by the resource's rendered name. The
key is the string you used in `rsp.desired.resources["key"]`; the rendered name is derived
and includes a hash suffix.

In v2 there is no `writeConnectionSecretsToNamespace` on the composition. To surface
credentials, compose the `Secret` yourself in the XR's namespace, gathering values from the
observed resources' connection details.

**That branch does not execute in a composition test.** It reads observed state, and a local
render has none. Cover it with `observedResources` in a test, or say it is unverified.

---

## Pattern: ProviderConfig readiness

A ProviderConfig you compose (a Helm or Kubernetes ProviderConfig pointing at a cluster you
just created) must be marked ready **after** you write the resource, never before. Writing
the resource replaces what is at that key, so a readiness flag set first is discarded.

The general form of this rule: **write, then annotate**. Any per-resource metadata you set
before writing the resource is lost.

---

## Pattern: flexible maps

Tags, labels and annotations are user-supplied key-value maps. Two things go wrong:

1. **The XRD declares them with fixed `properties` instead of `additionalProperties`.**
   This is wrong for a map: every key the user did not supply materialises as a null, which
   typed languages reject at parse time. It is also what a schema inferred from an example
   always produces, since the example only shows the keys it happens to use. Write the XRD:

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

Where a language offers a merge (KCL's `|`, a spread, a dict update), **order matters and the
intuition is usually backwards**: defaults first, specifics last, because the later operand
wins.

One language-specific hazard worth knowing about generally: some "update" operations are
*replacements* at the nested level rather than deep merges, so two successive writes to
`status` leave only the second. Write one call with all the keys. See the language file.

---

## Naming

`{type}-{resourceName}-{qualifier}` — e.g. `subnet-web-public-a`. Predictable names make
`render.log` readable, which is the thing you actually debug against.

Keep names stable. See the composition-key note at the top: a rename is a migration.

---

## Where each pattern's syntax lives

| Pattern | KCL | Python | TypeScript |
|---|---|---|---|
| Module organisation | Patterns 1-3 | Part 3 | Part 2 |
| Entry point / bootstrap | Pattern 2 | Pattern 2 | Pattern 1 |
| Configuration object | Pattern 4 | Part 3 | Pattern 7 |
| Helpers (metadata, labels) | Pattern 5 | Pattern 4 | Pattern 7 |
| Conditional creation | Pattern 6 | Pattern 8 | Pattern 4 |
| Lists / comprehension | Pattern 7 | Part 3 | Pattern 5 |
| Selectors and refs | Pattern 8 | Part 3 | Pattern 6 |
| Merging | Pattern 9 | Pattern 4b | Pattern 10 |
| Optional fields | Pattern 10 | Pattern 4c | Pattern 10 |
| Namespace propagation | — | Pattern 5 | — |
| Connection details | — | Patterns 6, 9 | — |
| ProviderConfig readiness | — | Pattern 7 | — |
| Flexible maps / XRD schema | Pattern 5 | Pattern 10 | Pattern 7 |

A dash means that language's reference does not yet document the pattern — the pattern still
applies, and adding it is a useful contribution.
