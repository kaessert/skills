# Running E2E on a local kind control plane (`--local`)

Read before running `up test run --e2e --local`. [SKILL.md](../SKILL.md) has what both targets share:
preconditions, the run idiom, stuck detection and the report. Facts below are from the up v0.55.0 source and
runs, and could change between versions.

## Preconditions

- **Docker must be reachable** (`docker info` exits 0). `up` creates the cluster itself through the kind
  library; the `kind` CLI is only needed to look inside or clean up.
- **List `kind get clusters` and `docker ps -a` before the run, and keep the lists.** Anything already there
  is not this run's, even with this project's `<project>-uptest-` name (SKILL.md, Never): report it.
- **Don't run `up ctx`, or check a repository, `--public` or the group.** `--local` ignores the context and
  sideloads the package instead of pushing it (`control-plane-project-charter` `charter/targets.md`), so a failing
  `up ctx . --short` is not a failed precondition here.
- **Credentials are a static Secret** in `extraResources`: `credentials.source: Secret` plus
  `secretRef: {namespace, name, key}`, built from a `UP_*` variable. `source: Upbound` web identity does not work
  on kind. The shapes, the AWS credentials-file format and how to build it in memory are in author-tests'
  `e2e.md` reference.
- **Run under the default umask (`022`), never `umask 077`.** `up` writes the local registry's TLS certificate
  and key (`/tmp/up-local-registry/<cluster>/.certs/`) with your umask, and the registry container runs as a
  non-root user. Under `umask 077` it can't read them and exits, and the run waits at `Waiting for package to
  be ready` until `context deadline exceeded`, about 10 min later (observed with up v0.55.0). `docker logs
  <cluster>-registry` shows `open /registry-data/.certs/tls.crt: permission denied`. To protect a credentials
  file, `chmod 600` that file; better, write no file at all.

## Target flags

```bash
up test run "tests/e2etest-<n>" --e2e --local
```

inside the run idiom in SKILL.md Phase 4. Optional:

- `--control-plane-version <version>` pins UXP (otherwise `spec.crossplane.version`, otherwise the latest
  stable UXP).
- `--skip-control-plane-cleanup` keeps the cluster after the test. Then deleting it, and checking the cloud,
  is yours to do or to report.

## What the run does

1. Creates a kind cluster whose name starts `<project>-uptest-` (shortened: below) on the node image
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

The cluster exists only during the run. Its name is `<project>-uptest-<test>` shortened: observed with up
v0.55.0, a 56-character name became its first 49 characters, ending in `-`. Don't derive it, and don't wait on
a word such as `cluster`: find it with `kind get clusters`, the entry starting `<project>-uptest-` that was not
in your list from before the run. The registry container is `<cluster>-registry`.

```bash
kind get clusters                                   # the new entry starting <project>-uptest-
KCFG=$(mktemp -t kubeconfig-e2e.XXXXXX)
kind get kubeconfig --name <cluster> > "$KCFG"
kubectl --kubeconfig "$KCFG" get managed -A
```

Use `kind get kubeconfig`, not a kubeconfig `up` leaves in `/tmp`: observed with up v0.55.0,
`/tmp/up-*.kubeconfig` was empty (0 bytes), and the test's own `/tmp/<test><random>/kubeconfig.yaml` was gone by
the next read.

If the run never got past the package install, check that first, before tracing any managed resource:
`docker logs <cluster>-registry` (the umask precondition), then `kubectl get pkgrev -o wide` and `kubectl
describe configuration`. Then use the brief in [troubleshooting.md](troubleshooting.md).

**A status field or condition.** An `E2ETest` can't assert one (author-tests' `e2e.md` reference). To read one,
take it inside the one run you need anyway, and **watch rather than poll**: the delete starts about a second
after the assert sees `Ready` (observed with up v0.55.0), so a read every few seconds misses the one moment the
status is complete. Wait, bounded, until the XR exists, then watch that one object (`get managed -w` fails:
`managed` is a category), bounded too:

```bash
for _ in $(seq 1 60); do                            # until the XR exists, or the run ends
  grep -q '^EXIT=' /tmp/e2e-<n>.log && break
  kind get kubeconfig --name <cluster> > "$KCFG" 2>/dev/null &&
    kubectl --kubeconfig "$KCFG" --request-timeout=5s get <xr-kind> <xr-name> -n <namespace> >/dev/null 2>&1 &&
    break
  sleep 5
done
timeout 600 kubectl --kubeconfig "$KCFG" get <xr-kind> <xr-name> -n <namespace> -w \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status} {.status}{"\n"}' >> /tmp/e2e-<n>-status.txt 2>&1
grep '^True ' /tmp/e2e-<n>-status.txt | tail -1      # the last read taken while Ready
```

The watch prints one line per change and ends with the cluster or at its timeout; size that to one command's
timeout, and if it ends before `EXIT=` is in the log, start it again (it prints the current state first). Give
every other `kubectl` call `--request-timeout`: one without it hung for 150 s once the cluster was gone.

Quote it as **"read-back, not asserted"**, with its `Ready` condition: a read while `Ready` is `False` can be
partial. It is not a provider read. Never re-run a green e2e only to read status: if the window was missed,
report "not read back".

## Evidence and cleanup

After the run the cluster is gone, so `kubectl get managed` afterwards is impossible. The evidence is:

- **The log's `Cleanup summary: N deleted, 0 remaining` line**, quoted.
- **A provider read taken during the run**, quoted. Without one, the report says "not verified at the
  provider".
- **Leftovers, checked in the provider's API** by the names or tags the test used, not in Kubernetes. Don't
  assume a provider CLI exists: `command -v <cli>` first, then use whatever is installed (observed: no `aws`
  CLI, but an SDK such as boto3). If neither is available, say the leftovers were not checked.
- **`kind get clusters`** lists no `<project>-uptest-*` cluster beyond those in your list from before the run.

## Leaks

- **A half-built cluster can leak.** If control-plane creation fails partway, `up` never hands it to teardown
  (from the v0.55.0 source, not observed), so a kind cluster or registry container can stay behind. A run
  killed mid-install by a command timeout left both behind (observed). After either, run `kind get clusters`
  and `docker ps -a`.
- **Remove only what this run created:** the cluster `kind get clusters` lists for this run, with
  `kind delete cluster --name <cluster>`. Anything else on the machine is the user's.
- **`kind delete cluster` leaves the registry container behind** (`charter/targets.md`). If you delete a
  leaked cluster by hand, check `docker ps -a` for this run's registry container (`upbound/olareg`) and remove it
  with `docker rm -f -v <container>`.
