---
name: author-configuration-package
description: Use this skill when user requests to create, scaffold, modify, or extend a Crossplane configuration package. Handles project initialization, XRD creation/modification, composition setup, dependency management, function generation, building, and setting up the local development environment. Use immediately when user mentions creating/scaffolding/modifying/extending a configuration package, adding new resources to an existing package, installing or adding a provider ("add provider-aws-s3", "install the AWS provider", `up dep add`), or setting up the Python environment ("configure a venv", "my imports do not resolve", "set the VS Code interpreter"). Use this skill instead of manually creating project structures, XRDs, or running `up project init`/`up function generate` commands directly. This skill ensures correct build order, proper scaffolding, and prevents common initialization mistakes that manual setup lacks.
license: Apache-2.0
references:
  - references/knowledge.md
---

# Crossplane Configuration Package Authoring

Scaffold and modify Crossplane configuration packages. This skill handles structure, XRDs, dependencies, and building - NOT composition implementation.

## Binding rules — they hold even if you open nothing else

These are the core of `control-plane-project-charter`, which this skill does not load for you;
the charter has the reasons. Where the project's spec, work item or gate script decides
otherwise, the project wins: say so in your report.

1. **Never block on a question nobody can answer.** Decide from the project's spec and state
   the assumption, or stop and report the open question (charter §1).
2. **Never create a group, Space, control plane or cloud resource as a side effect** (§9).
3. **Test first: watch each new test fail for the reason you intended**, then make it pass. A
   broken test is not RED, even when it exits 1: a syntax error, a missing path, a run that
   stops at `✗ Parsing tests`, a bug in the test's own logic (§3).
4. **Backfilling a test for code that already works: mutate the implementation, never the
   test's expected value.** See that test go red, then revert (charter `tdd.md`).
5. **Managed resources carry `forProvider` only**, on the `.m.` API groups, unless the
   project's spec or API sets more: no `deletionPolicy`, `managementPolicies` or
   `metadata.namespace`; omit `providerConfigRef` if and only if
   `ClusterProviderConfig/default` exists and is the right one (§5).
6. **Name what ran and the command's own exit code.** After `| tail`, `$?` is `tail`'s: read
   `${PIPESTATUS[0]}`, or redirect to a file and then read `$?`. No command, no claim (§4).
7. **`No test files found` means nothing ran**, though `up test run` exits 0. A test program
   that prints `items: []` contributes zero tests (§8).
8. **For every test you added or changed, name the code change that turns it red**, and say
   whether you saw it fail. If you did not, call the test unproven (§4).
9. **Name the layer you reached** — render, composition test, local control plane, cloud — and
   never claim one you did not reach. Comments and docs claim no more than the test checks (§4).
10. **Re-read a document before you write from it.** Long runs lose old output: before you
    write a work item, a test expectation, a quote or a field value taken from a document,
    re-read the section you rely on in that step. Never quote from memory; if the re-read
    contradicts what you wrote, fix it first (charter §1).

## Phase 0: You run inline, and you are bound by the charter

This skill runs inline — you expand into the caller's conversation, share their
working directory, and can ask. `control-plane-project-charter` §1 (when nobody can answer,
never block) says what that means for asking questions, and §4 (report the effect, not the
intent) what it means for your summary. Both apply in full; only the binding rules above
repeat them.

**Load the charter before you start — this skill does not load it for you.** Load the
`control-plane-project-charter` skill, or read its `SKILL.md`, which sits beside this skill's
directory. It also carries the TDD loop (§3), what a v2 composed resource needs (§5), the
container boundary (§7), and what a green run does and does not prove (§8).

## Scope

**This skill DOES:**
- Create/modify project structure (apis/, examples/, scripts/)
- Write XRDs by hand, with the field list from the spec or the field wizard below
- Generate composition pipeline skeletons
- Manage dependencies (providers, functions)
- Run `up function generate` for function scaffolding
- Create example manifests
- Build and validate project

**This skill does NOT:**
- Write composition logic → Use `author-composition`
- Create tests → Use `author-tests`
- Run verification → Use `verify-configuration`

## Use the CLI generators for everything but the XRD

