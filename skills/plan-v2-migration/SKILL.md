---
name: plan-v2-migration
description: Use this skill when user requests to migrate, upgrade, or plan migration to Crossplane v2. Analyzes existing v1 configuration packages and generates comprehensive migration checklists covering XRD updates, function code changes, test updates, and file reorganization. Use immediately when user mentions "migrate to v2", "upgrade to crossplane v2", "plan v2 migration", or "crossplane 2 migration". Use this skill instead of manually analyzing migration requirements. This skill ensures comprehensive coverage of all breaking changes and prevents common migration mistakes that manual analysis lacks.
license: Apache-2.0
references:
  - references/knowledge.md
---

# Crossplane v2 Migration Planner

Analyze Crossplane v1 configuration packages and generate comprehensive migration checklists.

**Scope**: ANALYSIS ONLY - generates checklist, does NOT execute changes.

**Output**: `.agents/plans/CROSSPLANE_V2_MIGRATION.md`

---

## Mode, and the charter

**Interactive:** ask only what the project can't tell you. **Unattended:** never ask; decide from
the spec and state the assumption, or stop and report. Load `control-plane-project-charter`
before you start, or read its `SKILL.md` beside this skill's directory: this skill does not
load it.

## Terminology Disambiguation

**CRITICAL: These terms are distinct - do not confuse them:**

| Term | What It Means |
|------|---------------|
| **Crossplane v2** | The overall new version with namespaced resources |
| **XRD apiVersion v2** | `apiextensions.crossplane.io/v2` in definition.yaml |
| **upbound.yaml v2alpha1** | `meta.dev.upbound.io/v2alpha1` project config |
| **Provider namespaced** | Providers using `.m.` in API groups (awsm, azurem, gcpm) |
| **X-prefix removal** | v1: `XNetwork` → v2: `Network` |

**Provider import changes:**
- `aws` → `awsm` (API: `*.aws.m.upbound.io`)
- `azure` → `azurem` (API: `*.azure.m.upbound.io`)
- `gcp` → `gcpm` (API: `*.gcp.m.upbound.io`)

---

## Quick Reference: Key v1 → v2 Changes

| Component | v1 Pattern | v2 Pattern |
|-----------|-----------|-----------|
| XRD apiVersion | `apiextensions.crossplane.io/v1` | `apiextensions.crossplane.io/v2` |
| XRD scope | (implicit cluster) | `spec.scope: Namespaced` |
| Resource kind | `XNetwork` | `Network` |
| claimNames | Required section | Remove entirely |
| deletionPolicy | `Delete \| Orphan` | `managementPolicies: ["*"]` |
| providerConfigRef | `name: default` | omitted if and only if `ClusterProviderConfig/default` exists and is the right one; otherwise `{kind, name}` naming an object that exists |
| Secret namespace | Explicit | Removed (inferred) |
| compositionSelector | `spec.compositionSelector` | `spec.crossplane.compositionSelector` |
| Connection secrets | Built-in XR support | Manual Secret composition |

See [knowledge.md](references/knowledge.md) for detailed before/after examples.

---

## Workflow

### Phase 0: Detect and Validate v1

**Goal**: Confirm this is a v1 configuration package.

**Steps**:
1. Check `upbound.yaml` for `apiVersion: meta.dev.upbound.io/v1alpha1`
2. Check XRDs for `apiextensions.crossplane.io/v1`
3. Check for cluster-scoped provider imports (no `.m.` in paths)

**If NOT v1**: Report to user and exit gracefully.

