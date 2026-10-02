---
name: author-tests
description: Use this skill when user requests to implement a feature, write, create, author, modify, refactor or plan refactoring of Crossplane configuration tests (composition tests or E2E tests) in a control-plane project - in any language (KCL, Python, YAML, Go, go-templating). Use this rather than a generic planning mode when the user asks for a plan to refactor composition tests or e2e tests in a crossplane configuration package. Specialized skill focused only on test authoring and modification (not running tests). Detects the test language and applies the right templates and patterns. Use this skill instead of writing test files directly.
license: Apache-2.0
references:
  - references/knowledge.md
---

# Crossplane Test Authoring Assistant

Author and modify Crossplane configuration tests, in any language `up test generate` supports.

## Core Principle

**A test's *meaning* is language-agnostic; only its *syntax* differs.**

Every composition and E2E test - whether written in KCL, Python, YAML, Go, or go-templating - compiles to the same two Kubernetes objects: `CompositionTest` and `E2ETest` (`meta.dev.upbound.io/v1alpha1`). The fields, the concepts, the critical rules, and the common mistakes are identical across languages. The only thing that changes is how you express those objects: KCL models, Python Pydantic builders, raw YAML manifests, or Go.

So this skill has two layers:
- **Language-agnostic core** (this file + [knowledge.md](references/knowledge.md)): the object model, rules, patterns, and mistakes. Read these regardless of language.
- **Per-language reference** (kcl.md (`control-plane-project-charter` `languages/kcl.md`), python.md (`control-plane-project-charter` `languages/python.md`), yaml.md (`control-plane-project-charter` `languages/yaml.md`)): syntax, scaffolding, templates, and language-specific mistakes.

## Scope

**This skill DOES:**
- ✅ Create/modify composition tests and E2E tests in any supported language
- ✅ Plan test refactoring (creates `.agents/tasks/REFACTOR_TESTS.md`)
- ✅ Execute refactoring (one priority item at a time)
- ✅ Generate scaffolds with `up test generate`
- ✅ **Run the test you just wrote** — `up test run "tests/<t>"`, directly, as the RED/GREEN loop requires

**This skill does NOT:**
- ❌ Build and deploy the package, or run the whole suite as a gate (use `verify-configuration` — but *after* the loop below, never inside it)
- ❌ Execute E2E tests (use `e2e-test-configuration`)
- ❌ Implement composition features (use `author-composition`)

## The TDD loop — this skill owns the RED step

The canonical loop lives in
`control-plane-project-charter` §3: write the
test, run it, read the failure, then implement. It is not repeated here — read it, including
the table of which failures count as RED and the deliberate-mutation technique for backfill.

**What is specific to this skill** is that you are the one writing the assertion that has to
fail. Three things make that assertion bite:

| | |
|---|---|
| **Assert the field, not the existence.** | `assertResources` is partial and positive. An entry naming only `kind` passes against any resource of that kind, whatever it contains. Name the field you are adding. |
| **Assert on the composite too.** | Every `status` field the function writes needs an assertion on the XR itself. It is the only programmatic check on composition outputs. |
| **Cover the minimal XR.** | Use the inline `xr` field with every optional property omitted. That is the shape a real user writes first, and the one the scaffold never generates. |

Run it directly — `up test run "tests/<t>"` — not through `verify-configuration`, which builds
and deploys and is not an inner loop.

## Step 1: Detect the Test Language (do this first)

**The test language is NOT necessarily the composition language.** A Python composition project can (and often does) use raw YAML tests - `configuration-aws-ctp` is exactly this: Python functions, YAML tests. Detect the *test* language from the `tests/` directory, then fall back to project language, then ask.

```
Inspect tests/ (skip empty projects):
  tests/*/**.k                         → KCL      → ../../languages/kcl.md
  tests/*/test/__main__.py, main.py    → Python   → ../../languages/python.md
  tests/*/*.yaml, no other test source → YAML     → ../../languages/yaml.md
  tests/*/*.go, *.gotmpl               → Go       → ../../languages/go.md

No tests yet? Pick the language:
  1. Match existing test style if any test exists anywhere
  2. Else default to the project's composition language (functions/*.py → python, functions/**/*.k → kcl)
  3. Else default to YAML (simplest, no toolchain coupling)
  4. When ambiguous, ask the user
```

Scaffold in the chosen language:

| Language | Composition test | E2E test |
|----------|------------------|----------|
| KCL (default) | `up test generate <name> --language kcl` | `up test generate <name> --e2e --language kcl` |
| Python | `up test generate <name> --language python` | `up test generate <name> --e2e --language python` |
| YAML | `up test generate <name> --language yaml` | `up test generate <name> --e2e --language yaml` |
| Go | `up test generate <name> --language go` | `up test generate <name> --e2e --language go` |