**Use the generators for compositions, functions, tests and examples; write the XRD
yourself.** A composition or a function layout written by hand is what produces
`mode: Resources`, `apiVersion: v1` and a pipeline the CLI did not wire. The XRD is the one
exception: an example carries values, never constraints, so an XRD inferred from one loses
every `required:`, `default:`, open-ended map and `status` field you meant to have
(`control-plane-project-charter` §5: write the XRD yourself).

| Command | Input → Output |
|---|---|
| `up project init <name>` | interactive wizard → a whole working project (see below) |
| `up example generate [<xrd>]` | wizard, or an XRD → `examples/<plural>/example.yaml` |
| `up xrd generate <example.yaml>` | an example **XR** → an inferred `apis/<plural>/definition.yaml` + language models. **Not for the XRD you ship**: at most a read-only second opinion (below) |
| `up composition generate <xrd\|xr>` | XRD or XR → `apis/<plural>/composition.yaml`, **and adds the required function packages as dependencies** |
| `up function generate <name> [<pipeline-path>]` | → `functions/<name>/…`, and wires it into that composition's pipeline |
| `up test generate <name> [--e2e]` | → `tests/test-<name>/…` (or `tests/e2etest-<name>/…`) |

`up xrd generate` also accepts `--input rgd` (ResourceGraphDefinition) and `--input SimpleSchema`,
and `--plural` for words it can't pluralize (`--plural postgreses`). Whatever the input, its
output is a draft you review and then own like any XRD you wrote, and it never runs over an
XRD that already exists (below).

**The fastest correct route for a brand-new API is example-first:** write the XR you want users
to write, then **write the XRD to match it** and generate the composition from it. Drafting the
example first is what keeps the schema honest; deriving the schema from it is what loses every
`required:`, `default:` and `status` field you meant to have — see
`control-plane-project-charter` §5
for the skeleton and the model-quality comparison.

```bash
# --scope is REQUIRED for a non-interactive run (see below)
up example generate --scope=namespace --name example --namespace default \
    --api-group platform.example.com --api-version v1alpha1 --kind StorageBucket
#   -> examples/storagebucket/example.yaml   (singular!) with spec: {}
# Fill in the spec so it is the API you want users to write, then:
# Now WRITE apis/storagebuckets/definition.yaml yourself (`control-plane-project-charter` §5 has the
# skeleton). Note the directory is plural even though examples/ is singular.
up composition generate apis/storagebuckets/definition.yaml
#   -> apis/storagebuckets/composition.yaml (mode: Pipeline + auto-ready step)
#      and adds function-auto-ready to upbound.yaml dependsOn
up dep add 'xpkg.upbound.io/upbound/provider-aws-s3:>=v2.0.0'   # always a constraint (below)
up function generate compose-bucket apis/storagebuckets/composition.yaml --language python
#   -> functions/compose-bucket/ + inserts its pipeline step into the composition
up project build
```

What this chain gets right, and what to watch:

- **You control the XRD** — `apiVersion: apiextensions.crossplane.io/v2`, `scope: Namespaced`, no `claimNames`, and the `required:`/`default:`/`additionalProperties`/`status` that an inferred schema cannot express. Do not copy a template's XRD as a starting point: the templates are v1.
- **The composition is `mode: Pipeline`** with an auto-ready step, and its function dependency is added to `upbound.yaml` for you.
- ⚠️ **Build before generating the function.** The models are generated from whatever XRD is on disk, and `up function generate` writes `crossplane-models @ file:./../../.up/python` into the new `pyproject.toml` only once `.up/python` exists. So `up project build` must come between writing the XRD and generating the function — which is what the Critical Build Order below already says.
- ⚠️ **`up example generate` prompts for scope even when every other flag is supplied.** Without a TTY it prints `ERROR: ... could not open a new TTY`, then writes the file with the namespaced default and exits 0 — a confusing mix of error and success. **Always pass `--scope=namespace`** (or `--scope=cluster`).
- ⚠️ **Write every open-ended map as `additionalProperties`**, never as fixed properties:

  ```yaml
  tags:
    type: object
    additionalProperties:
      type: string          # -> Optional[Dict[str, str]]
  ```

  Fixed `properties:` under a map generates one Pydantic field per key, so every key a user
  did not supply arrives as `None` and validation fails with
  `Input should be a valid string [input_value=None]`. This is the single most common way a
  hand-written XRD goes wrong, and it is also exactly what `up xrd generate` emits if you let
  it infer a map from an example — one more reason to write the file yourself.

