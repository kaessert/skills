---
name: author-configuration-package
description: Use this skill when user requests to create, scaffold, modify, or extend a Crossplane configuration package. Handles project initialization, XRD creation/modification, composition setup, dependency management (including MRAPs and `up dep add --api`), function generation, building, and setting up the local development environment. Use immediately when user mentions creating/scaffolding/modifying/extending a configuration package, adding new resources to an existing package, installing or adding a provider ("add provider-aws-s3", "install the AWS provider", `up dep add`), or setting up the Python environment ("configure a venv", "my imports do not resolve", "set the VS Code interpreter"). Use this skill instead of manually creating project structures, XRDs, or running `up project init`/`up function generate` commands directly. This skill ensures correct build order, proper scaffolding, and prevents common initialization mistakes that manual setup lacks.
license: Apache-2.0
references:
  - references/templates.md
  - references/providerconfig.md
  - references/mrap.md
  - references/project-templates.md
---

# Crossplane Configuration Package Authoring

Scaffold and modify Crossplane configuration packages — structure, XRDs, dependencies, the
generated composition and function skeletons, examples and the build — in the order the CLI
needs. Composition logic and tests are other skills' work.

## Binding rules — they hold even if you open nothing else

These are the core of `control-plane-project-charter`, which this skill does not load for you;
the charter has the reasons. Where the project's spec, work item or gate script decides
otherwise, the project wins: say so in your report.

1. **Never block on a question nobody can answer.** Decide from the project's spec and state
   the assumption, or stop and report the open question (charter §1).
2. **Never create a group, Space, control plane or cloud resource as a side effect** (§9).
3. **Test first: watch each new composition or unit test fail for the reason you intended**,
   then make it pass; for a new E2ETest this is optional. A broken test is not RED, even when it
   exits 1: a syntax error, a missing path, a run that stops at `✗ Parsing tests`, a bug in the
   test's own logic (§3).
4. **Backfilling a test for code that already works: mutate the implementation, never the
   test's expected value.** See that test go red, then revert (the charter's `charter/tdd.md`).
5. **In a v2 project, managed resources carry `forProvider` only**, on the `.m.` API groups,
   unless the project's spec or API sets more: no `deletionPolicy`, `managementPolicies` or
   `metadata.namespace`; omit `providerConfigRef` if and only if
   `ClusterProviderConfig/default` exists and is the right one. A v1 project keeps its v1
   APIs: migrating it is separate work (§5).
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

## Mode, and the charter

**Interactive:** ask only what the project can't tell you. **Unattended:** never ask; decide from
the spec and state the assumption, or stop and report. Load `control-plane-project-charter`
before you start, or read its `SKILL.md` beside this skill's directory: this skill does not
load it.

Run the phases in order. The two builds bracket function generation: models come from the
XRD and the dependencies (Phase 6), and the function is generated against them (Phase 7).

## Phase 1: Start or open the project

`test -f upbound.yaml` tells you which. In an existing project, list its APIs
(`apis/*/definition.yaml`): add a resource from Phase 2, or change one by reading it, editing
it and rebuilding.

**Use the CLI generators for everything but the XRD.** A composition or function layout
written by hand is what produces `mode: Resources`, `apiVersion: v1` and a pipeline the CLI
did not wire; the XRD is the one file you write (Phase 3).

| Command | Input → Output |
|---|---|
| `up project init <name>` | interactive wizard → a whole working project (below) |
| `up example generate [<xrd>]` | wizard, or an XRD → `examples/<kind-lowercase>/<xr-name>.yaml`; the name defaults to the lowercase Kind (`examples/network/network.yaml`, up v0.55.0). Find the file; don't assume `example.yaml` |
| `up xrd generate <example.yaml>` | an example XR → an inferred `apis/<plural>/definition.yaml` + language models. Not for the XRD you ship (Phase 3) |
| `up composition generate <xrd\|xr>` | XRD or XR → `apis/<plural>/composition.yaml`, and adds the required function packages as dependencies |
| `up function generate <name> [<pipeline-path>]` | → `functions/<name>/…`, and wires it into that composition's pipeline. On an existing `functions/<name>` it prompts to overwrite and, without a TTY, cancels: wire the step by hand (the charter's `charter/generators.md`) |
| `up test generate <name> [--e2e]` | → `tests/test-<name>/…` (or `tests/e2etest-<name>/…`) |

The generators disagree on pluralization — `examples/storagebucket/` vs
`apis/storagebuckets/` — so read the path each command prints.

