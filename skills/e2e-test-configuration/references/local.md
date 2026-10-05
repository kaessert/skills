# Running E2E on a local kind control plane (`--local`)

Read before running `up test run --e2e --local`. [SKILL.md](../SKILL.md) has what both targets share:
preconditions, the run idiom, stuck detection and the report. Facts below are from the up v0.55.0 source and
runs, and could change between versions.

## Preconditions

- **Docker must be reachable** (`docker info` exits 0). `up` creates the cluster itself through the kind
  library; the `kind` CLI is only needed to look inside or clean up.
- **No `up ctx`, repository, `--public` or group check.** `--local` ignores the context and sideloads the
  package instead of pushing it (`control-plane-project-charter` `charter/targets.md`), so a failing
  `up ctx . --short` is not a failed precondition here.
- **Credentials are a static Secret** in `extraResources`: `credentials.source: Secret` plus
  `secretRef: {namespace, name, key}`, built from a `UP_*` variable. `source: Upbound` web identity does not work
  on kind. The shapes, and the AWS credentials-file format, are in author-tests' `e2e.md` reference.

## Target flags

```bash
up test run "tests/e2etest-<n>" --e2e --local
```

inside the run idiom in SKILL.md Step 4. Optional:

- `--control-plane-version <version>` pins UXP (otherwise `spec.crossplane.version`, otherwise the latest
  stable UXP).
- `--skip-control-plane-cleanup` keeps the cluster after the test. Then deleting it, and checking the cloud,
  is yours to do or to report.

## What the run does

1. Creates a kind cluster named `<project>-uptest-<test name>` (truncated to 63 characters) on the node image
   `xpkg.upbound.io/upbound/kind-node`: Kubernetes v1.37.0 with up v0.55.0. It also starts a local OCI registry
   container (`upbound/olareg`).
2. Installs UXP: `spec.crossplane.version` or `--control-plane-version` if set, otherwise **the latest stable
   UXP**. `spec.crossplane.autoUpgrade.channel` is ignored on this path.
3. Sideloads the built package into the local registry.
4. Applies `initResources`, **then** installs the Configuration and waits for its packages, **then** applies
   `extraResources` (Namespace, Secret, ProviderConfig) without waiting for them.
5. Applies the manifests and asserts `defaultConditions` within `timeoutSeconds`.
6. **Tears down after every test, pass or fail:** the test's resources, then the kind cluster, the registry and
   its directory. Skipped with `spec.skipDelete: true` or `--skip-control-plane-cleanup`.

The first progress line is `Creating local development control plane...`.

## Timings (observed with up v0.55.0)

| What | Observed |
|---|---|
| Whole run, a small VPC network (cleanup summaries counted 2–7 resources) | ~5–10 min |
| `chainsaw/apply` step | 79–258 s |
| `timeoutSeconds` that test set | 1200 (the Go scaffold writes 300) |

Size `timeoutSeconds` to what you provision (author-tests' `e2e.md` reference); an EKS cluster needs far more.

## Reaching the cluster while it runs

The cluster exists only during the run. For a stuck investigation or a provider-state read:

```bash
kind get clusters                                   # look for <project>-uptest-<test>
KCFG=$(mktemp -t kubeconfig-e2e.XXXXXX)
kind get kubeconfig --name <cluster> > "$KCFG"
kubectl --kubeconfig "$KCFG" get managed -A
```

`up` also writes a transient `/tmp/up-*.kubeconfig` during the run (observed); it goes with the cluster. If
the run never got past the package install, check that first (`kubectl get pkgrev -o wide`, `kubectl describe
configuration`) before tracing any managed resource, then use the brief in [troubleshooting.md](troubleshooting.md).

## Evidence and cleanup

After the run the cluster is gone, so `kubectl get managed` afterwards is impossible. The evidence is:

- **The log's `Cleanup summary: N deleted, 0 remaining` line**, quoted.
- **A provider read taken during the run**, quoted. Without one, the report says "not verified at the
  provider".
- **Leftovers, checked in the provider's API** by the names or tags the test used, not in Kubernetes. Don't
  assume a provider CLI exists: `command -v <cli>` first, then use whatever is installed (observed: no `aws`
  CLI, but an SDK such as boto3). If neither is available, say the leftovers were not checked.
- **`kind get clusters`** lists no `<project>-uptest-*` cluster.

## Leaks

- **A half-built cluster can leak.** If control-plane creation fails partway, `up` never hands it to teardown
  (from the v0.55.0 source, not observed), so a kind cluster or registry container can stay behind. After a
  failure at `Creating local development control plane`, run `kind get clusters` and `docker ps -a`.
- **Remove only what this run created:** the cluster named `<project>-uptest-<test>`, with
  `kind delete cluster --name <cluster>`. Anything else on the machine is the user's.
- **`kind delete cluster` leaves the registry container behind** (`charter/targets.md`). If you delete a
  leaked cluster by hand, check `docker ps -a` for this run's registry container (`upbound/olareg`) and remove it
  with `docker rm -f -v <container>`.