- ⚠️ **Re-run `up project build` after every XRD change.** The models under `.up/` are
  generated *from* the XRD, so the moment you edit one they are stale. Measured: a
  `status.probeField` added by hand is absent from the generated model until a rebuild, and
  present immediately after. The build order below puts the first build *before* function
  generation, so an XRD edit made after that step leaves you writing function code against a
  model that predates it.

  Also note the generators disagree on pluralization: `examples/storagebucket/` (singular) vs `apis/storagebuckets/` (plural). Read the path each command prints instead of assuming.

### Starting from a template

`up project init <name>` runs a wizard: template (AWS Bucket / Azure Storage / GCP Storage /
Kubernetes WebApp / from scratch) → composition language → test language → AI tooling configs.
Non-interactively: `up project init <name> --template project-template-aws-s3 --language python
[--test-language python]`.

A template gives you a **complete, passing** project — XRD, composition, function, composition
test, E2E test, `examples/providerconfig.yaml` — which is usually a better starting point than
scaffolding from scratch. Two things to know:

- **The language templates emit the *embedded* Python layout** (`functions/<n>/main.py` +
  `requirements.txt`, `from .model.io...`), not the SDK layout that `up function generate`
  produces. Code you add must match what the project already has.
- **`--scratch` ignores `--language`** (it logs `... for kcl` regardless). Harmless — the scratch
  template contains no functions — but don't read it as the project's language.

Templates also leave behind `examples/example/example.yaml` (`kind: Example`, `spec: {}`) which is
backed by no XRD. Delete it; the real example is `examples/<plural>/example.yaml`.

## Decision Tree

```text
User Request → What mode?

NEW PROJECT:
  → Phase 0: Is there a template that fits? (`up project init` wizard) → if yes, start there
  → Phase 1: Gather project info (name, group, org, provider)
  → Phase 2: Define resource (Kind, version)
  → Phase 3: Draft the example XR, then write the XRD to match
            (`control-plane-project-charter` §5 has the v2 skeleton; do not infer the schema)
  → Phase 4: Select dependencies (providers)
  → Phase 5: `up composition generate` + select language
  → Phase 6: FIRST BUILD (generates models)
  → Phase 7: up function generate
  → Phase 8: Refine examples + create examples/providerconfig.yaml
  → Phase 9: FINAL BUILD
  → Hand off to language-specific skill

MODIFY EXISTING:
  → Add new resource: Start at Phase 2
  → Modify resource: Read existing, apply changes, rebuild
```

## Critical Build Order

```bash
# MUST follow this exact sequence
1. Create files + add dependencies
2. up dep update-cache
3. up project build           # FIRST - generates models
   # Hand-edited the XRD after this? Run it again - the models come FROM the XRD
4. up function generate ...   # Uses models from step 3
5. python3 "$SCRIPTS/setup_venv.py"   # Python: BEFORE you write the function body
6. up project build           # FINAL - builds with function
```

**Step 5 comes before you write a line of the function body, not after.** It needs step 4 to
have run — it installs the `pyproject.toml` that `up function generate` just created — and it
costs ~11s once, installing the generated models editable so every later `up project build`
needs no reinstall.

Do it there because **the user has the project open in an editor and is following along.**
Until the venv exists, every `from models.io...` and `from crossplane.function import ...` is
underlined on correct code, go-to-definition into the generated models goes nowhere, and
`forProvider` autocomplete is dead — so they cannot tell a real mistake from a missing
interpreter. The fast tier also cannot run without it.

It is not needed to *build*, since the function runs in a container, which is exactly why it
gets deferred and then never done. Do it at step 5. `$SCRIPTS` is
`<author-composition>/scripts`, the `author-composition` skill's scripts directory. A
`<skill-name>` in a path is that skill's directory — the directory containing its SKILL.md —
which sits beside this skill's directory. See
`languages/python.md` (`control-plane-project-charter` `languages/python.md`) for the details and the by-hand
equivalent.

**NEVER:**
- Run `up function generate` before first build
- Skip `up dep update-cache`
- Use provider v1.x (must be v2.x for models)
- Use XRD apiVersion v1 (must be v2)
- Use Cluster scope (must be Namespaced)
- Use `mode: Resources` in a composition — **removed in Crossplane v2, only `mode: Pipeline` is valid.** `up test run`'s local render tolerates it, but the API server rejects it on admission. Every `up` scaffold emits `Pipeline`; don't hand-edit it to `Resources`.

