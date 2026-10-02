---
name: execute-v2-migration
description: Execute a Crossplane v1 to v2 migration plan in an Upbound control-plane project, phase by phase and with minimal interruption. Use when asked to "execute the migration", "implement the v2 migration", "run the migration plan", "continue the migration", or "migrate to v2 now". Reads .agents/plans/CROSSPLANE_V2_MIGRATION.md, creates a migrate-to-v2 branch, updates dependencies, XRDs, compositions and examples directly, migrates functions and tests through the suite's authoring skills, and stops at verification checkpoints that fail. Not for writing the plan, which is `plan-v2-migration`.
license: Apache-2.0
references:
  - references/knowledge.md
---

# Crossplane v2 Migration Executor

Execute Crossplane v1 to v2 migration plans autonomously, using the suite's specialised
skills for the complex steps and direct edits for the straightforward ones.

**Load the `control-plane-project-charter` skill first and read its SKILL.md.** Nothing in it
is repeated here; when this file and the charter disagree, the charter wins.

See [knowledge.md](references/knowledge.md) for detailed phase instructions, delegation
briefs, and worked examples.

---

## Phase 0: Know how you are running, and you are bound by the charter

This skill runs either in the user's conversation or as a delegated agent started by
another agent. `control-plane-project-charter` §1 says what each may do; decide which you
are before anything else.

- **As a delegated agent you cannot ask.** A question ends your turn and hands back a
  result for work that never happened. Act on the plan and the brief you were given,
  discover the rest from the project, and state every assumption you would otherwise have
  asked about. Treat the brief as the confirmation to execute, and skip E2E tests unless the
  brief explicitly asked for them.
