---
name: control-plane-project-charter
description: Shared rules and per-language references that the Upbound control-plane-project skills load first - agent behaviour, the test-first loop, what a v2 composed resource needs, the container boundary, what a green run proves, how to report, and the KCL, Python, TypeScript, Go and YAML references. Not the skill to pick for doing the work - choose the task skill, which loads this one itself - author-composition for composition function code, author-tests for composition or E2E tests, author-configuration-package for scaffolding, XRDs and dependencies, verify-configuration to build, verify or run the project, e2e-test-configuration to run E2E tests, and plan-v2-migration or execute-v2-migration for a Crossplane v2 migration.
license: Apache-2.0
references:
  - references/charter/agent-context.md
  - references/charter/container.md
  - references/charter/evidence.md
  - references/charter/generators.md
  - references/charter/provider-schema.md
  - references/charter/tdd.md
  - references/charter/v2-resources.md
  - references/charter/xrd-design.md
  - references/languages/README.md
  - references/languages/go.md
  - references/languages/kcl.md
  - references/languages/kcl/patterns-logic.md
  - references/languages/kcl/patterns.md
  - references/languages/kcl/pitfalls.md
  - references/languages/kcl/tests.md
  - references/languages/python.md
  - references/languages/python/examples.md
  - references/languages/python/imports.md
  - references/languages/python/patterns.md
  - references/languages/python/pitfalls.md
  - references/languages/python/readiness.md
  - references/languages/python/test-templates.md
  - references/languages/python/tests.md
  - references/languages/typescript.md
  - references/languages/yaml.md
---
# Development Charter

**Every skill in this plugin follows this charter.** It holds the rules that do not depend on
which language a project is written in or which skill you happen to be: how to behave as an
agent, how to develop, what Crossplane v2 actually requires, and how to report what you did.

Language-specific syntax lives in [`languages/`](references/languages/) — one file per language. Skill
workflows live in each skill's `SKILL.md`. Nothing in this file is language-specific, and
nothing in it is optional.

When a skill's own guidance contradicts this charter, **the charter wins** — and that
contradiction is a bug worth fixing in the skill.

**This file holds the rules; the detail sits beside it in [`charter/`](references/charter/).** Read this
one end to end — it is short on purpose. Follow a link when you need the evidence, the tables
or the worked example behind a rule.

| Detail file | What is in it |
|---|---|
| [`charter/agent-context.md`](references/charter/agent-context.md) | what inline and forked (separate-agent) skills may and may not do (§1) |
| [`charter/tdd.md`](references/charter/tdd.md) | the two-tier inner loop, and backfilling tests for existing code (§3) |
| [`charter/v2-resources.md`](references/charter/v2-resources.md) | the v2 XRD skeleton, what CRD defaults do to a render, choosing a ProviderConfig (§5) |
| [`charter/xrd-design.md`](references/charter/xrd-design.md) | naming, validation, immutability, status and printer columns for the XR API (§5) |
| [`charter/provider-schema.md`](references/charter/provider-schema.md) | measured constraint density, and the rules that live only in cloud API docs (§6) |
| [`charter/container.md`](references/charter/container.md) | which languages are containerized, and what crosses the boundary (§7) |
| [`charter/evidence.md`](references/charter/evidence.md) | reading a render, how `assertResources` matches, making a suite exhaustive (§8) |
| [`charter/generators.md`](references/charter/generators.md) | the `--language` slugs, and what each CLI generator actually emits (§10) |

---

## 1. Know which kind of agent you are

How you were started decides whether you can hold a conversation: loaded into the user's
conversation (inline), or handed a brief as a separate agent (forked). Know which you are
before you consider asking anything.

When a skill says to hand work to a sub-agent, or to run a command in the background, use
your harness's own way of doing that. If it has none, do the work in band: follow the brief
yourself, or run the command in the foreground — never detach it yourself.

**Detail:** [`charter/agent-context.md`](references/charter/agent-context.md) — what each context may and may not do, why a fork's only output channel is prose, and how to delegate or run long commands when your harness cannot.


## 2. Discover, do not interview

Whatever your `context:`, the project answers most questions faster and more reliably than
the user does.

| What you need | Where it is |
|---|---|
| Project root | `args`, or the nearest ancestor containing `upbound.yaml` |
| XR kind, group, version, spec schema | `apis/*/definition.yaml` |
| Existing composition + `functionRef` | `apis/*/composition.yaml` |
| Available provider families | `upbound.yaml` `spec.dependsOn` |
| Example XR shape | `examples/*/*.yaml` — one directory per XR kind, the file named for the XR. **Not** always `example.yaml` |
| Composition language | `functions/*/` contents — see [`languages/`](references/languages/) |
| Test language | `tests/*/` contents — **independent of the composition language** |
| Provider field names, types and constraints | the generated models under `.up/` |
| Current Space / group / control plane | `up ctx . --short` |

