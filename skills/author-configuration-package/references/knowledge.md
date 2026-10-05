# Knowledge: Crossplane Configuration Package Authoring

Detailed templates, phase instructions, and reference material for the author-configuration-package skill.

---

## Templates

### XRD Template (v2, Namespaced)

```yaml
apiVersion: apiextensions.crossplane.io/v2
kind: CompositeResourceDefinition
metadata:
  name: {plural}.{group}
spec:
  scope: Namespaced
  group: {group}
  names:
    kind: {Kind}
    plural: {plural}
  versions:
  - name: {version}
    served: true
    referenceable: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              # Fields from wizard go here
              region:
                type: string
                description: "AWS region"
              cidrBlock:
                type: string
                description: "CIDR block for VPC"
                default: "10.0.0.0/16"
            required:
              - region
```

### upbound.yaml Template

```yaml
apiVersion: meta.dev.upbound.io/v2alpha1
kind: Project
metadata:
  name: {project-name}
spec:
  dependsOn:
    - apiVersion: pkg.crossplane.io/v1
      kind: Function
      package: xpkg.upbound.io/crossplane-contrib/function-auto-ready
      version: '>=vX.Y.Z'   # always a constraint; a bare `up dep add <ref>` writes '>=v0.0.0'
    # Providers added here during Phase 4
  description: {description}
  license: Apache-2.0
  maintainer: {maintainer}
  readme: |
    Crossplane configuration package for {project-name}
  repository: xpkg.upbound.io/{org}/{project-name}
  source: github.com/{org}/{project-name}
```

### Provider Dependency Template

```yaml
# AWS provider example
- apiVersion: pkg.crossplane.io/v1
  kind: Provider
  package: xpkg.upbound.io/upbound/provider-aws-ec2
  version: '>=v2.0.0'
```

### Composition Skeleton Template

The shape `up composition generate` produces (`mode: Pipeline` with an auto-ready step), for
reading. Generate it rather than copying this (SKILL.md: use the generators for everything
but the XRD).

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: {plural}.{group}
spec:
  compositeTypeRef:
    apiVersion: {group}/{version}
    kind: {Kind}
  mode: Pipeline  # v2: ONLY valid mode — 'Resources' mode was removed in Crossplane v2
  pipeline:
    - functionRef:
        name: crossplane-contrib-function-auto-ready
      step: crossplane-contrib-function-auto-ready
```

**Note:** `up function generate` will add the function reference and reorder pipeline.

### .gitignore Template

```text
# Build artifacts
_output/
*.uppkg

# Generated models
.up/

# Go: `go build ./...` writes a binary named after its directory. One line per
# function; the test patterns cover every scaffolded test directory.
functions/<function-name>/<function-name>
tests/*/test-*
tests/*/e2etest-*

# IDE files
.vscode/
.idea/
*.swp
*.swo
*~

# OS files
.DS_Store
Thumbs.db

# Dependency cache
.cache/
```

### Example Manifest Template (Simple)

```yaml
apiVersion: {group}/{version}
kind: {Kind}
metadata:
  name: example-{resource}
  namespace: default
spec:
  # Only required fields
  region: us-west-2
```

### Example Manifest Template (Complete)

```yaml
apiVersion: {group}/{version}
kind: {Kind}
metadata:
  name: example-{resource}-complete
  namespace: default
spec:
  # All fields - required and optional
  region: us-west-2
  cidrBlock: "10.0.0.0/16"
  enableDnsHostnames: true
  tags:
    environment: development
```

---

## Detailed Phase Instructions

### Phase 0: Mode Detection

```bash
# Detect project state
test -f upbound.yaml && echo "Existing project" || echo "New project"

# List current resources if existing
find apis -name "definition.yaml" 2>/dev/null | sed 's|apis/||;s|/definition.yaml||'
```

**Options to ask the user:**
- New project
- Modify existing → Add new resource
- Modify existing → Change existing resource

### Phase 1: Project Information (New Projects)

**Ask the user for:**

| Field | Example | Notes |
|-------|---------|-------|
| Project name | configuration-aws-database | Prefix with "configuration-" |
| API group | aws.platform.upbound.io | Domain format |
| Cloud provider | AWS, Azure, GCP, Other | For provider suggestions |
| Organization | upbound | For repository field |
| Maintainer | team@example.com | Email |

**Create base structure:**
```bash
mkdir -p apis examples scripts
# Create upbound.yaml from template
# Create .gitignore from template
```

### Phase 2: Resource Definition

**Ask the user for:**

| Field | Example | Default |
|-------|---------|---------|
| Resource Kind | VPC, Database | Required |
| Plural name | vpcs, databases | Auto from Kind |
| Version | v1, v1alpha1 | v1 |

**Create directory:**
```bash
mkdir -p apis/{resource}
```

### Phase 3: XRD Schema Wizard

**Loop structure:**

```text
WHILE user wants to add fields:
  1. Ask field name
  2. Ask field type (string/integer/boolean/array/object)
  3. Ask description
  4. Ask if required
  5. Ask default value (optional)
  6. Ask "Add another field?"
