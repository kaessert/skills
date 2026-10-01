# Crossplane v2 Migration Executor - Knowledge Base

Detailed instructions, briefs, and examples for executing Crossplane v1 to v2 migrations.

Edits below are written as `replace A with B in <file>`. Apply each as an exact string
replacement: read the file first, match its whitespace exactly, and skip an edit whose
v2 form is already present.

---

## Table of Contents

- [Phase Details](#phase-details)
- [Delegation Briefs](#delegation-briefs)
- [Worked Examples](#worked-examples)
- [Error Handling](#error-handling)
- [Troubleshooting](#troubleshooting)

---

## Phase Details

### Phase 0: Pre-Flight Validation

**Check migration plan exists:**
```bash
test -f .agents/plans/CROSSPLANE_V2_MIGRATION.md
```
If missing → Exit with error: "Run the `plan-v2-migration` skill first"

**Read and parse plan:** read `.agents/plans/CROSSPLANE_V2_MIGRATION.md` in full.

Extract: project name, XRD count, function count, test count, dependency updates

**Verify v1 project:**
```bash
grep -q "apiVersion: meta.dev.upbound.io/v1alpha1" upbound.yaml
find apis -name "definition.yaml" -exec grep -l "apiextensions.crossplane.io/v1" {} \;
```

**Check git status:**
```bash
git status --porcelain
```
If uncommitted changes: in the user's conversation, ask once to commit or continue. As a
delegated agent, continue, and put the uncommitted paths at the top of your summary.

**Confirm execution (single question, user's conversation only):**
Show: Project name, scope (XRD/function/test counts), phases to execute
Ask: "Execute migration? (yes/no)"

As a delegated agent you cannot ask: the brief that started you is the confirmation.

---

### Phase 1: Pre-Migration Preparation

**1.1: Create git branch**
```bash
git checkout -b migrate-to-v2
```

**1.2: Update dependencies**

Read dependency updates from migration plan Phase 1.2.

For each provider and configuration dependency update, in `upbound.yaml`:
replace `version: {old}` with `version: {new}`.

If connection secrets detected in plan, in `upbound.yaml` replace

```yaml
spec:
  dependsOn:
```

with

```yaml
spec:
  apiDependencies:
  - k8s:
      version: v1.33.0
    type: k8s
  dependsOn:
```

**Update cache and build:**
```bash
up dep update-cache
up project build
ls -la .up/kcl/models/ | grep -E "awsm|azurem|gcpm"  # Verify v2 models
```

If build fails → Report error and exit.

---

### Phase 2: XRD Migration

For each XRD section in migration plan (Phase 2.X), read
`apis/{resource}/definition.yaml`, then apply in sequence:

| # | Change | Replace | With |
|---|---|---|---|
| 1 | API version v1 → v2 | `apiVersion: apiextensions.crossplane.io/v1` | `apiVersion: apiextensions.crossplane.io/v2` |
| 2 | Add scope (if missing) | `spec:` + `  group:` | `spec:` + `  scope: Namespaced` + `  group:` |
| 3 | Kind (remove X-prefix) | `kind: X{Kind}` | `kind: {Kind}` |
| 4 | metadata.name (remove x-prefix) | `name: x{plural}` | `name: {plural}` |
| 5 | spec.names.kind | `kind: X{Kind}` | `kind: {Kind}` |
| 6 | spec.names.plural (if x-prefixed) | `plural: x{plural}` | `plural: {plural}` |

**Handle special cases:**

- claimNames detected in plan → remove the whole `claimNames:` block (a multi-line replacement with the empty string).
- deletionPolicy parameter detected → replace it with `managementPolicies`: `type: string` becomes `type: array` with string items, and the enum values change (Example 1 shows the exact block).
- connectionSecretKeys detected → remove the `connectionSecretKeys:` block.

**Validate:**
```bash
yq '.' apis/{resource}/definition.yaml > /dev/null
```

---

### Phase 3: Function Code Migration

**CRITICAL:** Migrate each function with the `author-composition` skill.

For each function section in migration plan (Phase 3.X):

1. Extract migration requirements from plan for this function
2. Load the `author-composition` skill and follow it with the
   [function migration brief](#function-migration-brief). If your agent can delegate work,
   you may instead hand the function to a delegated agent with that brief; otherwise do it
   inline.
3. If it fails → Report error, retry once with an adjusted approach
4. Validate syntax:
```bash
kcl functions/{function-name}/main.k >/dev/null 2>&1
```

Repeat for all functions.

---

### Phase 4: Composition Updates

For each composition section in migration plan (Phase 4.X):

**Update compositeTypeRef kind:** in `apis/{resource}/composition.yaml` replace
`kind: X{Kind}` with `kind: {Kind}`.

**Validate:**
```bash
yq '.' apis/{resource}/composition.yaml > /dev/null
```

---

### Phase 5: Example Updates

For each example section in migration plan (Phase 5.X), in `examples/{file}.yaml`:

**Update kind:** replace `kind: X{Kind}` with `kind: {Kind}`.

**Add namespace (if missing):**
```bash
grep -q "namespace:" examples/{file}.yaml || echo "needs namespace"
```
If it needs one, replace `metadata:` + `  name: {name}` with `metadata:` + `  name: {name}` +
`  namespace: default`.

**Move compositionSelector (if at wrong level):**
```bash
# Check if compositionSelector exists at spec level
grep -A1 "^spec:" examples/{file}.yaml | grep -q "compositionSelector:" && echo "move it"
```
If so, move the block under `spec.crossplane.compositionSelector`.

**Remove writeConnectionSecretToRef (if present):** search the file for it and remove the
block.

**Validate:**
```bash
yq '.' examples/{file}.yaml > /dev/null
```

---

### Phase 6: Test Updates

**CRITICAL:** Migrate each test with the `author-tests` skill.

For each test section in migration plan (Phase 6.X):

1. Determine test type: composition (test-*) or E2E (e2etest-*)
2. Extract migration requirements from plan for this test
3. Load the `author-tests` skill and follow it with the
   [test migration brief](#test-migration-brief) — or, if your agent can delegate work, hand
   the test to a delegated agent with that brief; otherwise do it inline.
4. If it fails → Report error, retry once with an adjusted approach
5. Validate syntax:
```bash
kcl tests/{test-name}/main.k >/dev/null 2>&1
```

Repeat for all tests.

---

### Phase 7: File Reorganization

**Check if reorganization needed** (read Phase 7 from plan).

If needed:
```bash
# For each resource
mkdir -p apis/{resource-name}
git mv apis/{old-definition-path} apis/{resource-name}/definition.yaml
git mv apis/{old-composition-path} apis/{resource-name}/composition.yaml
```

If not needed → Skip phase.

---

### Phase 8: Verification

**8.1-8.2: Build and composition tests**

Load the `verify-configuration` skill and follow it with the
[verification brief](#verification-brief). Its output is long and disposable, so if your
agent can delegate work, hand it to a delegated agent and keep only the result; otherwise
run it inline.

If composition tests fail → Report failures, exit (user must fix).

**8.3: Composition rendering (optional validation)**

For one example:
```bash
up composition render apis/{resource}/composition.yaml examples/{example}.yaml --xrd apis/{resource}/definition.yaml | head -100
```

Verify output contains:
- Namespaced APIs (.m. in apiVersion)
- Managed resource `spec` contains **only** `forProvider` — no `providerConfigRef`,
  no `managementPolicies`, no `metadata.namespace`. Crossplane v2 supplies all three.

**8.4: E2E tests (with single user confirmation)**

E2E tests take 30-60 minutes and create real cloud resources, so never start them
without consent. In the user's conversation, ask once: "Run E2E tests? (30-60 min, uses
cloud resources) [yes/no/skip]". As a delegated agent, run them only if the brief that
started you explicitly asked for E2E; otherwise skip.

If yes: load the `e2e-test-configuration` skill and follow it with the
[E2E test brief](#e2e-test-brief), delegating it if your agent can.

If no/skip → Note in summary that E2E tests were skipped.

---

### Phase 9: Documentation

**Provide user with checklist:**
```markdown
## Documentation Updates Needed

Migration is functionally complete. Please update:

**README.md:**
- [ ] API version references (v1 → v2)
- [ ] Add namespace requirements to examples
- [ ] Document connection secret changes (if applicable)
- [ ] Update example commands

**CI/CD (if applicable):**
- [ ] Update Crossplane version in workflows
- [ ] Update test commands if paths changed

Ask: "Would you like help updating README.md? [yes/no]"
```

If yes → Update README.md based on user guidance.
If no, or running as a delegated agent → Include the checklist in the final summary.

---

## Delegation Briefs

Each brief is what to work from when you follow the named skill — inline, or handed to a
delegated agent if yours can delegate. A delegated agent does not see this conversation,
so give it the brief in full, with the plan's requirements filled in.

### Function Migration Brief

```text
Skill: author-composition

Migrate Crossplane function to v2: functions/{function-name}/main.k

Keep the exact function name — do NOT add a language suffix (`-python`/`-kcl`). The directory name is the published registry path and must stay in the publish allow-list.

**Required changes:**
{extract from plan:
- Import updates (aws→awsm, azure→azurem, gcp→gcpm)
- XR type updates (remove X-prefix)
- REMOVE providerConfigRef where it names the v2 default — that is
  `{kind: ClusterProviderConfig, name: default}`, or a v1 `providerConfigRef` naming
  `default`, both of which the API server now supplies. **Keep** one that names a
  non-`default` config: a platform with more than one credential set it deliberately, and
  deleting it silently repoints those resources at the default account. Never add a `kind`
  field to a reference you are keeping without checking the object exists — see below
- REMOVE managementPolicies and any deletionPolicy on managed resources
- REMOVE metadata.namespace from managed resources
- Remove namespace from secret refs
- Connection secret manual composition (if applicable)
}

**SUCCESS CRITERIA:**
1. `kcl functions/{function-name}/main.k` runs without syntax errors
2. All v1→v2 changes from the list above are applied
3. No v1 patterns remain (no X-prefix kinds, no deletionPolicy, no cluster-scoped imports)

**Return format:**
- Status: SUCCESS | FAILURE
- Files modified: [list]
- Key changes made: [bullet list]
- Warnings/concerns: [if any]
```

### Test Migration Brief

```text
Skill: author-tests

Update Crossplane test for v2: tests/{test-name}/main.k

**Required changes:**
{extract from plan:
- Import updates (aws→awsm, azure→azurem, gcp→gcpm)
- XR kind updates (remove X-prefix)
- Add namespace to XR metadata
- Update assertions:
  - Do NOT assert providerConfigRef or managementPolicies — they are defaulted
    by the API server and are absent from the rendered composition output
  - Remove namespace from secret refs
  - Add Secret resource (if connection secrets)
- E2E only: ProviderConfig namespaced API + namespace, Crossplane version pin
}

**SUCCESS CRITERIA:**
1. `kcl tests/{test-name}/main.k` runs without syntax errors
2. All v1→v2 changes from the list above are applied
3. XR assertions match expected v2 output format

**Return format:**
- Status: SUCCESS | FAILURE
- Files modified: [list]
- Key changes made: [bullet list]
- Warnings/concerns: [if any]
```

### Verification Brief

```text
Skill: verify-configuration

Build the project and run the composition tests only. Do not run E2E tests and do not
deploy to a control plane.

**SUCCESS CRITERIA:**
1. `up project build` completes without errors
2. All composition tests pass

**Return format:**
- Build status: SUCCESS | FAILURE
- Composition tests: X/Y passed
- Failure details: [if any failures, include test name and error]
```

### E2E Test Brief

```text
Skill: e2e-test-configuration

Run all E2E tests to completion with monitoring.

**SUCCESS CRITERIA:**
1. All E2E tests complete (pass or fail with clear reason)
2. Any failures include resource state and logs

**Return format:**
- Status: X/Y tests passed
- Failed tests: [list with brief reason]
- Resource issues: [if applicable]
```

---
## Worked Examples

### Example 1: XRD Migration

<example>
**Input** (apis/network/definition.yaml - v1):
```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: xnetworks.aws.example.org
spec:
  group: aws.example.org
  names:
    kind: XNetwork
    plural: xnetworks
  claimNames:
    kind: Network
    plural: networks
  connectionSecretKeys:
    - vpcId
    - subnetIds
  versions:
    - name: v1alpha1
      served: true
      referenceable: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                parameters:
                  type: object
                  properties:
                    region:
                      type: string
                    deletionPolicy:
                      type: string
                      enum: [Delete, Orphan]
                      default: Delete
```

**Output** (apis/network/definition.yaml - v2):
```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata:
  name: networks.aws.example.org
spec:
  scope: Namespaced
  group: aws.example.org
  names:
    kind: Network
    plural: networks
  # claimNames section REMOVED
  # connectionSecretKeys section REMOVED
  versions:
    - name: v1alpha1
      served: true
      referenceable: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                parameters:
                  type: object
                  properties:
                    region:
                      type: string
                    managementPolicies:
                      type: array
                      items:
                        type: string
                        enum: ["*", "Create", "Update", "Delete", "LateInitialize", "Observe"]
                      default: ["*"]
```

**Replacements applied, in order** (`old` → `new`):
```text
# 1. API version
"apiVersion: apiextensions.crossplane.io/v1"
  → "apiVersion: apiextensions.crossplane.io/v2"

# 2. Add scope
"spec:\n  group:"
  → "spec:\n  scope: Namespaced\n  group:"

# 3. Update metadata.name
"name: xnetworks.aws.example.org"
  → "name: networks.aws.example.org"

# 4. Update kind
"kind: XNetwork"
  → "kind: Network"

# 5. Update plural
"plural: xnetworks"
  → "plural: networks"

# 6. Remove claimNames (multi-line edit)
"  claimNames:\n    kind: Network\n    plural: networks\n"
  → ""

# 7. Remove connectionSecretKeys
"  connectionSecretKeys:\n    - vpcId\n    - subnetIds\n"
  → ""

# 8. Replace deletionPolicy with managementPolicies
"                    deletionPolicy:\n                      type: string\n                      enum: [Delete, Orphan]\n                      default: Delete"
  → "                    managementPolicies:\n                      type: array\n                      items:\n                        type: string\n                        enum: [\"*\", \"Create\", \"Update\", \"Delete\", \"LateInitialize\", \"Observe\"]\n                      default: [\"*\"]"
```
</example>

### Example 2: Function Import Migration

<example>
**v1 imports:**
```kcl
import models.io.upbound.aws.ec2.v1beta1 as ec2v1beta1
import models.io.upbound.aws.iam.v1beta1 as iamv1beta1
```

**v2 imports:**
```kcl
import models.io.upbound.awsm.ec2.v1beta2 as ec2v1beta2
import models.io.upbound.awsm.iam.v1beta1 as iamv1beta1
```

**Key changes:**
- `aws` → `awsm` (namespaced provider)
- Version may change (v1beta1 → v1beta2) - check provider docs
</example>

### Example 3: providerConfigRef Migration — delete it, don't port it

<example>
**v1 pattern:**
```kcl
_items += [ec2v1beta1.VPC {
    spec.forProvider = {
        region = oxr.spec.parameters.region
    }
    spec.providerConfigRef.name = "default"
}]
```

**v2 pattern:**
```kcl
_items += [ec2v1beta2.VPC {
    spec.forProvider = {
        region = oxr.spec.parameters.region
    }
}]
```

**Key changes:**
- **Delete `providerConfigRef`.** Do not port it and do not add a `kind` field.
  The provider CRD defaults it to `{kind: ClusterProviderConfig, name: default}`,
  which is what project templates, `examples/providerconfig.yaml`, and generated
  E2E tests actually create.
- **Do not add `metadata.namespace`.** It propagates from the XR automatically.

> **Migrating `providerConfigRef.kind = "ProviderConfig"` is an active defect, not a
> no-op.** `ProviderConfig` is the *namespaced* kind; nothing in a generated project
> creates one. A managed resource pointing at it gets **no status conditions and no
> events at all** — it is inert, with nothing to debug. Composition tests pass either
> way, so this only ever surfaces on a live control plane. Verified with two otherwise
> identical namespaced `Bucket`s.

Add `providerConfigRef` back only for a genuinely multi-credential platform, and then
with a `kind` that matches an object the platform actually creates.
</example>

### Example 4: Example YAML Migration

<example>
**v1 example:**
```yaml
apiVersion: aws.example.org/v1alpha1
kind: XNetwork
metadata:
  name: my-network
spec:
  compositionSelector:
    matchLabels:
      provider: aws
  parameters:
    region: us-west-2
  writeConnectionSecretToRef:
    name: network-secret
    namespace: default
```

**v2 example:**
```yaml
apiVersion: aws.example.org/v1alpha1
kind: Network
metadata:
  name: my-network
  namespace: default
spec:
  crossplane:
    compositionSelector:
      matchLabels:
        provider: aws
  parameters:
    region: us-west-2
  # writeConnectionSecretToRef REMOVED - connection secrets handled differently in v2
```

**Key changes:**
- `XNetwork` → `Network` (remove X-prefix)
- Add `namespace: default` to metadata
- Move `compositionSelector` under `spec.crossplane`
- Remove `writeConnectionSecretToRef`
</example>

---

## Error Handling

### Build Failures

**Symptom:** `up project build` fails after dependency updates

**Common causes:**
1. Dependency version mismatch
2. Missing v2 provider models
3. KCL syntax errors in functions

**Resolution:**
```bash
# Check for model availability
ls -la .up/kcl/models/ | grep -E "awsm|azurem|gcpm"

# If missing, force cache update
rm -rf .up/kcl/models/
up dep update-cache

# Rebuild
up project build
```

If still failing → Report error, check dependency versions, exit.

### XRD Edit Failures

**Symptom:** an exact replacement finds no match

**Common causes:**
1. Whitespace differences (tabs vs spaces)
2. File was already partially migrated
3. Multi-line string mismatch

**Resolution:**
1. Read the file to see exact content
2. Adjust the text being replaced to match the exact whitespace
3. If already migrated, skip this edit

### Function Migration Failures

**Symptom:** `author-composition` (or the delegated agent following it) reports FAILURE

**Resolution:**
1. Check the error message for specifics
2. Retry once with an adjusted brief
3. If retry fails → Report error, suggest manual intervention

```markdown
Function migration failed for: functions/{name}/main.k
Error: {error message}

Options:
1. Retry with adjusted approach
2. Skip and continue (manual fix needed later)
3. Abort migration
```

### Test Validation Failures

**Symptom:** `kcl tests/{name}/main.k` returns syntax errors

**Common causes:**
1. Import paths not updated
2. Type mismatches after kind changes
3. Assertion format incorrect

**Resolution:**
1. Run KCL with verbose output to see exact error
2. Check if imports match function imports
3. Verify XR kind matches updated definition

### Composition Test Failures

**Symptom:** Composition tests fail after migration

**Resolution:**
Do NOT continue to E2E tests. User must fix composition tests first.

```markdown
Composition tests failed: X/Y passed

Failed tests:
- {test-name}: {brief error}

Migration paused. Please fix composition test failures before continuing.
After fixing, ask to continue the v2 migration (argument `continue`).
```

---

## Troubleshooting

### Q: Migration plan not found

**Error:** "Run the `plan-v2-migration` skill first"

**Solution:** Generate the migration plan first with the `plan-v2-migration` skill.

### Q: Git branch already exists

**Error:** "Branch migrate-to-v2 already exists"

**Solution:**
```bash
# Check if previous migration attempt
git branch -a | grep migrate-to-v2

# Options:
# 1. Continue on existing branch
git checkout migrate-to-v2

# 2. Delete and restart
git branch -D migrate-to-v2
```

### Q: Some changes were already made

**Symptom:** a replacement finds no match because the v2 pattern is already present

**Solution:** The skill should detect partially migrated files and skip completed edits. If this happens:
1. Read the file to verify current state
2. Skip edits for already-migrated sections
3. Continue with remaining changes

### Q: E2E tests timeout

**Symptom:** E2E tests run for >60 minutes without completion

**Solution:** The `e2e-test-configuration` skill has built-in stuck detection. If it triggers:
1. Check for resource provisioning issues
2. Check cloud provider quotas
3. Consider running tests individually

### Q: Connection secrets not working in v2

**Background:** v2 removes built-in XR connection secret support. Secrets must be explicitly composed.

**Solution:** The function migration should add Secret resource composition. Verify:
1. Function creates Secret resource
2. Secret patches connection data from MRs
3. Test asserts Secret exists with expected keys