## Resolving Provider/Function Packages (marketplace discovery)

`up dep add` needs a package **reference** (e.g. `xpkg.upbound.io/upbound/provider-azure-network`). When the user names a **cloud + resource** but not the ref (e.g. "compose an Azure ResourceGroup + VirtualNetwork"), resolve it before adding — do **not** guess a package name blindly.

**Preferred — Upbound Marketplace MCP** (if one is configured for your agent). It uses your existing `up login` credentials:
1. `search_packages` — filter by type (provider/function), cloud/family, and tier to find the package + exact `xpkg` ref.
2. `get_package_version_resources` (or `..._groupkind_resources`) — get the **exact group/kind/version** you'll compose (e.g. `ResourceGroup` → `azure.m.upbound.io/v1beta1`), so the composition uses real Kinds from the start.
3. `up dep add '<ref>:>=vX.Y.Z'`, then `up dep update-cache`. **Always pass a constraint** (the
   form `up dep add --help` shows): a bare `<ref>` records `version: '>=v0.0.0'`, which accepts
   any major (observed with up v0.55.0). To cap the major, set `version: ^vX.Y.Z` in `upbound.yaml`.

**Fallback — web search and fetch** (no MCP): search for `site:marketplace.upbound.io <cloud> <service> provider` (functions: `... function`), or fetch a page like `https://marketplace.upbound.io/providers/upbound/provider-azure-network`, and read the ref + latest version off it. Marketplace *pages* list scope/description, not always exact Kinds — confirm Kinds from the generated models after the first build.

**Base resources live in the family package.** `ResourceGroup`, `ProviderConfig`, and other cross-service basics ship in **`provider-family-<cloud>`** (e.g. `provider-family-azure`), **not** a service provider. Service providers (`provider-<cloud>-<service>`) **transitively depend on the family**, so adding one (e.g. `provider-azure-network`) pulls the family in automatically — but add `provider-family-<cloud>` explicitly when you compose a base resource (like `ResourceGroup`) directly.

**Always:** prefer **v2+ Upbound Official families** (`provider-<cloud>-<service>`) over the monolithic `provider-<cloud>`; after the first build, verify the composed resources exist under `.up/python/models` (or the KCL/Go model tree) and correct Kinds/API versions. When more than one package/family could fit, ask the user, listing the candidates rather than guessing.

## Quick Reference

| Phase | Action | Key Command |
|-------|--------|-------------|
| 1-2 | Project/Resource info | Ask the user |
| 3 | Write the XRD | Field list from the spec or the field wizard, then `python3 <author-configuration-package>/scripts/check_xrd_schema.py apis/*/definition.yaml` |
| 4 | Dependencies | `up dep update-cache` |
| 5 | Composition + language | `up composition generate apis/{resource}/definition.yaml` |
| 6 | First build | `up project build` |
| 7 | Function generation | `up function generate {resource} apis/{resource}/composition.yaml --language <lang>` |
| 8 | Examples | Create simple + complete, **plus `examples/providerconfig.yaml`** |
| 9 | Final build | `up project build` |

### After the final build: deploying it somewhere