> **Python tests: set up the venv before you write one.** `up test generate --language python`
> creates a `pyproject.toml` in the new test directory; installing it is what makes
> `from models.io...` resolve for the person reading along in an editor, and it is a
> prerequisite for the fast tier. One command, ~11s, after `up project build`:
>
> ```bash
> python3 <author-composition>/scripts/setup_venv.py --project <root>
> ```
>
> It installs every function *and* test directory from the project's own pins, so run it again
> after generating a new test directory. Details in
> `languages/python.md` (`control-plane-project-charter` `languages/python.md`).

> **New projects:** `up project init` takes `--test-language` **separately** from `--language` (functions), confirming the two are independent axes (e.g. Go functions + Python tests). If you initialize a project, set the test language deliberately.

> **Go / go-templating:** supported by `up test generate` and use the identical object model and rules below, but this skill ships no Go templates yet. Scaffold with the CLI, then apply the agnostic rules from [knowledge.md](references/knowledge.md). Prefer YAML tests unless the project already commits to Go.

## Decision Tree

```
User Request → What action?

CREATE NEW TEST:
  → Detect/choose language (Step 1)
  → Which type?
    → Composition (fast, no cloud): up test generate <feature> --language <lang>
    → E2E (real resources):        up test generate <feature> --e2e --language <lang>
  → Fill in logic using the matching per-language reference

MODIFY EXISTING TEST:
  → Read test first, match its language and style, then apply changes

PLAN REFACTORING:
  → Create .agents/tasks/REFACTOR_TESTS.md with prioritized items
  → DO NOT execute, just plan

EXECUTE REFACTORING:
  → Check for plan file first
  → Execute ONE item at a time
  → Run tests after each item
```

## Quick Reference

| Type | Timeout | Validate | Dir prefix | Purpose |
|------|---------|----------|------------|---------|
| Composition | ≥60s | `false` (scaffold/lab default) | `test-` | Local render validation, no cloud |
| E2E | sized to resources (see below) | n/a | `e2etest-` | Real cloud lifecycle |

**E2E timeout is sized to what you provision, not a fixed number.** A couple of Azure resources may be fine at ~900s; a real EKS cluster + add-ons needs 3600-5400s. Under-sizing causes false failures. Set `cleanupTimeoutSeconds` proportionally.

### Provider Credentials (E2E)

| Provider | ProviderConfig API Group | Web-identity field |
|----------|--------------------------|--------------------|
| AWS | `aws.m.upbound.io/v1beta1` | `webIdentity.roleARN` |
| Azure | `azure.m.upbound.io/v1beta1` | `webIdentity.clientID` |
| GCP | `gcp.m.upbound.io/v1beta1` | `federation.providerID` + `serviceAccount` |

**CRITICAL**: always use the `.m.` API groups in tests. The `.m.` marks the **modern** (Crossplane v2) API group — not "naMespaced" and not "monolithic". It holds the namespaced managed resources *and* the cluster-scoped `ClusterProviderConfig` they default to, which is why "m = namespaced" cannot be right. See `control-plane-project-charter` §5.

**A composed managed resource should carry no `providerConfigRef` at all** — the API server
defaults it to `{kind: ClusterProviderConfig, name: default}`, which is the object the templates
and generated E2E tests create. See
`control-plane-project-charter` §5
for the live-control-plane evidence that overriding it leaves the resource inert.

