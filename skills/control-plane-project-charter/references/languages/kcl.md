# KCL

Everything KCL-specific for a control-plane project: composition functions **and** tests.

The language-agnostic rules — the TDD loop, what a v2 managed resource needs, the container
boundary, what a green run proves, reporting discipline — are in
[`../CHARTER.md`](../../SKILL.md) and are **not** repeated here. Read the charter first; this
file only tells you how KCL expresses it.

| | |
|---|---|
| Scaffold a function | `up function generate <n> --language kcl` (KCL is `up`'s default) |
| Scaffold a test | `up test generate <n> --language kcl` (add `--e2e`) |
| Type-check a module | `kcl functions/<n>/main.k` |

---

# Part 1 — Imports and models

**Namespaced models use the `m`-suffixed import path.** This is the KCL expression of the
`.m.` namespaced-API rule in [`../CHARTER.md` §5](../../SKILL.md#5-crossplane-v2-what-a-composed-resource-actually-needs);
note that KCL puts the `m` on the *cloud* segment (`awsm`), where Python puts it before
(`m.aws`).

```kcl
# CORRECT - namespaced (note the 'm')
import models.io.upbound.awsm.ec2.v1beta1
import models.io.crossplane.kubernetesm.v1alpha1

# WRONG - cluster-scoped, missing 'm'
import models.io.upbound.aws.ec2.v1beta1
import models.io.crossplane.kubernetes.v1alpha1
```

### Import Examples by Provider

```kcl
# AWS (namespaced)
import models.io.upbound.awsm.ec2.v1beta1 as ec2v1beta1
import models.io.upbound.awsm.rds.v1beta1 as rdsv1beta1
import models.io.upbound.awsm.iam.v1beta1 as iamv1beta1

# Azure (namespaced)
import models.io.upbound.azurem.compute.v1beta1 as computev1beta1
import models.io.upbound.azurem.network.v1beta1 as networkv1beta1

# GCP (namespaced)
import models.io.upbound.gcpm.compute.v1beta1 as computev1beta1
```

---
The test-object models live under `models.io.upbound.dev.meta` (`CompositionTest`, `E2ETest`).
Your own XR's models are under `models.io.<reversed-group>.<version>`.

---

# Part 2 — Composition functions

---

## Where everything is

This file is the index. The rest sits in [`kcl/`](kcl/), so each file stays small enough to
read in one go.

| File | What is in it |
|---|---|
| [`kcl/patterns.md`](kcl/patterns.md) | module layout, the entry point, helper functions, and what a v2 managed resource needs |
| [`kcl/patterns-logic.md`](kcl/patterns-logic.md) | conditional creation, list comprehensions, selector-based references, type merging, optional fields |
| [`kcl/tests.md`](kcl/tests.md) | composition and E2E test templates, and test-structure patterns |
| [`kcl/pitfalls.md`](kcl/pitfalls.md) | KCL mistakes that render green and break later |