**`up project init`.** Non-interactively: `up project init <name> --scratch` (or
`--template <t> --language <lang> [--test-language <lang>]`). Starting from a language
template instead of `--scratch`: read [project-templates.md](references/project-templates.md)
first; its Python layout differs from what `up function generate` produces.

- `--scratch` ignores `--language` (it logs `... for kcl` regardless). Harmless — the scratch
  template has no functions — but don't read it as the project's language.
- `up project init --directory .` fails with `directory is not empty` even when the directory
  holds only `.git`. Init into a temporary directory and move the files across, dotfiles
  included (up v0.55.0).
- The scratch template leaves its own values behind: `upbound.yaml` `source`
  (`github.com/upbound/project-template-scratch`), a placeholder `maintainer`,
  `repository: xpkg.upbound.io/example/<name>`, and `module
  github.com/upbound/project-template-scratch/tests/<dir>` in generated Go tests' `go.mod`.
  **Set `repository`, `source` and `maintainer` before any generator runs** — `spec.repository`
  names the embedded function in every `functionRef` (the charter's `charter/generators.md`) —
  and fix any test `go.mod` that still names the template.
- Templates leave `examples/example/example.yaml` (`kind: Example`, `spec: {}`), backed by no
  XRD. Delete it; the real example is the file `up example generate` writes.

## Phase 2: Gather the project and resource information

From the spec: project name, API group, cloud, organisation, maintainer; then the resource
Kind, its plural and its version (`v1alpha1` for a new API, the charter's
`charter/xrd-design.md`); and the function language for Phase 7 (`kcl`, `python`, `go`,
`go-templating`) — from the spec or an existing function, else ask: it is a decision, not a
discoverable fact. New tests follow it (charter §10).
Interactive and not in the spec: ask, with the tables in
[templates.md](references/templates.md#questions-for-a-new-project).

## Phase 3: Write the XRD, and check its design

**Write the XRD yourself** (charter §5 has the reason, `charter/v2-resources.md` the v2 skeleton). For a **new** XRD:

| Field | Value |
|---|---|
| `apiVersion` | `apiextensions.crossplane.io/v2` |
| `scope` | `Namespaced` |
| version | `v1alpha1` |
| `names.kind` | exactly the user's XR Kind (`Network`): no `X` prefix, no `claimNames` |

An existing v1 project stays v1 until it is migrated deliberately (`plan-v2-migration`), and a
migration keeps its existing Kind, `X` prefix included: renaming a Kind is a new API, and
existing objects are not converted (the charter's `charter/xrd-design.md`). Don't copy a
template's XRD as a v2 starting point: the templates are v1.

**The fastest correct route for a new API is example-first:** write the XR you want users to
write, then write the XRD to match it, then generate the composition from it.

```bash
# --scope is required for a non-interactive run (below)
up example generate --scope=namespace --name example --namespace default \
    --api-group platform.example.com --api-version v1alpha1 --kind StorageBucket
#   -> examples/storagebucket/example.yaml (spec: {}); fill in the spec users should write
# Write apis/storagebuckets/definition.yaml yourself (plural directory).
up composition generate apis/storagebuckets/definition.yaml                 # Phase 5
up dep add 'xpkg.upbound.io/upbound/provider-aws-s3:>=v2.0.0, <v3.0.0'      # Phase 4
up project build                                                            # Phase 6
up function generate compose-bucket apis/storagebuckets/composition.yaml --language python
up project build                                                            # Phase 9
```

- **`up example generate` prompts for scope even when every other flag is supplied.** Without
  a TTY it prints `ERROR: ... could not open a new TTY`, then writes the file with the
  namespaced default and exits 0. Always pass `--scope=namespace` (or `--scope=cluster`).
- **Write every open-ended map as `additionalProperties`**, never as fixed properties:

  ```yaml
  tags:
    type: object
    additionalProperties:
      type: string
  ```

  Fixed `properties:` under a map generates one model field per key, so every key a user did
  not supply arrives as a null the typed model rejects (Python: `Input should be a valid
  string [input_value=None]`). It is the most common way a hand-written XRD goes wrong, and
  exactly what `up xrd generate` emits for a map inferred from an example.
- **Never run `up xrd generate` over an XRD that already exists.** An example carries values,
  not constraints, so regenerating silently drops `enum:`, `default:`,
  `minimum:`/`maximum:`/`pattern:`, `description:` and the intended `required:`. Treat
  `apis/*/definition.yaml` as hand-maintained source. `up xrd generate -o /tmp/xrd.yaml && diff`
  is fine as a read-only second opinion; it also accepts `--input rgd`, `--input SimpleSchema`
  and `--plural` (`--plural postgreses`), and its output is a draft you review and then own.
- With no spec to read the fields from (interactive only), collect them with the field wizard
  in [templates.md](references/templates.md#xrd-field-wizard), and keep every constraint you
  add compatible with the user's draft XR.

**A field list is not the schema.** It cannot tell you that a field is `vpcId` while the Kind
is `VPC`, that a repeated group prefix may or may not be stutter, that an unbounded array
leaves no CEL budget, or that redefining `READY` prints the column twice. XRD versions must
round-trip, so all of that is permanent from the first version that ships.
`control-plane-project-charter`'s `charter/xrd-design.md` has the rules; run the mechanical
ones before the first build, with the script in this skill's directory
(`<author-configuration-package>`, the directory containing this SKILL.md). Run it from there:
don't copy it into the project, and don't write a test for the XRD (charter §3).

```bash
python3 <author-configuration-package>/scripts/check_xrd_schema.py \
  apis/*/definition.yaml
```

Exit `0` is clean, `10` is at least one finding, and `2` means it extracted nothing — a corpus
error, not a pass. `FAIL` lines are defects; `REVIEW` lines (booleans, bare strings) are calls
for you to make. The `ACRONYMS` table applies to the **Kind** only; trim it to the acronyms this
API uses.

An enum whose values mirror an upstream API verbatim (`aurora-postgresql`) fails the casing
rule by design, and a **frozen API** (already shipped, or fixed by the project's spec) reports
FAILs you may not fix. Record each deliberate one in `xrd-schema-exceptions.yaml` at the
project root, under its rule class, with a mandatory `reason`:

```yaml
enumCasing:
  - field: spec.engine   # the path the FAIL prints, minus file and [version]
    reason: AWS RDS engine names, passed through verbatim
maxItems:
  - field: status.subnetIds
    reason: frozen API, shipped without a bound
```

Classes keyed by field path: `enumCasing`, `description`, `listType`, `maxItems`,
`lowerCamel`, `fieldCasing`; by name: `kindAcronym` (the Kind), `printerColumn` (`READY`),
`collision` (the spellings as printed). `uniqueItems` has none: the API server rejects the CRD.
The script reads the file from the working directory, prints those findings as `EXCEPTED`,
reports an entry that matches nothing for REVIEW, and can then serve as a gate. To read a
frozen API's state without gating, pass `--report-only` (exit 0 despite findings). A skeleton
XRD has too few fields to count as an extraction, so pass `--min-corpus` until the API has grown.

## Phase 4: Add dependencies

`up dep add` needs a package **reference** (`xpkg.upbound.io/upbound/provider-azure-network`).
When the user names a cloud and a resource but not the ref, resolve it; do not guess a
package name.

- **Upbound Marketplace MCP**, if one is configured (it uses your `up login` credentials):
  `search_packages` (filter by type, cloud/family and tier) for the package and its `xpkg`
  ref, then `get_package_version_resources` (or `..._groupkind_resources`) for the exact
  group/kind/version you will compose (`ResourceGroup` → `azure.m.upbound.io/v1beta1`).
- **Otherwise web search and fetch:** `site:marketplace.upbound.io <cloud> <service> provider`
  (functions: `... function`), or a page such as
  `https://marketplace.upbound.io/providers/upbound/provider-azure-network`, for the ref and
  latest version. Pages list scope and description, not always exact Kinds — confirm Kinds
  from the generated models after the first build.
- **Always pass a constraint that caps the major:** `up dep add '<ref>:>=v2.0.0, <v3.0.0'`
  (accepted by up v0.55.0). A bare `<ref>` records `version: '>=v0.0.0'`, and `'>=v2.0.0'`
  alone still accepts any later major. Then `up dep update-cache`; do not skip it.
- **Prefer v2+ Upbound Official family providers** (`provider-<cloud>-<service>`) over the
  monolithic `provider-<cloud>`. A new project needs v2.x: the `.m.` groups ship from v2.0.0.
- **Base resources live in the family package.** `ResourceGroup`, `ProviderConfig` and other
  cross-service basics ship in `provider-family-<cloud>`. Service providers depend on it
  transitively, but add it explicitly when you compose a base resource directly.
- When more than one package could fit, ask the user, listing the candidates.
- **External pipeline functions must be declared dependencies.** Embedded functions (built
  from `functions/`) are wired automatically. An external `functionRef`
  (`crossplane-contrib-function-auto-ready`, `function-patch-and-transform`) missing from
  `dependsOn` or the cache makes `up test run`'s render fail with `unknown function … is it
  listed in the render input?`. Fix it by declaring the dependency, not by deleting a step the
  project needs: declared external functions do render. The one step to delete is the
  duplicate auto-ready step of Phase 5.

Writing a ManagedResourceActivationPolicy, or running `up dep add --api crossplane:<tag>`:
read [mrap.md](references/mrap.md) first. The manifest must sit under `apis/` or it is
silently left out of the package, and `up project build` barely validates it.

## Phase 5: Generate the composition

`up composition generate apis/<plural>/definition.yaml` writes a `mode: Pipeline` composition
with an auto-ready step, and adds `crossplane-contrib/function-auto-ready` at `'>=v0.0.0'` to
`dependsOn` — even when the project already declares another auto-ready function, which then
gets a step too (up v0.55.0). When the project declares its own function set, delete the
duplicate step and its dependency, and say so; otherwise give the dependency a constraint.

`mode: Resources` was removed in Crossplane v2: only `Pipeline` is valid. `up test run`'s
local render tolerates `Resources`, but the API server rejects it on admission. Every `up`
scaffold emits `Pipeline`; don't hand-edit it.

## Phase 6: First build

`up project build` generates the models from the XRD and the dependencies on disk; check the
model tree under `.up/<language>/` exists and holds the Kinds and API versions you will
compose. **Re-run it after every XRD change** — the models come from the XRD, so an edit
leaves them stale (a `status` field added by hand is absent from the model until a rebuild).
No `.m.` models: the provider is v1.x, or the cache was not updated.

## Phase 7: Generate the function

Only after the first build: `up function generate <name> apis/<plural>/composition.yaml
--language <lang>`. It wires the models into the function only once they exist under
`.up/<language>/`. Check its step comes before the auto-ready step in the pipeline.

Python, before you write the function body: run
`python3 <author-composition>/scripts/setup_venv.py`, where `<author-composition>` is the
directory containing that skill's SKILL.md, beside this skill's directory (why it comes first:
the charter's `languages/python.md`).

## Phase 8: Examples and the ProviderConfig

Write the example XRs under `examples/<kind-lowercase>/<xr-name>.yaml` — a minimal one with
the required fields only, and a complete one
([templates.md](references/templates.md#example-xrs)).

**Every project needs a ProviderConfig, and `--scratch` gives you none.** Create
`examples/providerconfig.yaml`, matching the provider family from Phase 4: by default a
`ClusterProviderConfig` named `default`, unless the project's spec or API names another
config (charter §5). Without it, every managed resource sits unauthenticated while the build
and the tests pass. Read [providerconfig.md](references/providerconfig.md) before you write
it: the manifest, its family-group apiVersion, and the credential secret the README must
list.

## Phase 9: Final build, and report

`up project build` again; it produces the package under `_output/` (`.uppkg`). Then report
what ran and what it printed, not a checklist (`control-plane-project-charter` §4): the
commands and exit codes, the layer reached (package build), and what you assumed. The
template is in [templates.md](references/templates.md#hand-off-report).

This skill stops at a built package. Deploying it (`up project run`) is `verify-configuration`'s
job; where a run lands and why a Space context needs the user's choice — `--public`
publishes their package — is `control-plane-project-charter` `charter/targets.md`.

## Boundaries

- Composition logic → `author-composition`; tests → `author-tests`, which writes each failing
  test before `author-composition` implements it (charter §3); verification and deploying →
  the project's own gate, else `verify-configuration`.

## Success criteria

Checks for you before you report, not a report format (charter §4: report what ran). The
skill succeeds when:

- Project structure created, with `upbound.yaml` metadata set before any generator ran
- XRD written by hand, with the schema the user or spec defined, and `check_xrd_schema.py` run
- First build generated the models (`.up/<language>/` model tree exists)
- `up function generate` created the function, its step before auto-ready
- Final build succeeded (`.uppkg` under `_output/`)
- No unbounded dependency: every `dependsOn` `version` caps the major you built against
  (`'>=v2.0.0, <v3.0.0'`), never `'>=v0.0.0'`
- Example XRs and `examples/providerconfig.yaml` created
- The hand-off names the next skill

## References

- [templates.md](references/templates.md) — read when writing `upbound.yaml`, an XRD,
  `.gitignore` or example XRs, when asking a user for project or field information, when
  choosing a provider package, when a build fails, and for the hand-off report.
- [providerconfig.md](references/providerconfig.md) — read before writing
  `examples/providerconfig.yaml` (Phase 8).
- [mrap.md](references/mrap.md) — read before writing a ManagedResourceActivationPolicy or
  running `up dep add --api` (Phase 4).
- [project-templates.md](references/project-templates.md) — read before starting from a
  language template rather than `--scratch` (Phase 1).