- **In the user's conversation** you may ask — but only at the
  [interaction points](#user-interaction-points) below, and for irreversible decisions.

Either way, your summary is the evidence. `control-plane-project-charter` §4 — report the
effect, not the intent — is binding on every summary you write, and it is not repeated here.

**Read the whole charter before you start.** It also carries the TDD loop (§3), what a v2
composed resource needs (§5), the container boundary (§7), what a green run does and does not
prove (§8), and the rule against creating infrastructure as a side effect (§9).

## Purpose

Executes Crossplane v2 migration plans by:
1. Reading migration plan from `.agents/plans/CROSSPLANE_V2_MIGRATION.md`
2. Executing phases systematically with minimal user interruption
3. Using specialized skills for complex tasks (functions, tests, verification)
4. Applying straightforward changes directly (XRDs, compositions, examples)
5. Validating at critical checkpoints

---

## Arguments

| Argument | Description |
|----------|-------------|
| (none) or `all` | Execute all phases sequentially |
| `1 2 3` | Execute specific phases (space-separated) |
| `continue` | Resume from last checkpoint |

---

## Language Detection (Phase 0)

**Detect function language before Phase 3:**

```bash
# Check for Python functions
find functions -name "*.py" | grep -v __pycache__ | head -5

# Check for KCL functions
find functions -name "*.k" | head -5
```

| Result | Language | Phase 3 Skill | Phase 6 Skill |
|--------|----------|---------------|---------------|
| `.py` files found | Python | `author-composition` | `author-tests` |
| `.k` files found | KCL | `author-composition` | `author-tests` |
| Both found | Mixed | Use per-function language | `author-tests` |

**Carry the detected language forward into Phase 3.**

---

## Workflow Overview

| Phase | Description | Method |
|-------|-------------|--------|
| 0 | Pre-flight + language detection | Direct (read, shell) |
| 1 | Dependencies + git branch | Direct edits + shell |
| 2 | XRD migration | Direct edits |
| 3 | Function code migration | Load `author-composition` and follow it |
| 4 | Composition updates | Direct edits |
| 5 | Example updates | Direct edits |
| 6 | Test updates | Load `author-tests` and follow it |
| 7 | File reorganization | Direct (`git mv`) |
| 8 | Verification | Load `verify-configuration`, then `e2e-test-configuration` |
| 9 | Documentation | User-guided edits |

**Run the authoring skills in your own context.** When you load `author-composition` or
`author-tests`, follow it here rather than handing it off: you keep everything it
discovers, and it keeps everything you have already established — the project root, the
language, the provider family. Do not re-derive what is already known. The two
verification skills produce long, disposable output; if your agent can delegate work, hand
each to a delegated agent with its brief from knowledge.md and wait for its result before
continuing. Otherwise run them inline.

**Migrating the tests can lead, and usually should.** A migration is backfill — the code
already works — so there is no natural RED unless you create one. Updating a test to its v2
expectations *before* migrating the function it covers gives you exactly that: the test goes
red against the un-migrated function for the right reason, and green when the migration is
correct. Where the ordering above makes that impractical, prove the migrated test still
bites with a deliberate mutation instead. Either way the loop is the one in
`control-plane-project-charter` §3; a test updated against already-passing code and never
observed failing is where the false coverage claims come from.

---

## Phase Checkpoints

**CRITICAL:** Validate at each checkpoint before proceeding.

| Checkpoint | After Phase | Validation (KCL) | Validation (Python) | On Failure |
|------------|-------------|-----------------|---------------------|------------|
| Dependencies | 1 | `up project build` succeeds | `up project build` succeeds | Exit with error |
| XRDs | 2 | `yq '.' apis/*/definition.yaml` | `yq '.' apis/*/definition.yaml` | Report file, exit |
| Functions | 3 | `kcl functions/*/main.k` | `python -c "import ast; ast.parse(open('functions/*/main.py').read())"` | Offer retry once |
| Tests | 6 | `kcl tests/*/main.k` | `python -m pytest tests/` (syntax check) | Offer retry once |
| Full build | 8.1 | `up project build` succeeds | `up project build` succeeds | Exit with error |
| Composition tests | 8.2 | All tests pass | All tests pass | Exit (user must fix) |
| E2E tests | 8.4 | Tests pass or skipped | Tests pass or skipped | Report results |

---

## Execution Flow

### Phase 0: Pre-Flight

1. Verify `.agents/plans/CROSSPLANE_V2_MIGRATION.md` exists
2. Parse plan: extract project name, counts, dependency updates
3. Verify v1 project (apiVersion check)
4. Check git status (warn on uncommitted changes)
5. **Confirmation**: in the user's conversation, show scope and ask "Execute migration?
   (yes/no)". As a delegated agent, the brief is the confirmation — proceed.

### Phases 1-7: Execute Changes

For each phase, follow instructions in [knowledge.md](references/knowledge.md).

**Direct edits (Phases 1, 2, 4, 5, 7):**
- Apply the exact replacements from the migration plan
- Validate after each file with `yq`

**Skill-driven work (Phases 3, 6):**
- Load the skill and follow it with the brief from knowledge.md, including its success
  criteria
- Validate syntax when it finishes
- On failure: report the error, offer one retry. As a delegated agent there is no one to
  offer it to: retry once yourself, and say so in the report

### Phase 8: Verification

1. **Build + composition tests**: `verify-configuration`
2. **Composition rendering**: Spot-check one example
3. **E2E tests**: only with consent — ask once in the user's conversation; as a delegated
   agent, only if the brief asked for them. Then `e2e-test-configuration`

### Phase 9: Documentation

Provide checklist of README updates. Offer to help if requested.

---

## Final Summary Template

```markdown
## Migration Complete

**Project:** {project-name}
**Branch:** migrate-to-v2

**Updated:**
- XRDs: {count} → v2 + Namespaced
- Functions: {count} → namespaced APIs (.m.)
- Tests: {count} → v2 compatible
- Examples: {count} → namespaced + kind updates
- Compositions: {count} → kind updates

**Verification:**
- Build: {status}
- Composition Tests: {passed}/{total}
- E2E Tests: {passed}/{total} | Skipped

**Assumptions made:** {list, or "none"}

**Next Steps:**
1. Review: `git diff main..migrate-to-v2`
2. Commit: `git add . && git commit -m "Migrate to Crossplane v2"`
3. PR: `gh pr create --title "Migrate to Crossplane v2"`
```

---

## User Interaction Points

**Minimize interruptions.** In the user's conversation, only ask for:

| Point | Question | Options |
|-------|----------|---------|
| Phase 0 | Execute migration? | yes / no |
| Phase 0 | Uncommitted changes detected | commit first / continue |
| Phase 8.4 | Run E2E tests? | yes / no / skip |
| Phase 9 | Help with README? | yes / no |

Do NOT ask for confirmation on individual files or phases. As a delegated agent, ask none of
these: take the default the brief implies, and list it under "Assumptions made".

---

## Critical Requirements

1. **Migration plan MUST exist** in `.agents/plans/CROSSPLANE_V2_MIGRATION.md`
2. **Create git branch** `migrate-to-v2` before any changes
3. **Execute in order**: Dependencies → XRDs → Functions → Compositions → Examples → Tests → Verification
4. **Use specialized skills** for: composition functions in any language (`author-composition`), tests (`author-tests`), verification (`verify-configuration`, `e2e-test-configuration`)
5. **Edit files directly** for: XRDs, compositions, examples (straightforward YAML)
6. **Validate at checkpoints**: Do not proceed past failed checkpoint
7. **Autonomous execution**: Make decisions without asking unless critical
8. **Never rename a function to add a language suffix** (`-python`/`-kcl`): the function name is the published registry path

---

## Success Criteria

- [ ] Migration plan read and parsed
- [ ] Git branch created
- [ ] Dependencies updated to v2 versions
- [ ] XRDs migrated (v2 + Namespaced + X-prefix removed)
- [ ] Functions migrated via `author-composition`
- [ ] Compositions updated (kind references)
- [ ] Examples updated (namespace + kind + compositionSelector)
- [ ] Tests migrated via `author-tests`
- [ ] Build succeeds with v2 models
- [ ] Composition tests pass
- [ ] E2E tests pass or skipped
- [ ] Final summary provided

---

## Error Recovery

| Error Type | Strategy |
|------------|----------|
| Build failure | Report error, check dependencies, exit |
| XRD edit failure | Report file + location, exit |
| Function migration failure | Report error, offer one retry, then exit |
| Test update failure | Report error, offer one retry, then exit |
| Composition test failure | Report failures, exit (user must fix) |
| E2E test failure | Use the `e2e-test-configuration` debugging, report results |

**Critical error**: Create recovery checkpoint, report completed phases, exit cleanly.

---

## References

- [Detailed phase instructions](references/knowledge.md)
- [Delegation briefs](references/knowledge.md#delegation-briefs)
- [Worked examples](references/knowledge.md#worked-examples)
- [Crossplane v2 Upgrade Guide](https://docs.crossplane.io/latest/guides/upgrade-to-crossplane-v2/)
