# E2E Test Configuration - Knowledge Base

Detailed reference for the e2e-test-configuration skill. See SKILL.md for the core workflow.

## Provider API Versions

**Understanding Upbound Provider Architecture:**

All Upbound providers (provider-aws-iam, provider-aws-ec2, provider-aws-eks, etc.) are part of the **provider family architecture**:
- **Single providers**: Individual providers like provider-aws-iam, provider-aws-ec2, provider-aws-eks
- **Provider family (provider-family-aws)**: Either refers to the collection of single providers, or a meta-provider with shared logic that Crossplane auto-installs as a dependency

**API Versions:**

| Type | Format | Used? |
|------|--------|-------|
| Namespaced | `aws.m.upbound.io/v1beta1` | YES - always use this |
| Cluster-scoped | `aws.upbound.io/v1beta1` | NO - valid but we don't use |

The `.m.` marks the **modern** (Crossplane v2) API group — not "naMespaced" and not "monolithic". It holds the namespaced managed resources *and* the cluster-scoped `ClusterProviderConfig` they default to, which is why "m = namespaced" cannot be right. See `control-plane-project-charter` §5.

**Common Misconceptions to Avoid:**
- "Family providers use v1 API which doesn't support apiVersion in providerConfigRef" - FALSE
- "Single providers vs family providers have different APIs" - FALSE
- "The .m. stands for monolithic" - FALSE

---

## Pre-Validation Commands

```bash
# 1. Get kubeconfig for the CURRENT context (without changing it), to a fresh file
KCFG=$(mktemp -t kubeconfig-e2e.XXXXXX)
up ctx . -f- > "$KCFG"
grep -q '^apiVersion:' "$KCFG" || { echo "not a kubeconfig: $KCFG"; exit 1; }
echo "kubeconfig: $KCFG"   # reuse this literal path in later commands
up ctx . --short | cut -d/ -f3   # the group: 3rd segment of <org>/<space>/<group>[/<ctp>]

# 2. Verify connectivity
up ctp list --kubeconfig "$KCFG"

# 3. Build project
up project build

# 4. Run composition tests (test-* only: tests/* also runs every e2e program, even without --e2e)
up test run "tests/test-*"
```

**Stop execution if ANY step fails.**

---

## Resource Extraction

Before running a test, extract resources to monitor:

```bash
# Extract all resources from test manifests
# Output: <kind> <name> <namespace> (tab-separated)
kcl tests/<test-name>/ | yq -o json '.items[].spec.manifests' | jq -r '.[] | [(.kind | ascii_downcase), .metadata.name, .metadata.namespace] | @tsv'
```

Store as `RESOURCE_KIND`, `RESOURCE_NAME`, `RESOURCE_NAMESPACE` for monitoring.

---

## Test Execution Command

```bash
# --public only if the caller chose it; it permanently publishes the package.
# <group> and <kubeconfig> are the literal values pre-validation printed.
up test run tests/<test-name> --e2e --control-plane-group=<group> \
  --kubeconfig <kubeconfig> 2>&1 | tee /tmp/e2e-<test-name>.log
echo "EXIT=${PIPESTATUS[0]}"
```