Read the XRD's **defaults** before you design anything against it. `up test run` applies them
itself — it derives a CRD from the XRD and runs Kubernetes' structural-defaulting library over
the XR before the pipeline sees it — so a field with a `default:` reaches your function whether
the example sets it or not, and a test that asserts only what the example mentions is asserting
the XRD's defaults back to itself.

Two limits, and they are easy to trip over:

- **Only if the test sets `xrdPath` (or inline `xrd`).** Without it the XR is rendered exactly
  as written and no defaulting happens at all.
- **The XR only.** Composed resources are never touched by this. Provider *CRD* defaults are a
  different mechanism — see §5.

---

## 3. Develop test-first (RED → GREEN → REFACTOR)

This is the plugin's default flow for composition code, tests, and migrations alike.
`author-tests` owns the authoring detail; the loop itself is
here because every skill is bound by it.

**Why test-first here specifically.** Every evaluation round of these skills has produced the
same finding: coverage reported that did not exist — *"covers the conditional branch"*,
*"Coverage: complete"* — for tests that could not have failed. Writing the test first and
**watching it fail** is the only thing that makes a coverage claim checkable rather than
aspirational. You do not have to argue that the test would catch a regression; you saw it
catch the absence of the implementation.

### The loop

1. **RED — write the test, run it, and read the failure.**

   ```bash
   up test run "tests/<t>"      # expect: FAIL
   ```

   Run it directly. Do not route this through `verify-configuration`: that skill builds,
   deploys and talks to a control plane, which is not an inner loop.

   **A failure is only RED if it fails for the reason you intended.** Check the message:

   | Failure | Verdict |
   |---|---|
   | `no actual resource found` for the resource you are about to compose | valid RED |
   | a field mismatch naming the exact field you are adding | valid RED |
   | a syntax error, an unresolved import, a missing `compositionPath` | **not** RED — the test is broken, not the code. Fix it before writing any implementation |
   | passes immediately | **not** RED — the assertion is vacuous, or the behaviour already exists |

   Record the failure text. It goes in your report as the evidence that the test bites.

2. **GREEN — implement** until the test passes, and no further.

3. **REFACTOR** with the suite green, then add the next failing assertion and repeat.

**Detail:** [`charter/tdd.md`](references/charter/tdd.md) — the two-tier inner loop (every `up test run` pays a full build, so use a fast tier for crashes), and how to backfill tests for code that already works by proving each one can fail.

## 4. Report the effect, not the intent

Every skill in this plugin that reported success in a recent evaluation overstated what it
had verified — a green composition suite reported as "production-ready", a local KIND run
reported as a Space pass, "all resources Ready" pasted above a tree showing `Ready=False`,
provider values "verified" that were read back off the input manifest. The pattern is always
the same: asserting what the change was *meant* to do instead of reading back what it *did*.

Before writing any summary:

1. **Name what you actually ran**, and what its exit code was.
2. **Re-read the evidence you are about to paste** and check it does not contradict your
   verdict.
3. **Distinguish the layers.** A render is not an install; an install is not a provider
   accepting the resource; `Ready=True` is not the provider holding the value you meant.
   Say which layer you reached.
4. **When you did not verify something, say so plainly.** "Not verified at the provider" is
   a useful report. A checkmark you cannot support is not.
5. **A coverage claim is a claim about what would fail.** Before writing "covers X",
   "complete", or "N/N", answer: *what change to the code would make this go red?* If you
   cannot name one, you have not covered X — you have written something that passes. This
   is where the reports go wrong most often: "covers the conditional branch" and
   "Coverage: complete" were both false for the very test the skill had just written.
6. **Drop the checkmark register.** `✅ Complete`, `PASS`, and a tidy summary table read as
   verification regardless of what is behind them, and they are what makes an overstated
   report persuasive. Write what ran, what it printed, and what remains unknown. If the
   honest summary is "tests pass; provider validity unchecked; not deployed", that is the
   summary — it is more useful to the caller than a confident one that is wrong.

**Abort on a failed precondition; do not proceed and report the symptom.** A check that
comes back *blocked* — not merely *failed* — means the run you are about to start cannot
produce a valid result. Starting it anyway spends real time and produces a failure whose
cause you already knew.

---

## 5. Crossplane v2: what a composed resource actually needs

### The `.m.` API groups

Compositions target the `.m.` provider API groups. **`.m.` is for *modern*, not
"naMespaced"** — the groups hold the namespaced managed resources *and* the cluster-scoped
`ClusterProviderConfig` they default to, which is why the "namespaced" reading cannot be right.