END LOOP
```

**Build schema incrementally:**
```yaml
properties:
  {fieldName}:
    type: {fieldType}
    description: "{description}"
    default: {defaultValue}  # Only if provided
```

**Track required fields:**
```yaml
required:
  - {requiredField1}
  - {requiredField2}
```

### Phase 4: Dependencies

**Present provider options based on cloud:**

**AWS providers:**
| Package | Use Case |
|---------|----------|
| provider-aws-ec2 | VPC, subnets, gateways, instances |
| provider-aws-rds | Databases (RDS, Aurora) |
| provider-aws-s3 | Storage buckets |
| provider-aws-iam | Identity, roles, policies |
| provider-aws-eks | Kubernetes clusters |
| provider-aws-lambda | Serverless functions |
| provider-aws-sns | Notifications |
| provider-aws-sqs | Message queues |

**Azure providers:**
| Package | Use Case |
|---------|----------|
| provider-azure-compute | VMs, scale sets |
| provider-azure-network | VNets, subnets, load balancers |
| provider-azure-storage | Storage accounts, blobs |
| provider-azure-aks | Kubernetes clusters |
| provider-azure-sql | Databases |

**GCP providers:**
| Package | Use Case |
|---------|----------|
| provider-gcp-compute | VMs, networks |
| provider-gcp-network | VPCs, firewalls |
| provider-gcp-storage | Cloud storage |
| provider-gcp-gke | Kubernetes clusters |
| provider-gcp-sql | Cloud SQL |

**After selection:**
```bash
up dep update-cache
```

**Verify cache update:**
```bash
ls .cache/  # Should show downloaded provider schemas
```

### Phase 5: Composition & Language

**Language options:**
| Language | Notes |
|----------|-------|
| KCL | Recommended, best typing support |
| Go | For complex logic, function-sdk-go |
| Python | For complex logic, function-sdk-python |

**Generate the composition:** `up composition generate apis/{resource}/definition.yaml`. The
Composition Skeleton Template above shows what it produces; do not write it by hand.

**CRITICAL:** Only include `function-auto-ready` at this stage. The function reference will be added by `up function generate`.

### Phase 6: First Build

```bash
up project build
```

**Validate models generated:**
```bash
if [ -d ".up/kcl/models" ]; then     # .up/python/models, .up/go/models for those languages
  echo "models generated"
  ls .up/kcl/models/ | head -10
else
  echo "models missing - check providers"
