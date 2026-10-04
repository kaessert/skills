# Designing the XRD schema

Naming, validation, immutability and status for the API your users type against. [`control-plane-project-charter` §5](../../SKILL.md#5-crossplane-v2-what-a-composed-resource-actually-needs) covers what a *composed resource* needs and why you write the XRD by hand; this covers what to put in it.

---

## Everything here is driven by one constraint

Two XRD versions are two views of the same stored object, so any change must round-trip losslessly. That makes most of a schema permanent from the first version that ships.

| Across versions you can | You can never |
|---|---|
| Rename a field (`spec.widgets` → `spec.widgetCount`) | Drop a field an older version requires |
| Move a field (`spec.shape` → `spec.properties.shape`) | Add a required field an older version lacks |

A new version buys you almost nothing, so do not plan to fix the schema in `v1beta1`. `v1alpha1`, before anything depends on it, is the only cheap moment. Every rule below is cheap now and impossible later.

A field can be renamed across versions. **The Kind cannot.** It is the GVK and the CRD's `spec.names.kind`; renaming it stops the CRD serving the old name and every stored object of that type becomes unreadable. `HttpLoadbalancer`, which wants to be `HTTPLoadBalancer`, is cheap to fix before `v1alpha1` ships and effectively permanent after.

If you script a casing fix, match on **word boundaries**: end of string, or followed by an uppercase letter. A bare `ReplaceAll(s, "Api", "API")` reaches inside longer words and rewrites `apiep` (from `api_ep`) to `APIep`.

---

## Name fields for your API, not for the backend

**Do not repeat the group or kind in a field name.** With group `artifactory.example.com` and kind `Repository`, `spec.artifactoryRepositoryName` reads as `artifactory.Repository.artifactoryRepositoryName`. It wants to be `spec.name`. The stutter usually arrives on only some fields, so the API ends up inconsistent as well as verbose.

**But a field that merely starts with the group's word is not automatically stutter**, and this is the one place the rule is regularly over-applied. Three field names on a `Route` in group `gateway.example.com` look identical to a prefix match and are not the same thing:

| Field | Verdict |
|---|---|
| `gatewayRouteName` | Stutter. It restates this object's own identity, and wants to be `name`. |
| `gatewayName` | Fine. It names a **different** object, the gateway this route attaches to. `name` would be worse, because it no longer says whose. |
| `gatewayTimeoutSeconds` | Fine, or at least arguable. "Gateway Timeout" is HTTP 504, a compound term rather than a repeated qualifier. `timeoutSeconds` is still the better name here, but for concision, not stutter. |

The test is whether the word is restating *this* object or naming another one. That is semantic, so treat a prefix match as a question to answer rather than a defect to fix.

**An initialism is a casing decision, and the two surfaces answer it differently.**

| Surface | Rule | Examples |
|---|---|---|
| **Field** | lowerCamel, initialism title-cased | `vpcId`, `projectId`, `instanceId`, `bucketArn`, `cacheTtlSeconds` |
| **Kind** | initialism in full | `VPC`, `DNSRecord`, `OIDCProvider`, `HTTPLoadBalancer` |

This is deliberately *not* the Kubernetes core convention. Core spells them `containerID`, `imageID`, `storagePolicyID`, and copying that into an XRD is the mistake: across the Crossplane resources your users see beside your XR, the field surface is title-case throughout. `vpcID` on your XR next to `vpcId` on everything around it is one concept with two spellings, and a reader pays for it every time.

**Orthography is not vocabulary**, and the distinction matters because this file argues both sides. Choosing `repositoryClass` over a backend's `rclass`, or `Enabled` over `on`, is your platform's vocabulary and yours to set; that is what "not a thin wrapper" means. `Id` versus `ID` is not a naming decision at all. Diverging on it buys nothing and costs a double-take, so follow the convention and spend the design budget on the names that carry meaning.

The failure is silent either way: a wrong guess is a schema mismatch nobody notices, not an error.

**Get the Kind right, because it is the one you cannot fix.** A field can be renamed across versions; the Kind is the GVK and `spec.names.kind`. `HttpLoadbalancer` should be `HTTPLoadBalancer`: two defects, only one of them mechanical, since no table can see the missing word boundary in `Loadbalancer`.

For the Kind, an **allowlist of tokens that must be upper-cased** is what scales, each written with the expansion it stands for. The allowlist is inverted from the intuitive design, and the inversion is the reason it works. A *registry* of canonical initialisms, used to decide what casing is wrong, fires on every name it does not know, so nearly every hit is a gap in the registry rather than a defect, and the check gets switched off. An allowlist used the other way can only ever produce a **missed defect**, never a false alarm. An entry nobody can expand does not belong in it.

The field surface needs no list at all. Under the title-case rule no word in a correct field name is ever all-caps, so any all-caps run of two letters or more is a defect without consulting a table, which is registry-free and safe against an acronym nobody wrote down.

Two rules neither approach makes for you:

- **Stacked acronyms, on a Kind.** Canonicalising both halves of `VmiId` gives `VMIID`, readable as neither "VMI ID" nor one word. Expand the leading one into a word: `VMInstanceID`. On the *field* surface this never arises: `vmiId` is already correct.
- **Invented abbreviations.** `adminsSG` forces `SG` vs `Sg`, and in a Crossplane codebase `SG` reads as an AWS security group whatever you meant. Title-casing it to `adminsSg` answers the casing question and leaves the worse one. No list catches this, because the token is yours. `adminGroups` has no casing question and no second reading.

**Consistency checking alone reports this schema clean.** Comparing every field name against every other, case-insensitively, catches `projectID` beside `ProjectId`: one concept, two spellings. It is blind to an acronym spelled two ways across names that never collide, such as `tlsConfig` beside `tlsParameters`, or one name carrying both spellings inside itself.

So run both. Neither subsumes the other.

---

## Constrain every string, and say what it is

A field with only `type: string` and no `description` accepts anything and documents nothing. Descriptions are the API: they are what `kubectl explain` and the console render, so a schema without them cannot be consumed without reading the composition.

| Add | When |
|---|---|
| `description` | Always. No exceptions. |
| `enum` | The value is one of a known set |
| `pattern`, `minLength`, `maxLength` | The backend will reject some strings |
| `default` | There is a safe value, especially the most restrictive one |

The payoff is where the failure surfaces. Without constraints, a bad value is accepted at `kubectl apply` and fails inside the provider minutes later, with an error the user cannot map back to the field they typed.

**Verify bounds against vendor documentation, not from memory.** Guessing produces confident, wrong constraints in both directions: too tight rejects the user's own valid input, too loose defers the failure again. Backend key rules in particular are rarely what you assume, and they often vary by resource subtype, which a single `pattern` cannot express. Those parts belong in CEL (below).

---

## One field, one axis

Before adding a field, check that its name names exactly one thing. A field called "type" on a repository API sounds obvious and is usually two concepts: the *package* type (`maven`, `docker`) and the repository *class* (`local`, `remote`, `virtual`). Conflating them hides the second axis somewhere unvalidated, typically inside `metadata.name` as a suffix the composition then has to parse back out.

The tell is that the missing axis has its own configuration. Once the class is a real field, each class needs different input, and that is the **variant pattern**: a discriminator plus one block per variant.

```yaml
spec:
  repositoryClass: Remote
  remote:
    url: https://registry.example.com
  # virtual:
  #   repositories: [a, b]
```

Gate the blocks so an invalid combination cannot be stored:

```yaml
x-kubernetes-validations:
- rule: 'self.repositoryClass == "Remote" ? has(self.remote) : !has(self.remote)'
  message: spec.remote is required when repositoryClass is Remote, and must be absent otherwise
```

Adding `remoteUrl` as a flat sibling later also works, but you can never make it required and the ambiguity is permanent.

---

## Booleans do not grow; enums do

A boolean is a two-value enum that can never gain a third. Ideas that start as `fast: true` trend toward a small set of mutually exclusive options, and configuration that starts as `xrayIndex: true` grows policies and schedules with nowhere to put them.

```yaml
xray:
  indexing: Enabled   # Enabled | Disabled, and room for xray.policy later
```

A bare boolean with no `default` also leaves unset and `false` indistinguishable to the composition.

**Enum values are CamelCase with an initial capital**, per the [Kubernetes API conventions](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md#constants): `ClusterFirst`, `Pending`, `ClientIP`. The XR is your platform's contract, not a thin wrapper, so translating to the backend's vocabulary is the composition's job. Two exceptions are defensible:

- **A proper noun with established casing** (`npm`, `PyPI`, `NuGet`), where CamelCasing produces something wrong (`Npm`) and reintroduces the casing trap.
- **Values that mirror an upstream API verbatim**, when the platform deliberately passes them through and consumers already use them: AWS engine names (`aurora-postgresql`, `oracle-se2`), protocols (`udp`). Translating them is the composition's job only when the XR presents its own vocabulary; when it doesn't, renaming them gains nothing and breaks recognition.

Write each exception down with its reason — in the field's description, and in the project's `xrd-schema-exceptions.yaml` so that `check_xrd_schema.py` records it rather than failing on it forever.

---

## Required is permanent; a default is not

When you add a required field, assume you will never remove it. Prefer optional with a sensible default, and reserve `required` for fields with genuinely no safe value.

Defaulting to the most restrictive option is the strongest form of this: if `access` defaults to `Private`, forgetting the field cannot publish anything. Defaults also make the fallback discoverable through `kubectl explain` instead of hiding it in the composition, and they shrink what users have to type.

---

## Make destructive edits impossible

Ask of every field: what happens if someone edits this on a live object? When the answer is "the backend destroys and recreates the resource", a one-word `kubectl edit` is a data-loss event with no guard. Add a transition rule:

```yaml
x-kubernetes-validations:
- rule: self == oldSelf
  message: repositoryName is immutable
```

Identity fields, names, classes, types and project or account keys are almost always in this category.

---

## Lists need a type and a bound

```yaml
type: array
items:
  type: string
maxItems: 32
x-kubernetes-list-type: set
```

Without `x-kubernetes-list-type`, a list is atomic: duplicates are accepted, and two controllers or two people doing server-side apply clobber each other instead of merging. Use `set` for unordered unique scalars and `atomic` where order is meaningful, such as a virtual repository's resolution order. `maxItems` is not only hygiene: CEL rules are costed against the declared maximum, so an unbounded list can leave no budget for the validations you want later.

**Never reach for `uniqueItems: true`.** It is the obvious way to write "the backend rejects duplicates" and it is forbidden in a CRD schema: the API server refuses to create the CRD at all, with `uniqueItems cannot be set to true since the runtime complexity becomes quadratic`. `x-kubernetes-list-type: set` is the construct that means this, and it is enforced on admission rather than quadratically.

---

## `status` is the half of the API people forget

Crossplane injects `status.conditions` and nothing else. An empty `status` means a user who created the object cannot learn anything the composition computed: the URL, the key it actually got, the resolved identifier.

They usually cannot derive it either, because composition naming is rarely the object name. Surface what the caller cannot compute:

```yaml
status:
  type: object
  properties:
    repositoryKey: {type: string, description: Key the repository was created with}
    url: {type: string, description: Base URL at which the repository can be reached}
```

---

## Printer columns: add the ones Crossplane does not

`kubectl get` with no `additionalPrinterColumns` shows name and age. It is the highest value per line in the whole file, with one trap:

**Crossplane already appends `SYNCED`, `READY`, `COMPOSITION`, `COMPOSITIONREVISION` and `AGE` to every XR.** Defining any of them yourself prints it twice:

```
NAME       ENV    CLASS  PACKAGE  KEY  URL  SYNCED  READY  AGE  SYNCED  READY  COMPOSITION  AGE
```

Add only columns Crossplane cannot know: the spec fields that distinguish one instance from another, and the status fields you just declared.

---

## Namespace or spec field

Under `scope: Namespaced` the namespace is already a tenancy boundary. Before adding a field that names an environment, tenant or team, ask whether the namespace carries it. Stating it twice creates drift you cannot prevent, such as an object in namespace `default` carrying `environment: Stage`.

This is a real design decision rather than a rule: a team may keep the field deliberately, for instance when the value selects a backend instance rather than an isolation boundary. If it stays, give it an enum and an immutability rule, and note in the schema that nothing ties it to the namespace.

---

## Check the names mechanically, and assert the corpus

```bash
python3 <author-configuration-package>/scripts/check_xrd_schema.py \
  apis/*/definition.yaml
```

`<author-configuration-package>` is the directory containing that skill's SKILL.md, beside the
charter's own directory.

Collisions, allowlist casing, group stutter, enum casing, missing descriptions, unbounded lists and printer columns Crossplane already appends are all greppable out of the YAML, before any cluster is involved. The script's `ACRONYMS` table applies to the **Kind only**: trim it to the acronyms this API actually uses, and add entries only with the expansion written beside them. Field casing needs no table, because the title-case rule makes any all-caps run a defect on its own.

Booleans, bare strings and group stutter print as `REVIEW`, not `FAIL`. A check that fails every boolean gets disabled, and each of these is a judgement: whether `gatewayName` restates this object or names another one is not something a prefix match can decide.

One trap sits underneath all of it: **a check whose corpus is empty reports every schema clean.** Assert the corpus size before trusting the verdict, and exit non-zero on extraction failure with a different code than on a finding. The script exits `0` clean, `10` on a finding and `2` when it extracted nothing, so a caller can tell a pass from a silence.

What the check does not look at, deliberately: **kind stutter** (`repositoryClass` is a good name and `repositoryName` is not, the difference is semantic, and a check firing on both pushes someone to break the good one); which fields are **identity fields** needing `self == oldSelf`; and whether a `pattern` matches what the backend actually enforces. Those stay review judgements.

---

## Prove the schema on a control plane

A schema that parses is not a schema that works. CEL expressions are compiled by the API server, not by your YAML parser, so a rule with a typo is invisible until something applies against it. `--dry-run=server` exercises the whole admission path and writes nothing:

```bash
kubectl apply -f apis/<resource>/definition.yaml
kubectl apply --dry-run=server -f /tmp/bad-xr.yaml     # must be REJECTED, and say why
kubectl apply --dry-run=server -f examples/<r>.yaml    # must be ACCEPTED
kubectl patch <kind> <name> -n <ns> --type=merge --dry-run=server \
  -p '{"spec":{"<immutable-field>":"other"}}'          # must be REJECTED
```

Write one rejection case per rule, plus a valid control that must pass. A suite where everything is rejected proves nothing: it is equally consistent with a schema that rejects everything.

Then read `kubectl get` output once, with real objects in it. Duplicate printer columns, a defaulted field that did not default, and a status that never populates are all invisible in the source and obvious in the table.