| Aspect | Use this | Not this |
|---|---|---|
| Managed resource `apiVersion` | `<service>.<cloud>.m.upbound.io/v1beta1` (Upbound providers) or `<...>.m.crossplane.io/v1beta1` (community) | the same group without `.m.` |
| XRD | `apiextensions.crossplane.io/v2` + `scope: Namespaced` | `v1` + cluster-scoped |
| **Composition** | **stays `apiextensions.crossplane.io/v1`** | there is no `v2` Composition — do not bump it |

**Write the XRD yourself** rather than inferring it from an example with `up xrd generate`: an
example carries values, never constraints, so an inferred schema loses every `required:`,
`default:`, open-ended map and `status` field you meant to have.
[`charter/v2-resources.md`](references/charter/v2-resources.md) has the verified v2 skeleton and the
model-quality comparison.

**Then design the schema, do not just transcribe fields.** A schema that parses can still be
one nobody can consume: no `description` means `kubectl explain` documents nothing, no `enum`
or `pattern` means bad input fails in the provider rather than at `kubectl apply`, and an empty
`status` means the caller cannot learn what the composition computed. Because XRD versions must
round-trip, most of this is permanent from the first version that ships, so it is cheap at
`v1alpha1` and impossible later.
[`charter/xrd-design.md`](references/charter/xrd-design.md) has the rules, the CEL patterns, and the
`--dry-run=server` loop that proves them on a control plane.

### Set `forProvider`, and stop

Crossplane v2 fills in the rest. Adding "required v2 fields" is at best noise and at worst
breaks the resource.

| Field | Do you set it? | Verified behaviour |
|---|---|---|
| `metadata.namespace` | **No** | **If the XR is namespaced**, Crossplane overwrites it with the XR's namespace (`if xr.GetNamespace() != "" { cd.SetNamespace(...) }`), so a function setting a *different* namespace is silently overridden, not merged with. A **cluster-scoped** XR is the exception — its composed resources keep the namespace the function sets, which is how a cluster XR targets one. (A namespaced XR composing a cluster-scoped kind is a hard error, not a namespace question.) |
| `managementPolicies` | **No** | The namespaced MR spec carries `+kubebuilder:default={"*"}`, so the API server fills it in. Set it only for a genuinely different policy — e.g. `["Create","Observe","Update","LateInitialize"]` to orphan on delete, which for a namespaced MR is the *only* way to orphan: there is no `deletionPolicy` field on the namespaced spec at all. |
| `providerConfigRef` | **No** | The same struct, the same way: `+kubebuilder:default={"kind":"ClusterProviderConfig","name":"default"}`. |
| `metadata.name` | Only for a stable external name | Otherwise Crossplane generates `<prefix>-<sha256(xr-uid + composition-resource-name)[:12]>`, where the prefix comes from the `crossplane.io/composite` label, truncated to 63 chars. Deterministic for one XR instance, **not** across re-creations — and it falls back to a random 5-char suffix when the composition-resource-name annotation or the controller ownerRef is missing. Inside a *render* it is fully deterministic and safe to assert — see §8. |
| `crossplane.io/composition-resource-name` | Never by hand | It comes from the key you store the resource under. |

**Detail:** [`charter/v2-resources.md`](references/charter/v2-resources.md) — what these CRD defaults do to a render (it differs by language), when a `providerConfigRef` is genuinely warranted, and the two greps that catch a hardcoded one.

## 6. The provider schema is a lower bound, not the constraint set

Namespaced APIs and `forProvider`-only are *Crossplane* correctness. They say nothing about
whether the provider will accept the resource. A composition can be perfectly v2-conformant
and still emit a resource AWS rejects — observed: lifecycle rules with neither `filter` nor
`prefix`, which fail with `MalformedXML`, while composition tests passed.

**First, read what the models do record.** Some generated models carry conditional rules the
type system cannot express, in docstrings and field descriptions: *"Required if
`source_db_instance_identifier` is not specified"*, *"Conflicts with `domain_fqdn`,
`domain_ou`"*, *"If set, must contain at least one key-value pair"*. A field being optional in
the generated type means only that the **CRD** does not require it — the provider still can.

**Expect this to be sparse, not systematic**, and treat *one list element → one object* as a decision you justify rather than the default. [`charter/provider-schema.md`](references/charter/provider-schema.md) has the measured hit rates, the one docstring that is always a false positive, and the rule classes that appear only in the cloud API docs.

State the result in your summary: which Kinds you checked, what the schema required, and
which API-level rule you could not confirm. "I checked and found nothing" is a valid result.
Silently skipping is not.

---

## 7. The container boundary

**Detail:** [`charter/container.md`](references/charter/container.md) — which languages are containerized, how `UP_`-prefixed variables are forwarded, and the tighter second boundary around function rendering.