fi
```

**If build fails:**
1. Check provider versions (must be v2.x for AWS)
2. Verify `up dep update-cache` completed
3. Check upbound.yaml syntax
4. Check XRD syntax (must be v2, Namespaced)

### Phase 7: Function Generation

```bash
up function generate {resource} apis/{resource}/composition.yaml --language kcl
```

**What this creates:**
- `functions/{resource}/main.k` - Entry point
- `functions/{resource}/kcl.mod` - Module config
- `functions/{resource}/model/` - Symlink to .up/kcl/models

**What this updates:**
- `apis/{resource}/composition.yaml` - Adds function reference

**Verify pipeline order:**
```bash
grep -A 20 "pipeline:" apis/{resource}/composition.yaml
```

**CRITICAL:** `function-auto-ready` MUST be LAST. If not, edit composition.yaml.

### Phase 8: Examples

Create two example files:

1. **Simple** (`examples/{resource}-simple.yaml`):
   - Only required fields
   - Minimal configuration

2. **Complete** (`examples/{resource}-complete.yaml`):
   - All fields (required + optional)
   - Shows full capability

3. **README** (`examples/README.md`):
   ```markdown
   # Examples

   ## Simple Example
   kubectl apply -f {resource}-simple.yaml

   ## Complete Example
   kubectl apply -f {resource}-complete.yaml
   ```

### Phase 9: Final Build

```bash
up project build
```

**Validate package:**
```bash
ls -lh _output/*.uppkg
```

**If build fails:**
1. Check main.k syntax
2. Check kcl.mod dependencies
3. Check composition.yaml pipeline

---

## Common Pitfalls

### 1. Models Not Generated

**Symptom:** `.up/kcl/models/` empty or missing after first build.

**Causes:**
- Using v1.x provider (must be v2.x)
- Skipped `up dep update-cache`
- Provider package name wrong

**Fix:**
```bash
# Check provider version in upbound.yaml
grep -A 2 "provider-aws" upbound.yaml

# Should show version >= v2.0.0
# Update and rebuild:
up dep update-cache
up project build
```

### 2. XR Never Reaches Ready

**Symptom:** XR stays in "Creating" state forever.

**Cause:** `function-auto-ready` not last in pipeline.

**Fix:** Edit `apis/{resource}/composition.yaml`:
```yaml
pipeline:
  - functionRef:
      name: {org}-{project}{resource}
    step: {org}-{project}{resource}
  - functionRef:
      name: crossplane-contrib-function-auto-ready
    step: crossplane-contrib-function-auto-ready  # MUST BE LAST
```

### 3. Function Generate Fails

**Symptom:** `up function generate` errors about missing models.

**Cause:** First build not run, or build failed.

**Fix:**
```bash
# Ensure first build completed
up project build

# Check models exist
ls .up/kcl/models/

# Then generate function
up function generate {resource} apis/{resource}/composition.yaml --language kcl
```

### 4. Wrong XRD Version

**Symptom:** Resources created but features missing, scope wrong.

**Cause:** Using XRD apiVersion v1 instead of v2.

**Fix:** Update `apis/{resource}/definition.yaml`:
```yaml
# WRONG
apiVersion: apiextensions.crossplane.io/v1

# CORRECT
apiVersion: apiextensions.crossplane.io/v2
```

### 5. Cluster vs Namespaced Scope

**Symptom:** Resources not found, namespace issues.

**Cause:** Using Cluster scope instead of Namespaced.

**Fix:** In `apis/{resource}/definition.yaml`:
```yaml
spec:
  scope: Namespaced  # NOT Cluster
```

### 6. Composition Uses Removed `Resources` Mode

**Symptom:** Composition test passes locally, but applying the XR to a control plane fails admission with an error about `spec.mode`.

**Cause:** `spec.mode: Resources` — the legacy Crossplane v1 default. It was **removed in Crossplane v2**; only `Pipeline` is valid. `up test run`'s local render is lenient and doesn't enforce v2 admission, so it slips through. This is a v1-ism usually reintroduced by hand-editing the composition — **not** by the CLI/skeleton: every `up` scaffold (`up composition generate`, `up project init` templates, `up function generate`) emits `Pipeline`.

**Fix:** In `apis/{resource}/composition.yaml`:
```yaml
spec:
  mode: Pipeline  # NOT Resources (removed in v2)
```

---

## Validation Checklist

Before handing off, verify:

- [ ] `upbound.yaml` exists with correct metadata
- [ ] No unbounded dependency: no `dependsOn` entry at `version: '>=v0.0.0'`
- [ ] `apis/{resource}/definition.yaml` uses v2, Namespaced
- [ ] `apis/{resource}/composition.yaml` has correct pipeline order
- [ ] `functions/{resource}/` generated by `up function generate`, its step before auto-ready
- [ ] Models under `.up/<language>/` populated with provider schemas
- [ ] Example XRs under `examples/`, plus `examples/providerconfig.yaml`
- [ ] Final build produces `_output/*.uppkg`

---

## Integration Points

### Hand-off to author-tests and author-composition, test first

For each behaviour, the composition test comes first: `author-tests` writes it and watches it
fail for the intended reason, then `author-composition` implements the function in
`functions/{resource}/` against the generated models under `.up/<language>/` until it passes
(charter §3).

### The gate

Once the suite is green: the project's own gate if it has one, else `verify-configuration`
for the build and the whole `up test run`. E2E tests or a deploy only where the project, the
user or your instructions allow it (charter §9).

---

## After the final build: deploying it somewhere

This skill stops at a built package; it does not deploy. But the command you will reach for
next has a failure mode worth knowing before you run it, because nothing in the CLI points
at it:

```bash
up ctx .                       # FIRST: does the context name a Space?
up project run --timeout=20m   # ...then run, with the flag the answer implies
```

Which kind of dev control plane you get is decided by your **current `up` context**, not by a
flag — a cloud one when the context is an Upbound Space, a local KIND one otherwise. On the
**cloud** path `up project run` pushes to a **private** repository and then installs onto a
control plane it gives no pull credential, so the second half fails on what the first half
wrote, and it reports the 401 as `context deadline exceeded`. The default `--timeout` of `5m`
is also short for a first run that pulls providers.

**If the context is a Space, ask the user which they want** — do not choose for them, and do
not silently fall back to `--local`. They connected to that Space deliberately, and a local
KIND cluster is a different environment, not a transparent substitute. The three options are:
supply pull access for the cloud control plane (ask where the pull secret is), `--public`
(which **permanently publishes their package** — a disclosure decision, never a debugging
step), or `--local` (side-loads, so the pull failure cannot occur, and still creates real
cloud resources).

Full diagnosis, the `kubectl describe` that actually names the error, and the
kubeconfig-left-pointing-elsewhere trap: see the **verify-configuration** skill,
*"When a run hangs on Waiting for package to be ready"*.