So in a test's `extraResources`, create a **`ClusterProviderConfig`** (cluster-scoped, no
namespace) unless the project genuinely uses per-namespace credentials — in which case it
creates a namespaced `ProviderConfig`, which does need `namespace: default`, and the function
must reference it explicitly. The training labs use `ClusterProviderConfig`; see
[knowledge.md](references/knowledge.md#two-providerconfig-kinds-v2).

## Critical Rules (all languages)

### MUST DO:
1. **Always scaffold with `up test generate`** - never create test directories manually
2. **Define the XR inline** where the format supports it (composition tests) - keeps tests self-contained
3. **Assert ALL critical fields** - not just resource existence
4. **Match exact composed-resource names** - find them with `up composition render`
5. **`namespace: default` on the XR** (v2). On the provider config only if the project actually uses the namespaced `ProviderConfig` kind — the default and the usual case is `ClusterProviderConfig`, which is cluster-scoped and takes no namespace
6. **Run the test directly while authoring** (`up test run "tests/<t>"`); hand the built-and-deployed gate to `verify-configuration` once the suite is green

### NEVER DO:
1. Hardcoded long-lived credentials in E2E tests (use web/injected identity, or a Secret sourced from an env var)
2. `skipDelete: true` in E2E tests (always clean up)
3. `timeoutSeconds < 60` for composition tests
4. Under-sized E2E timeouts (see sizing note above)
5. Assert resource existence only, with no field assertions

### Crossplane version in E2E tests

Set the `crossplane` block one of two valid ways:
- **Track a channel** (recommended, and what real configs use): `autoUpgrade.channel: Stable` (or `Rapid`), no pinned version.
- **Pin a version** when you need determinism: `version: <current UXP version>` + `autoUpgrade.channel`.

Do NOT hard-code a stale pinned version copied from an example - if you pin, use a current one. A channel-only block is a fine and common default.

### Namespaced APIs (`.m.`) - expressed differently per language

Everything in tests uses the **namespaced** API surface (`aws.m.upbound.io`, `kubernetes.m.crossplane.io`, `helm.m.crossplane.io`, ...). How you write that depends on the language:
- **KCL / Python**: via the imported model path (the `m` in the import). See kcl.md (`control-plane-project-charter` `languages/kcl.md`) / python.md (`control-plane-project-charter` `languages/python.md`).
- **YAML**: directly in the `apiVersion` string (e.g. `s3.aws.m.upbound.io/v1beta1`). No imports. See yaml.md (`control-plane-project-charter` `languages/yaml.md`).

## Test Organization

**CONSOLIDATE (same directory) when:**
- Same resource type, different configs
- Feature enabled/disabled variants
- 3-5 related scenarios

**SEPARATE directory when:**
- Different resource types
- E2E tests (always separate, `e2etest-` prefix)
- Complex sequential dependencies

## Phase 0: You run inline, and you are bound by the charter

This skill runs inline — you expand into the caller's conversation, share their
working directory, and can ask. `control-plane-project-charter` §1 says what
that means for asking questions, and §4 (`control-plane-project-charter`) what it
means for your summary. Both apply in full, and are not repeated here.

**Read the whole charter before you start.** It also carries the TDD loop (§3), what a v2
composed resource needs (§5), the container boundary (§7), and what a green run does and does
not prove (§8).

## Workflow Summary

### New Test
1. Detect/choose test language (Step 1)
2. Determine feature/resources/variants from `args` and the project (`apis/*/definition.yaml`,
   `apis/*/composition.yaml`, the function source, `examples/*/example.yaml`) — do not ask;
   see Phase 0
3. Generate scaffold: `up test generate <feature> --language <lang>` (add `--e2e` for E2E)
4. Write test using the template from the matching per-language reference
5. **Hand off to `verify-configuration`** once the suite is green — it builds and deploys,
   which is the gate, not the inner loop

### Modify Test
1. Read existing test; match its language and style
2. Understand current assertions
3. Apply changes
4. **Hand off to `verify-configuration`** once the suite is green — it builds and deploys,
   which is the gate, not the inner loop

### Refactoring Plan
1. Analyze `tests/` directory structure
2. Identify duplication and consolidation opportunities
3. Create `.agents/tasks/REFACTOR_TESTS.md` with prioritized items ([template](references/knowledge.md#refactoring-plan-template))
4. DO NOT execute - inform user how to proceed

### Refactoring Execution
1. Check for `.agents/tasks/REFACTOR_TESTS.md`
2. If missing: ask user to create plan first
3. Execute ONLY the highest priority unchecked item
4. **Hand off to `verify-configuration`** once the suite is green — it builds and deploys,
   which is the gate, not the inner loop
5. Mark item complete with date
6. Report completion and next item

## References

- [knowledge.md](references/knowledge.md) - language-agnostic object model, patterns, common mistakes, refactoring template
- kcl.md (`control-plane-project-charter` `languages/kcl.md`) - KCL syntax, imports, templates (composition + E2E for AWS/Azure/GCP)
- python.md (`control-plane-project-charter` `languages/python.md`) - Python SDK test layout, Pydantic dump modes, templates
- yaml.md (`control-plane-project-charter` `languages/yaml.md`) - raw YAML tests, real-world examples

## Success Criteria

Test authoring is complete when:
- ✅ Test language detected/chosen and scaffold generated (or existing test read)
- ✅ Test content follows the agnostic rules + the matching per-language reference
- ✅ All critical fields asserted (not just existence)
- ✅ The new assertion was observed to FAIL before the implementation existed, and to pass after
- ✅ `verify-configuration` run once the suite is green, and it passes
