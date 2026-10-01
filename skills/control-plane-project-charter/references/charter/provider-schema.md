# What the provider schema does and does not tell you

How sparse the recorded constraints really are, and the classes of rule that live only in the cloud API. [the charter §6](../../SKILL.md#6-the-provider-schema-is-a-lower-bound-not-the-constraint-set) states the rule.

---

**Expect this to be sparse, not systematic.** Measured over the namespaced AWS models in a real
project: `Conflicts with` in 12 of 127 Kinds, `Required if` in 3 — and those cluster in the big
Kinds like RDS `Instance`. Two consequences: the grep is cheap and worth running, and **finding
nothing is not evidence the API has no such rule.**

One false positive to filter out: *"At most one of each condition type may apply"* appears in
269 of 281 model files. It is the Kubernetes `Condition` docstring in every resource's *status*
block, not a provider input constraint.

**Then ask the structural question the models cannot answer:**

> **When an XR field is a list, is one resource — or one rule — per element actually correct
> for this API?**

Treat *one element → one object* as a decision you justify, not the default. These are the
rule classes that live only in the cloud API and never in a CRD schema:

| Class of rule | Example | Where it is written down |
|---|---|---|
| Uniqueness / non-overlap across a list | two S3 lifecycle rules whose filters both match the same prefix | AWS API docs only |
| Mutually exclusive combinations | a Table with both on-demand billing and provisioned throughput | AWS API docs only |
| Ordering and dependency | a policy referencing a role that does not exist yet | provider behaviour |
| Account- or region-scoped limits | one bucket-lifecycle configuration per bucket, not one per rule | AWS API docs only |

For S3 lifecycle the answer is a single `BucketLifecycleConfiguration` holding N rules, and
the rules must not overlap — a loop that emits one configuration per rule is wrong twice
over, and renders perfectly.