**Foreground by default:** one Bash call, `timeout: 600000` (10 min, the tool's maximum).
The result carries the complete output and the true exit code, which is the entire record.

**Background only when the run cannot fit in ten minutes** — check the test's
`spec.timeoutSeconds` (scaffold default 4500s) and expect a first run pulling providers to
overrun. Then run it in the background, and **wait for the exit notification**; a poll of the background output is a progress view for the user, never the basis of a verdict.
If your harness cannot run commands in the background, run it in the foreground with the
longest timeout your shell allows — do not detach it yourself — and report a run that timeout cut off as *cut off*, not
as an outcome (`control-plane-project-charter` §1).

---

## Monitoring Loop (background path only)

Progress reporting, not verdicts — the run is finished when the process exits.

```python
last_output = ""
last_progress_time = current_time
check_interval = 180  # 3 minutes
# Derive from the test's own spec.timeoutSeconds. A fixed 900 can never fire on a test
# whose timeoutSeconds is 300 — the run dies at 5 min and this branch is unreachable.
stuck_threshold = min(900, test_timeout_seconds // 3)
if test_timeout_seconds <= stuck_threshold:
    # The test times out before "stuck" could ever be declared; treat the timeout itself
    # as the investigation trigger and say so in the report.
    stuck_threshold = None

while test_running:
    current_output = background_output_so_far()  # your harness's own tool

    if current_output != last_output:
        last_progress_time = current_time
        last_output = current_output
        display_progress_update(current_output)

    time_since_progress = current_time - last_progress_time
    if time_since_progress >= stuck_threshold:
        if not resources_still_creating():
            trigger_stuck_investigation()
            break
        else:
            last_progress_time = current_time  # Reset timer

    wait(check_interval)
```

**Progress Indicators:**
- New log output
- Phase changes: Building → Creating CP → Applying → Waiting → Cleanup
- Resource status changes
- New kubectl events

**Creating Status Exception:**

Before declaring stuck, check `crossplane beta trace`:
```bash
KUBECONFIG=/tmp/kubeconfig-<cp-name> crossplane beta trace $RESOURCE_KIND $RESOURCE_NAME -n $RESOURCE_NAMESPACE
```

NOT stuck if STATUS shows `Creating` - cloud resources may take time (VPN Gateways, NAT Gateways, RDS).

---

## Stuck Investigation Subagent Prompt

Launch a sub-agent with this brief when test is stuck 15+ minutes — or, if your harness has
no sub-agents, follow it yourself (`control-plane-project-charter` §1):

Brief — *Troubleshoot stuck E2E test*:

```text
You are troubleshooting a stuck Crossplane E2E test (15+ min no progress).

**Context:**
- Test: <test-name>
- Control plane: <cp-name>
- Resource: <RESOURCE_KIND>/<RESOURCE_NAME> in <RESOURCE_NAMESPACE>
- Phase when stuck: <phase>
- Last output: <last-lines>

**Steps:**

1. Get kubeconfig:
```bash
up ctx <cp-name> -f- > /tmp/kubeconfig-<cp-name>   # relative to the current group
```

2. Collect debug info (use --kubeconfig flag on ALL commands):

**If stuck at "Waiting for package":**
```bash
kubectl get pkgrev -o wide --kubeconfig /tmp/kubeconfig-<cp-name>
kubectl describe configuration --kubeconfig /tmp/kubeconfig-<cp-name>
```

**If stuck at "Applying Extra Resources":**
```bash
kcl tests/<test>/ | yq -o json '.items[].spec.extraResources'
kubectl get providerconfig -A -o wide --kubeconfig /tmp/kubeconfig-<cp-name>
```

**Resource status:**
```bash
kubectl get $RESOURCE_KIND $RESOURCE_NAME -n $RESOURCE_NAMESPACE -o yaml --kubeconfig /tmp/kubeconfig-<cp-name>
kubectl get managed -o wide --kubeconfig /tmp/kubeconfig-<cp-name>
KUBECONFIG=/tmp/kubeconfig-<cp-name> crossplane beta trace $RESOURCE_KIND $RESOURCE_NAME -n $RESOURCE_NAMESPACE -o wide
```

**Events:**
```bash
kubectl get events -n $RESOURCE_NAMESPACE --sort-by='.lastTimestamp' --kubeconfig /tmp/kubeconfig-<cp-name> | tail -50
```

**Provider/Function logs:**
```bash
kubectl logs -n upbound-system -l pkg.crossplane.io/provider --tail=200 --kubeconfig /tmp/kubeconfig-<cp-name> | grep -i "error|denied|auth"
kubectl logs -n crossplane-system -l pkg.crossplane.io/function=function-kcl --tail=200 --kubeconfig /tmp/kubeconfig-<cp-name> | grep -i "error"
```

3. Map to failure patterns:

| Symptom | Likely Cause |
|---------|--------------|
| Stuck "Waiting for package" | Package install failed, dependency issue |
| Stuck "Applying Extra Resources" | ProviderConfig invalid, missing secrets |
| Resources "Creating", no errors | Cloud API slow (normal) or auth issue |
| "ProviderConfig not found" | Missing namespace, wrong API version |
| Function errors | KCL syntax error |
| "AccessDenied" | IAM role issue |

4. Return ONLY this (max 100 lines):

---
## Root Cause Analysis
**Primary Issue:** <1-2 sentences>
**Cause:** <2-3 sentences>
**Category:** <composition error | provider issue | infrastructure | authentication>

## Proposed Fixes
**1. <Issue>**
- **File:** `<path>`
- **Problem:** <what's wrong>
- **Solution:** <change needed>

## Key Evidence
- <error/condition 1>
- <error/condition 2>
---
```

After the investigation completes: stop the background run with your harness's own tools.

---

## Report Formats

### Success Report
```markdown
## E2E Test: PASSED

**Test:** <test-name>
**Duration:** <total-time>
**Control Plane:** <cp-name>

### Resources Created
<list key resources>

### Timeline
- 00:00 - Building & deploying
- XX:XX - Creating control plane
- XX:XX - Resources provisioning
- XX:XX - Cleanup complete
```

### Stuck/Failure Report
```markdown
## E2E Test: STUCK (Canceled)

**Test:** <test-name>
**Stuck Duration:** 15m (no progress)
**Phase When Stuck:** <phase>
**Control Plane:** <cp-name>

---
### Stuck Detection Details
**Last Output:**
```
<last few lines>
```

---
### Troubleshooting Analysis
<INSERT SUBAGENT OUTPUT>

---
### References
- Test directory: `tests/<test>/`
- Related file: `<file>`
```

---

## Expected Timings

| Phase | Duration |
|-------|----------|
| Normal E2E test | 30-40 minutes |
| Stuck threshold | `min(15 min, spec.timeoutSeconds / 3)` — never a fixed 15 min |
| Monitoring interval | 3 minutes |

---

## Multiple Tests Execution

When running multiple tests:
1. Run **sequentially** (not parallel)
2. Wait for completion before next
3. Stop on first failure (ask user to continue)
4. Aggregate results in final summary

```
[1/3] test-basic-vpc
  Running...
  PASSED (25m 34s)

[2/3] test-secondary-cidr
  Running...
  STUCK (canceled after 15min)

Stopped after failure. Run remaining tests? (y/n)
```