## 8. A green run is not evidence

| Green thing | What it actually proves |
|---|---|
| `up project build` | the package was assembled. For KCL and single-file Python it does not import, type-check, or execute anything — a function with an `AttributeError` on its normal path builds cleanly. **Go is different**: the build runs `go mod tidy` and a real compile, so a Go function that does not compile fails here. The Python SDK builder runs `hatch build` + `pip install`, so packaging and dependency errors fail too, but `fn.py` is still never imported. Either way, a clean build never proves the function *runs*. |
| A composition test suite | the assertions you wrote held against the render. `assertResources` is **partial and positive for objects**: it ignores composed resources it does not list, and within a resource it checks only the fields you name, at every depth. **Lists are the exception** — an asserted list must match the rendered one exactly in length *and* order, or you get `lengths of slices don't match`. A short list assertion is not a weak assertion; it is a failing one. |
| A render | the function produced objects. Not that the API server accepts them, and not that the provider does. |
| `Ready=True` | the provider reconciled *something*. Read back the field you meant, from the live object, not from the input manifest. |

**`up test generate` emits a stub that does not even run.** `assertResources: []` plus empty
`xrPath`, `compositionPath` and `xrdPath`, and the empty `compositionPath` fails before any
assertion is reached:

```
cannot load Composition from "": not a composition: /
```

Per §3's table that is a **broken test, not RED** — fill the paths in first.

The vacuous pass is the *next* state: correct paths, and an `assertResources` list you never
populated. An empty expected list produces no errors, so that test is green and means nothing
whatsoever.

A filled-in single test is not much better: one input shape, asserting only composed
resources, passes over a function that crashes on a minimal XR and drops three of four status
fields.

**Observed-state branches are reachable, and you are expected to reach them.** A render starts
with no observed resources *unless the test supplies `spec.observedResources`*. So code gated
on observed-and-ready is dead in a test that omits that field and live in one that sets it —
write the second test rather than declaring the branch untestable. Then be precise about what
it proves: your branch logic, given the status you wrote. It does not prove a provider ever
reports that status. For that, `--e2e` or a live apply — or say it is unverified.

**Detail:** [`charter/evidence.md`](references/charter/evidence.md) — finding the render artifacts, how `assertResources` matches a resource, and asserting `spec.crossplane.resourceRefs` so a surplus resource fails the suite.


## 9. Never create infrastructure as a side effect

A group, a Space, a control plane, or a published package is the user's decision.

- **Never create a control-plane group** to make a command work. `--control-plane-group`
  defaults to the current context's group, and an empty group falls back to the kubeconfig
  namespace and then to the literal `default` — a cloud control plane in group `default` is a
  real thing you just created, not a no-op.
- **Check the context is in a Space before you start.** If the current kubeconfig context is
  *not* an Upbound Space context — a plain EKS or docker-desktop context — the run silently
  uses a **local KIND cluster** instead, which is a different result rather than a fallback.
  A Space-level context does not trigger this; a non-Space one does. `up ctx . --short` tells
  you which you have.
- **`--public` publishes the user's package.** It is a disclosure decision, never a debugging
  step. It applies only to repositories the command *creates*: pushing to a repository that
  already exists leaves its visibility untouched. `up repository update --private` can flip
  the flag back afterwards, but it cannot un-publish what was already fetched — treat the
  disclosure as irreversible even though the setting is not. Accepted by `up test run`,
  `up project push`, `up project run` and `up project simulate create`.
- **Deleting is never cleanup you decide on.** Report what you would delete and let the user
  choose.

---

## 10. Language dispatch

The composition language and the test language are **independent axes** — `up project init`
takes `--language` and `--test-language` separately, and a Python-function project commonly
uses YAML tests. Detect each from its own directory, then read the matching file:

| Detected | Read |
|---|---|
| `functions/*/*.k`, `tests/*/*.k` | [`languages/kcl.md`](references/languages/kcl.md) |
| `functions/*/{main.py,function/fn.py}`, `tests/*/{main.py,test/__main__.py}` | [`languages/python.md`](references/languages/python.md) |
| `functions/*/*.ts` | [`languages/typescript.md`](references/languages/typescript.md) — the CLI has no TS builder yet, so these projects are hand-built; its header says what to do instead |
| `tests/*/*.yaml` with no other test source | [`languages/yaml.md`](references/languages/yaml.md) |
| `functions/*/*.go`, `tests/*/*.go` | [`languages/go.md`](references/languages/go.md) |

**Detail:** [`charter/generators.md`](references/charter/generators.md) — the accepted `--language` slugs, what each generator actually emits (`up project init` produces a **v1** project; `up test generate` prepends `test-`; `up composition generate` wires only auto-ready), and why the XRD is the one file you author by hand.