The commands: [knowledge.md](references/knowledge.md#detect-v1-configuration).

### Phase 0.5: Discover Project Structure

**Goal**: Map all components that need migration: the project name, XRDs, functions, tests,
and the X-prefixed directories that need renaming. The commands:
[knowledge.md](references/knowledge.md#discover-project-structure).

### Phase 1: Verify Dependencies (Use a Sub-agent)

**Goal**: Verify all provider and configuration dependencies support v2.

**IMPORTANT**: Use a sub-agent to avoid loading large marketplace responses into main context.

Hand the sub-agent the prompt in
[knowledge.md](references/knowledge.md#subagent-prompt-template), which also shows the report
format to expect. If your harness has no sub-agents, follow the prompt yourself
(`control-plane-project-charter` §1).

Store sub-agent report for Phase 1.2 of the checklist.

### Phase 2: Analyze Components

**For each XRD**:
- Check apiVersion, claimNames, connectionSecretKeys
- Check for X-prefix in kind
- Check for deletionPolicy parameter

**For each function**:
- Check provider imports (aws vs awsm, etc.)
- Check deletionPolicy usage
- Check providerConfigRef patterns
- Check connection secret usage

**For each test**:
- Check provider imports
- Check XR kind references
- Check namespace in metadata

**For each example**:
- Check kind (X-prefix)
- Check compositionSelector location
- Check writeConnectionSecretToRef

### Phase 3: Generate Migration Checklist

**Output file**: `.agents/plans/CROSSPLANE_V2_MIGRATION.md`

Use the template from [knowledge.md](references/knowledge.md) → "Migration Checklist Template" section.

**Key sections**:
1. **Phase 1**: Pre-migration (backup, dependency updates)
2. **Phase 2**: XRD migration (apiVersion, scope, remove claimNames)
3. **Phase 3**: Function code migration (imports, providerConfigRef, managementPolicies)
4. **Phase 4**: Composition updates (compositeTypeRef kind)
5. **Phase 5**: Example updates (kind, namespace, compositionSelector)
6. **Phase 6**: Test updates (imports, XR kind, assertions)
7. **Phase 7**: File reorganization (remove X-prefix from directories)
8. **Phase 8**: Verification (build, tests)
9. **Phase 9**: Documentation

**Important**: Include specific file paths and before/after code snippets for each task.

### Phase 4: Display Summary

After writing the checklist, display:

```markdown
## v2 Migration Plan: [project]

**Output File**: `.agents/plans/CROSSPLANE_V2_MIGRATION.md`

**Migration Scope:**
- XRDs to update: [count]
- Functions to update: [count]
- Tests to update: [count]
- Examples to update: [count]
- Dependencies verified: [count] providers, [count] configurations

**Major Breaking Changes Detected:**
[List 3-5 most critical for this project]

**Complexity**: [Low | Medium | High]

**Execution Strategy:**
- Phase 1-2: Manual edits (upbound.yaml, XRDs)
- Phase 3: Use `author-composition` skill for functions
- Phase 6: Use `author-tests` skill for tests
- Phase 8: Use `verify-configuration` + `e2e-test-configuration` skills

**Next Steps:**
1. Review the plan in `.agents/plans/CROSSPLANE_V2_MIGRATION.md`
2. Create branch: `git checkout -b migrate-to-v2`
3. Execute phases using recommended skills
```

---

## Skill Boundaries

### This Skill Does
- Analyze v1 configuration structure
- Detect all breaking changes
- Generate phase-based checklist
- Verify dependencies via sub-agent
- Write checklist to `.agents/plans/CROSSPLANE_V2_MIGRATION.md`
- Read-only analysis (safe)

### This Skill Does NOT Do
- Modify any code files
- Execute the migration
- Run builds or tests
- Create git commits

### Handoff to Other Skills
| Task | Skill to Use |
|------|--------------|
| Execute migration | `execute-v2-migration` |
| Write function code | `author-composition` |
| Write tests | `author-tests` |
| Run verification | `verify-configuration` |
| Run E2E tests | `e2e-test-configuration` |

---

## Success Criteria

Checks for you before you report, not a report format (`control-plane-project-charter` §4:
report the effect, not the intent). The skill completes successfully when:

1. Confirmed v1 configuration (or exited gracefully if not)
2. Discovered all XRDs, functions, tests, examples
3. Verified dependencies via sub-agent
4. Analyzed all components for breaking changes
5. Generated checklist at `.agents/plans/CROSSPLANE_V2_MIGRATION.md`
6. Displayed summary with metrics and next steps

---

## References

- [knowledge.md](references/knowledge.md) — read for the detection and analysis commands, the
  dependency-check prompt, the before/after examples of each breaking change, and the
  checklist template (Phase 3), before you write the plan.
- [Crossplane v2 Upgrade Guide](https://docs.crossplane.io/latest/guides/upgrade-to-crossplane-v2/)
- [What's New in Crossplane v2](https://docs.crossplane.io/latest/whats-new/)
