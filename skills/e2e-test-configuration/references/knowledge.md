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
# 1. Get kubeconfig for the CURRENT context (without changing it), written fresh
rm -f /tmp/e2e-<test-name>.kubeconfig
up ctx . -f- > /tmp/e2e-<test-name>.kubeconfig
grep -q '^apiVersion:' /tmp/e2e-<test-name>.kubeconfig || echo "not a kubeconfig"
up ctx . --short | cut -d/ -f3   # → <group>: 3rd segment of <org>/<space>/<group>[/<ctp>]

# 2. Verify connectivity
up ctp list --kubeconfig /tmp/e2e-<test-name>.kubeconfig

# 3. Build project
up project build

# 4. Run composition tests
up test run tests/*
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
up test run tests/<test-name> --e2e --control-plane-group=<group> \
  --kubeconfig /tmp/e2e-<test-name>.kubeconfig 2>&1 | tee /tmp/e2e-<test-name>.log
echo "EXIT=${PIPESTATUS[0]}"
```

**Foreground by default**, when your shell can hold one command open for the whole run.
The result carries the complete output and the true exit code, which is the entire record.

**Background only when the run cannot fit** — check the test's `spec.timeoutSeconds`
(scaffold default 4500s) and expect a first run pulling providers to overrun. Use the agent's
own background execution, or the `nohup` wrapper in SKILL.md Phase 3, which writes `EXIT=<n>`
into the log and the wrapper's PID into `<log>.pid`. **Wait for the exit**; a poll is a
progress view for the user, never the basis of a verdict.

---

## Monitoring Loop (background path only)

Progress reporting, not verdicts — the run is finished when the process exits.

One poll, every 3 minutes, from any shell:

```bash
grep '^EXIT=' /tmp/e2e-<test-name>.log && echo "finished"   # the only signal that the run is over
wc -c < /tmp/e2e-<test-name>.log                             # compare with the last poll: grew = progress
tail -n 20 /tmp/e2e-<test-name>.log                          # what to show the user
```

The decision around it:

- **Stuck threshold** = `min(900, timeoutSeconds / 3)` seconds, from the test's own
  `spec.timeoutSeconds`. A fixed 900 can never fire on a test whose `timeoutSeconds` is
  300 — the run dies at 5 minutes and stuck detection is unreachable. If `timeoutSeconds` is
  at or below the threshold, treat the timeout itself as the investigation trigger and say so
  in the report.
- **Log grew** since the last poll → reset the progress timer and show a one-line update.
- **No growth for the threshold** → check `crossplane beta trace` (below). Still `Creating`
  → reset the timer and continue. Not creating → run the stuck investigation, then stop the
  run by PID.

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

## Stuck Investigation Checklist

Run this when a test is stuck (no progress for the threshold, not creating). Run it yourself,
or hand it to a separate agent if yours can delegate — either way, only the final analysis
goes back to the caller.

**Context to carry:**
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
kubectl logs -n upbound-system -l pkg.crossplane.io/provider --tail=200 --kubeconfig /tmp/kubeconfig-<cp-name> | grep -iE "error|denied|auth"
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

4. Produce ONLY this (max 100 lines):

```markdown
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
```

Then stop the run by PID (`pkill -P "$(cat /tmp/e2e-<test-name>.pid)"; kill "$(cat /tmp/e2e-<test-name>.pid)"`) and
report any control plane the terminated run left behind.

---

## Report Formats

- **Success** (5-10 lines): test name, exit code, duration *quoted from the log*, resources
  created, timeline.
- **Stuck/Failure** (50-100 lines): test name, stuck duration, phase, last output,
  troubleshooting analysis, proposed fixes.

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
## E2E Test: STUCK (Terminated)

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
<INSERT TROUBLESHOOTING ANALYSIS>

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
3. Stop on first failure (ask the user whether to continue; as a delegated agent, stop and report)
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
