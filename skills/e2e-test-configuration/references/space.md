# Running E2E on an Upbound Space (Upbound Cloud)

Read before running `up test run --e2e` against a Space. [SKILL.md](../SKILL.md) has what both targets share:
preconditions, the run idiom, stuck detection and the report. Facts are from the up v0.55.0 source and earlier
runs of this skill, and could change between versions.

## Preconditions

Run these after SKILL.md Step 1's build, composition and credential checks, stopping at the first failure.

**1. The context resolves to a group.** `--control-plane-group` defaults to the group in the current
context, so a Space-level context with no group silently runs on local kind instead.

```bash
up ctx . --short                       # <org>/<space>/<group>[/<control-plane>]
GROUP=$(up ctx . --short | cut -d/ -f3)
[ -n "$GROUP" ] || echo "no group in context; select one with 'up ctx <org>/<space>/<group>'"
```

Bare `up ctx` cannot work for an agent: with no terminal it fails with `could not open a new TTY: open
/dev/tty: device not configured`. The non-interactive forms are `up ctx .` (current context), `up ctx .
--short` (bare path) and relative navigation (`up ctx ../<name>`).

Derive the group from the context; never hardcode one. If the group the context names does not exist, report
it. Never create a group, space or control plane to make the run work: that is an outward-facing change to the
user's Space that outlives the run. Observed: a default borrowed from another Space named an absent group, the
agent created it, and an empty group was left behind.

**2. The repository the package is pushed to is pullable.** On a Space, `--e2e` builds and pushes the
package, then installs it on a control plane it gives no pull credential. A private repository makes the
install fail to pull what the push just wrote: the run stalls on `Waiting for package to be ready` and exits
`context deadline exceeded`, which names neither half of the problem. A one-second check predicts it:

```bash
REPO=$(yq -r '.spec.repository // .metadata.name' upbound.yaml | sed 's|.*/||')
up repository get "$REPO" --format=json 2>/dev/null \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); d=d[0] if isinstance(d,list) else d; print("public =", d.get("public"))' \
  || echo "repository does not exist yet"
```

`--public` creates **new** repositories public (`up test run --help`: "Create new repositories with public
visibility.") and does not change an existing one:

| Repository state | Without `--public` | With `--public` |
|---|---|---|
| Does not exist yet | created **private**: install cannot pull, `context deadline exceeded` | created public: works |
| Exists, `public: true` | works | works |
| Exists, `public: false` | hangs, then `context deadline exceeded` | **still hangs**: the flag does not flip an existing repository |

Adding `--public` to a retry looks like the fix for the last row and changes nothing.

**`--public` is the user's decision, never yours.** It permanently publishes their package; that is a
disclosure choice, not a debugging step, and re-running without the flag does not undo it.

- If the caller already chose `--public` (in the brief, or earlier in the conversation), use it and do not ask
  again.
- Otherwise, before burning a run, name the options: publish publicly, change the existing repository's
  visibility (the user's call, outside this skill), push to a repository the control plane can already pull
  from (`--repository`), or have the caller choose the local target instead. Interactive, ask; unattended,
  stop and report. Never add `--public` because a run hung.

**3. Credentials.** `source: Upbound` web identity works here, and only here. Each test gets its own control
plane named `<project>-uptest-<test>`, so a trust policy needs a wildcard subject (inference). A static Secret
works too. Shapes: author-tests' `e2e.md` reference.

## Target flags

`--kubeconfig` is an input the CLI reads, never an output it writes. A stale or garbage file at that path is
believed, fails to resolve, and the run silently falls back to `Creating local development control plane...`.
Observed: a leftover `/tmp/kubeconfig-*` holding an error string turned a Space run into a local one. So write
it fresh, check it, and pass `--control-plane-group` explicitly even when the context names the group:

```bash
KCFG=$(mktemp -t kubeconfig-e2e.XXXXXX)
up ctx . -f- > "$KCFG"
grep -q '^apiVersion:' "$KCFG" || { echo "not a kubeconfig: $KCFG"; head -3 "$KCFG"; }
echo "group: $GROUP  kubeconfig: $KCFG"   # shell variables do not survive to your next command; reuse the values
```

The target flags for SKILL.md Step 3's run idiom are then:

```bash
up test run "tests/e2etest-<n>" --e2e --control-plane-group="<group>" --kubeconfig "<kubeconfig>"
# add --public ONLY if the caller chose it
```

## What the run does

1. Creates a control plane `<project>-uptest-<test name>` in the group. The first progress line is `Creating
   development control plane in Spaces`.
2. Crossplane version: `spec.crossplane.version` or `--control-plane-version` if set; otherwise the latest
   version matching the project's constraint (`^v2.0.0-up.0` for a v2 project). `spec.crossplane.autoUpgrade.channel`
   applies here.
3. Pushes the built package to the repository, applies `initResources`, installs the Configuration and waits
   for it, then applies `extraResources` without waiting.
4. Applies the manifests and asserts `defaultConditions` within `timeoutSeconds`.
5. Tears down after every test, pass or fail, unless `spec.skipDelete: true` or `--skip-control-plane-cleanup`.

**Timings:** 30–40 minutes per test was normal in earlier runs of this skill on a Space; not re-measured with
up v0.55.0.

**Known transient:** `Creating: Waiting for control plane API: cannot provision contr...` is a progress
message truncated mid-word (the `up ctp list` MESSAGE column), not a failure. All conditions may still settle
`True`.

## Stuck on a Space

Check the package installed before any managed resource. If the run never got past `Waiting for package to be
ready`, no XR exists and tracing resources is wasted effort:

```bash
up controlplane list                     # the control plane usually reads Available/Healthy regardless
up ctx ../<control-plane-name>           # relative form; `up ctx default/<cp>` is rejected
kubectl get configuration.pkg.crossplane.io
kubectl describe configuration.pkg.crossplane.io <name>
```

A `401 Unauthorized` or `UNAUTHORIZED: authentication required` in the unpack error means the control plane
cannot pull the package that was just pushed: a private repository with no pull credential on that Space
(common when `up profile list` shows the active profile as `disconnected`). Fix `spec.repository` or the
Space's pull secret; retrying the test does not help.

For the troubleshooting brief in [troubleshooting.md](troubleshooting.md), get the test control plane's kubeconfig while it
exists:

```bash
CPCFG=$(mktemp -t kubeconfig-cp.XXXXXX)
up ctx <control-plane-name> -f- > "$CPCFG"   # relative to the current group
```

## Evidence and cleanup

- **The log's `Cleanup summary` line**, quoted.
- **Resource and provider reads taken during the run**, through the control plane's kubeconfig above; the
  control plane is deleted afterwards.
- **No test control plane left behind:** `up controlplane list` shows no `<project>-uptest-<test>` once the run
  has exited, unless the test skips deletion.
- **Leftovers in the cloud**, checked in the provider's API by the names or tags the test used.