This skill stops at a built package. Before `up project run`, read
[knowledge.md](references/knowledge.md#after-the-final-build-deploying-it-somewhere): which
control plane you get depends on the current `up` context, and on a Space the default run
fails on a pull it cannot make. If the context is a Space, ask the user which run they want:
`--public` publishes their package.

### Never run `up xrd generate` over an XRD that already exists

An example carries values; it does not carry **constraints**. Regenerating over an XRD
silently destroys everything that is not inferable from a single manifest:

| Lost on regeneration | Why it cannot survive |
|---|---|
| `enum:` | an example shows one value, not the permitted set |
| `default:` | indistinguishable from "the value this example happens to use" |
| `minimum:` / `maximum:` / `pattern:` | no example implies a bound |
| `description:` | never present in an example |
| `required:` | inferred from what the example sets, not from intent |

This is why the XRD is authored, not generated: the table above is the *permanent* gap
between an example and a schema, not a one-off defect. Treat `apis/*/definition.yaml` as
hand-maintained source and edit it directly. `up xrd generate -o /tmp/xrd.yaml && diff` is
still fine as a read-only second opinion on a schema you already have.

### Phase 8 also owns the ProviderConfig — every project needs one and `--scratch` gives you none

A `--scratch` project has no `examples/providerconfig.yaml`. Only the *language templates*
ship one. So a scratch project builds, its tests pass, it installs on a control plane — and
every managed resource it composes sits unauthenticated, because Crossplane v2 defaults an
omitted `providerConfigRef` to `{kind: ClusterProviderConfig, name: default}` and **nothing
in the project creates that object**.

The failure mode is a managed resource with **no conditions and no events at all** — byte
for byte the same symptom as the `providerConfigRef` trap in the composition skills, so you
cannot tell the two causes apart from the cluster. Nothing in the workflow prompts for it,
and no check anywhere verifies that the ProviderConfig a composition implicitly depends on
exists.

Create it in Phase 8, matching the provider family you added in Phase 4. The default is a
`ClusterProviderConfig` named `default`, below. When the project's spec or API names another
config — a namespaced `ProviderConfig` in the XR's namespace, a non-`default` name — create
that one instead, so this example and the compositions' `providerConfigRef` name the same
object (`control-plane-project-charter` §5: defaults the project may override).

```yaml
# examples/providerconfig.yaml
apiVersion: aws.m.upbound.io/v1beta1     # family group, NOT kms.aws.m.upbound.io
kind: ClusterProviderConfig
metadata:
  name: default                          # must be "default" to match the v2 default ref
spec:
  credentials:
    source: Secret                       # or IRSA / WebIdentity / PodIdentity / Upbound
    secretRef:
      namespace: crossplane-system
      name: aws-creds
      key: creds
```

Two things worth confirming rather than guessing:

- **The apiVersion is the family group** (`aws.m.upbound.io/v1beta1`), not a service group.
  This is a different group shape from every other resource in the family, which is exactly
  the kind of thing that gets guessed wrong. Confirm it from the generated tree, where the
  module path *is* the reversed group:
  `python3 <author-composition>/scripts/probe_project.py --project <root> ClusterProviderConfig`
  → `models.io.upbound.m.aws.clusterproviderconfig` = `aws.m.upbound.io`. (A `grep` for
  `Literal` in that module shows the credential `source` values, not the apiVersion.)
- **`ClusterProviderConfig` (cluster-scoped) vs `ProviderConfig` (namespaced)** — use the
  cluster-scoped one named `default` unless the project's spec or API calls for per-namespace
  credentials, and remember the generated E2E test creates a `ClusterProviderConfig` too.

Also add the credential secret to the README's prerequisites, since it is not part of the
package:

```bash
kubectl -n crossplane-system create secret generic aws-creds \
  --from-file=creds="${AWS_SHARED_CREDENTIALS_FILE:-$HOME/.aws/credentials}"
kubectl apply -f examples/providerconfig.yaml
```

### XRD Defaults (ALWAYS use these)

| Field | Value |
|-------|-------|
| apiVersion | `apiextensions.crossplane.io/v2` |
| scope | `Namespaced` |

**Kind naming (new vs migration).** For a **new** config, name the XRD Kind exactly as the user's XR (e.g. `Network`) — **no `X` prefix and no `claimNames`** (those are the v1 claim model). An XRD from a template or an older project may use the legacy claim-based `X<Kind>` + `claimNames: <Kind>` (`up project init` templates are v1); for a new namespaced XR, switch it to the intended Kind and drop `claimNames`. **When migrating an existing v1 config, keeping the `X`-prefixed Kind is fine** — don't force-rename existing XRs.

### Provider Options by Cloud

| Cloud | Common Providers |
|-------|------------------|
| AWS | provider-aws-ec2, provider-aws-rds, provider-aws-s3, provider-aws-iam, provider-aws-eks |
| Azure | provider-azure-compute, provider-azure-network, provider-azure-storage |
| GCP | provider-gcp-compute, provider-gcp-network, provider-gcp-storage |

> **Base/cross-service resources** (`ResourceGroup`, `ProviderConfig`, …) ship in **`provider-family-<cloud>`** (e.g. `provider-family-azure`), **not** the service providers above — service providers depend on the family transitively. See "Resolving Provider/Function Packages" above.

> **Pitfall — external pipeline functions must be declared dependencies.** Your project's own **embedded** functions (built from `functions/`) are wired automatically. But an **external** function `functionRef` (e.g. `crossplane-contrib-function-auto-ready`, `function-patch-and-transform`) that isn't in `upbound.yaml` `dependsOn` and cached (`up dep update-cache`) makes `up test run`'s render fail with `unknown function … is it listed in the render input?`. **Fix by declaring the dependency — do not delete the pipeline step.** (`up test run` *does* render declared external functions — verified.)

## Field wizard (Phase 3): you write the XRD, the wizard collects its fields

With no spec to read the fields from, ask in a loop until user says done:

1. Field name (e.g., region, cidr)
2. Field type (string, integer, boolean, array, object)
3. Description
4. Required? (yes/no)
5. Default value (optional)
6. Add another field? (yes/no)

Write the OpenAPIv3 schema into `apis/<plural>/definition.yaml` as you go, by hand.

**Add reasonable validation — but keep the draft valid.** Sensible enhancements are encouraged (accurate types, `required`, descriptions, a CIDR `pattern`, well-scoped `enum`s/defaults). The one rule: any constraint must still **accept the values in the user's XR draft** — never add validation that rejects the user's own example (e.g. a lowercase `location` enum that accepts only `westeurope` and rejects the draft's `West Europe`). If a reasonable constraint would conflict with a draft value, normalize the value or relax the constraint — or ask.

**The six questions are not the schema.** They collect a field list; they cannot tell you that a
field is `vpcId` while the Kind is `VPC`, that a repeated group prefix may or may not be stutter,
that an unbounded array leaves no CEL budget, or that redefining `READY` prints the column twice.
XRD versions must round-trip, so all of that is permanent from the first version that ships.
[`charter/xrd-design.md` (`control-plane-project-charter` `charter/xrd-design.md`) has the rules; run the mechanical
ones before the first build:

```bash
python3 <author-configuration-package>/scripts/check_xrd_schema.py \
  apis/*/definition.yaml
```

`<author-configuration-package>` is this skill's directory: the directory containing this
SKILL.md.

Exit `0` is clean, `10` is at least one finding, and `2` means it extracted nothing — a corpus
error, not a pass. `FAIL` lines are defects; `REVIEW` lines (booleans, bare strings) are calls
for you to make. The `ACRONYMS` table applies to the **Kind** only; trim it to the acronyms this API uses.

An enum whose values mirror an upstream API verbatim (`aurora-postgresql`) fails the casing
rule by design. When that is a deliberate decision, record it in `xrd-schema-exceptions.yaml`
at the project root, one entry per field with a mandatory `reason` (format in the script's
docstring); the script reads it from the working directory, prints those findings as
`EXCEPTED`, and can then serve as a gate. A skeleton XRD has too few fields to count as an
extraction, so pass `--min-corpus` until the API has grown.

## Post-Scaffolding Hand-off

After the final build, report what ran and what it printed, not a checklist
(`control-plane-project-charter` §4: report the effect, not the intent):

```markdown
## Package scaffolding: {project-name}

**Resource:** {Kind} ({api-group}/{version}) · **Language:** {language}

**Ran:**
- `up project build` → exit {code}; package {path under _output/}
- `check_xrd_schema.py apis/*/definition.yaml` → exit {code}; {findings, or none}

**Layer reached:** package build. Nothing rendered, no tests run, nothing deployed.
**Assumed / not verified:** {e.g. Kinds confirmed from the generated models; ProviderConfig not applied}

### Next steps
1. Composition logic: `author-composition` (`functions/{resource}/`)
2. Tests: `author-tests`
3. Gate: the project's own gate if it has one, else `verify-configuration`
```

## Templates & Detailed Instructions

See [knowledge.md](references/knowledge.md) for:
- Complete XRD template (v2, Namespaced)
- upbound.yaml template
- .gitignore template
- Composition skeleton template
- Detailed phase instructions
- Common pitfalls and solutions

## Success Criteria

Checks for you before you report, not a report format (charter §4: report what ran). The
skill succeeds when:
- Project structure created
- XRD written by hand, with the schema the user or spec defined
- First build generates models (`.up/<language>/` model tree exists)
- `up function generate` creates function structure
- Final build succeeds (`.uppkg` created)
- No unbounded dependency: every `dependsOn` `version` names the major you built against, never `'>=v0.0.0'`
- Examples created
- User guided to language-specific skill
