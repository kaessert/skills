# Crossplane v2 Migration Executor - Knowledge Base

Detailed instructions, templates, and examples for executing Crossplane v1 to v2 migrations.

---

## Table of Contents

- [Phase Details](#phase-details)
- [Sub-agent Prompts](#sub-agent-prompts)
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
If missing → Exit with error: "Run plan-v2-migration skill first"

**Read and parse plan:**
```bash
read(".agents/plans/CROSSPLANE_V2_MIGRATION.md")
```

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
If uncommitted changes, ask user once to commit or continue.

**Confirm execution with user (single question):**
Show: Project name, scope (XRD/function/test counts), phases to execute
Ask: "Execute migration? (yes/no)"

---

### Phase 1: Pre-Migration Preparation

**1.1: Create git branch**
```bash
git checkout -b migrate-to-v2
```

**1.2: Update dependencies**

Read dependency updates from migration plan Phase 1.2.

For each provider dependency update:
```bash
replace(file="upbound.yaml", old="version: {old}", new="version: {new}")
```

For each configuration dependency update:
```bash
replace(file="upbound.yaml", old="version: {old}", new="version: {new}")
```

If connection secrets detected in plan:
```bash
replace(file="upbound.yaml", old="spec:\n  dependsOn:", new="spec:\n  apiDependencies:\n  - k8s:\n      version: v1.33.0\n    type: k8s\n  dependsOn:")
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

For each XRD section in migration plan (Phase 2.X):

**Read XRD:**
```bash
read("apis/{resource}/definition.yaml")
```

**Apply updates in sequence:**

```bash
# 1. API version v1 → v2
replace(file="apis/{resource}/definition.yaml",
        old="apiVersion: apiextensions.crossplane.io/v1",
        new="apiVersion: apiextensions.crossplane.io/v2")

# 2. Add scope (if missing)
replace(file="apis/{resource}/definition.yaml",
        old="spec:\n  group:",
        new="spec:\n  scope: Namespaced\n  group:")

# 3. Update kind (remove X-prefix)
replace(file="apis/{resource}/definition.yaml",
        old="kind: X{Kind}",
        new="kind: {Kind}")

# 4. Update metadata.name (remove x-prefix)
replace(file="apis/{resource}/definition.yaml",
        old="name: x{plural}",
        new="name: {plural}")

# 5. Update spec.names.kind
replace(file="apis/{resource}/definition.yaml",
        old="kind: X{Kind}",
        new="kind: {Kind}")

# 6. Update spec.names.plural (if has x-prefix)
replace(file="apis/{resource}/definition.yaml",
        old="plural: x{plural}",
        new="plural: {plural}")
```

**Handle special cases:**

If claimNames detected in plan:
```bash
# Remove claimNames section with a multi-line replace
```

If deletionPolicy parameter detected:
```bash
# Replace with managementPolicies using Edit
# Change type: string → type: array
# Change enum values
```

If connectionSecretKeys detected:
```bash
# Remove connectionSecretKeys section
```

**Validate:**
```bash
yq '.' apis/{resource}/definition.yaml > /dev/null
```

---

### Phase 3: Function Code Migration

**CRITICAL:** Use author-composition skill via sub-agent for each function.

For each function section in migration plan (Phase 3.X):

1. Extract migration requirements from plan for this function
2. Launch sub-agent (see [Sub-agent Prompts](#function-migration-prompt))
3. Wait for completion. If fails → Report error, offer retry once
4. Validate syntax:
```bash
kcl functions/{function-name}/main.k >/dev/null 2>&1
```

Repeat for all functions.

---

### Phase 4: Composition Updates

For each composition section in migration plan (Phase 4.X):

**Update compositeTypeRef kind:**
```bash
replace(file="apis/{resource}/composition.yaml",
        old="kind: X{Kind}",
        new="kind: {Kind}")
```

**Validate:**
```bash
yq '.' apis/{resource}/composition.yaml > /dev/null
```

---

### Phase 5: Example Updates

For each example section in migration plan (Phase 5.X):

**Update kind:**
```bash
replace(file="examples/{file}.yaml",
        old="kind: X{Kind}",
        new="kind: {Kind}")
```

**Add namespace (if missing):**
```bash
if ! grep -q "namespace:" examples/{file}.yaml; then
  replace(file="examples/{file}.yaml",
          old="metadata:\n  name: {name}",
          new="metadata:\n  name: {name}\n  namespace: default")
fi
```

**Move compositionSelector (if at wrong level):**
```bash
# Check if compositionSelector exists at spec level
if grep -A1 "^spec:" examples/{file}.yaml | grep -q "compositionSelector:"; then
  # Extract compositionSelector content
  # Move to spec.crossplane.compositionSelector using Edit
fi
```

**Remove writeConnectionSecretToRef (if present):**
```bash
# Use Grep to detect, Edit to remove section
```

**Validate:**
```bash
yq '.' examples/{file}.yaml > /dev/null
```

---

### Phase 6: Test Updates

**CRITICAL:** Use author-tests skill via sub-agent for each test.

For each test section in migration plan (Phase 6.X):

1. Determine test type: composition (test-*) or E2E (e2etest-*)
2. Extract migration requirements from plan for this test
3. Launch sub-agent (see [Sub-agent Prompts](#test-migration-prompt))
4. Wait for completion. If fails → Report error, offer retry once
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

Use verify-configuration skill via a sub-agent (see [Sub-agent Prompts](#verification-prompt)).

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

Ask user once: "Run E2E tests? (30-60 min, uses cloud resources) [yes/no/skip]"

If yes: Launch sub-agent (see [Sub-agent Prompts](#e2e-test-prompt)).

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

If yes → Use Edit to update README.md based on user guidance.
If no → Proceed to final summary.

---

## Sub-agent Prompts

Hand each brief to a sub-agent and wait for its result. If your harness has no sub-agents,
follow the brief yourself (`control-plane-project-charter` §1).

### Function Migration Prompt

Brief — *Migrate function {name} to v2*:

```text
Migrate Crossplane function to v2: functions/{function-name}/main.k

Keep the exact function name — do NOT add a language suffix (`-python`/`-kcl`). The directory name is the published registry path and must stay in the publish allow-list.

Load the `author-composition` skill
Tell skill: "Migrate this function from v1 to v2"

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

### Test Migration Prompt

Brief — *Update test {name} for v2*:

```text
Update Crossplane test for v2: tests/{test-name}/main.k

Load the `author-tests` skill
Tell skill: "Update this test for v2 migration"

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

### Verification Prompt

Brief — *Verify build and composition tests*:

```text
Load the `verify-configuration` skill

When asked about E2E tests, select "No - I'll run them later"

**SUCCESS CRITERIA:**
1. `up project build` completes without errors
2. All composition tests pass

**Return format:**
- Build status: SUCCESS | FAILURE
- Composition tests: X/Y passed
- Failure details: [if any failures, include test name and error]
```

### E2E Test Prompt

Brief — *Run E2E tests*:

```text
Load the `e2e-test-configuration` skill for these tests: {names from
`ls -1d tests/e2etest-* | sed 's|tests/||'`}

Run each named test with monitoring.

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

**Edit commands used:**
```bash
# 1. API version
replace(old="apiVersion: apiextensions.crossplane.io/v1",
        new="apiVersion: apiextensions.crossplane.io/v2")

# 2. Add scope
replace(old="spec:\n  group:",
        new="spec:\n  scope: Namespaced\n  group:")

# 3. Update metadata.name
replace(old="name: xnetworks.aws.example.org",
        new="name: networks.aws.example.org")

# 4. Update kind
replace(old="kind: XNetwork",
        new="kind: Network")

# 5. Update plural
replace(old="plural: xnetworks",
        new="plural: networks")

# 6. Remove claimNames (multi-line edit)
replace(old="  claimNames:\n    kind: Network\n    plural: networks\n",
        new="")

# 7. Remove connectionSecretKeys
replace(old="  connectionSecretKeys:\n    - vpcId\n    - subnetIds\n",
        new="")

# 8. Replace deletionPolicy with managementPolicies
replace(old="                    deletionPolicy:\n                      type: string\n                      enum: [Delete, Orphan]\n                      default: Delete",
        new="                    managementPolicies:\n                      type: array\n                      items:\n                        type: string\n                        enum: [\"*\", \"Create\", \"Update\", \"Delete\", \"LateInitialize\", \"Observe\"]\n                      default: [\"*\"]")
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

**Symptom:** the replacement fails with "old text not found"

**Common causes:**
1. Whitespace differences (tabs vs spaces)
2. File was already partially migrated
3. Multi-line string mismatch

**Resolution:**
1. Read the file to see exact content
2. Adjust the old text to match exact whitespace
3. If already migrated, skip this edit

### Function Migration Failures

**Symptom:** sub-agent reports FAILURE

**Resolution:**
1. Check the error message for specifics
2. Offer user one retry with adjusted prompt
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
After fixing, ask to continue the migration (execute-v2-migration resumes from the plan)
```

---

## Troubleshooting

### Q: Migration plan not found

**Error:** "Run plan-v2-migration skill first"

**Solution:**
```bash
# Generate migration plan first
Plan the migration again (plan-v2-migration)
```

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

**Symptom:** Edit fails because v2 patterns already present

**Solution:** The skill should detect partially migrated files and skip completed edits. If this happens:
1. Read the file to verify current state
2. Skip edits for already-migrated sections
3. Continue with remaining changes

### Q: E2E tests timeout

**Symptom:** E2E tests run for >60 minutes without completion

**Solution:** The e2e-test-configuration skill has built-in stuck detection. If it triggers:
1. Check for resource provisioning issues
2. Check cloud provider quotas
3. Consider running tests individually

### Q: Connection secrets not working in v2

**Background:** v2 removes built-in XR connection secret support. Secrets must be explicitly composed.

**Solution:** The function migration should add Secret resource composition. Verify:
1. Function creates Secret resource
2. Secret patches connection data from MRs
3. Test asserts Secret exists with expected keys
