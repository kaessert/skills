# Where a run lands: local KIND or a Space

Facts shared by every command that creates a control plane: `up project run`, `up test run --e2e`, and
`up project stop` finding one again. The procedures stay in the skills that run them
(verify-configuration, e2e-test-configuration); [`control-plane-project-charter` §9](../../SKILL.md#9-never-create-infrastructure-as-a-side-effect)
holds the never-rules. Facts are from the up v0.55.0 source unless marked *observed*.

---

## Which control plane a run uses

The context decides, not a flag (`internal/ctp`, `EnsureDevControlPlane`):

1. `--local` → a local KIND control plane, whatever the context says.
2. Otherwise, if the current kubeconfig context resolves to a Space at **any** level — Space, group
   or control plane → a control plane in that Space.
3. Otherwise → local KIND, without saying so.

`--control-plane-group` does not select a Space: from a context outside any Space, a run that passes
it still goes local. The first progress line names the result:

```text
Creating local development control plane...          <- local KIND
Creating development control plane in Spaces         <- Space
```

| | Local KIND | Space |
|---|---|---|
| Control plane | kind cluster `up-<project>` (`up project run`) or `<project>-uptest-<test>` (E2E), plus a registry container `<cluster>-registry` | `ControlPlane` of the same name in the group |
| Package | sideloaded into the local registry; nothing is pushed | pushed to `spec.repository`, then installed |
| Repository, `--public`, group | none of them apply | all of them apply (below) |
| Cloud resources | created, through the test's or project's provider credentials | created |

A local result says nothing about the Space, and the reverse.

## Reading the context (`up ctx`)

Bare `up ctx` is the interactive browser; without a terminal it fails with
`could not open a new TTY: open /dev/tty: device not configured`. The non-interactive forms:

| Command | Does |
|---|---|
| `up ctx .` / `up ctx . --short` | print the current context (prose / bare path) |
| `up ctx ../<name>` | move to a sibling: from a control plane to another one in the same group |
| `up ctx ./<name>` | move into a child: from a group to one of its control planes |
| `up ctx <org>/<space>/<group>[/<cp>]` | absolute path; it must start with the profile's root (`<org>`, or `disconnected/<space>`), otherwise `context "…" is not available in the current profile` |
| `up ctx . -f -` | write the current context's kubeconfig to stdout instead of switching |

A path without a leading `.` is absolute: `up ctx <cp>` from a group does not mean "the control plane
in this group".

**Read the shape of `up ctx . --short`, not its first word.** The first segment is the organization
on Upbound Cloud and the literal `disconnected` on a disconnected Space, so matching
`disconnected/` misses every Cloud Space.

| `up ctx . --short` | Context is at | A run without `--local` lands in |
|---|---|---|
| exits non-zero | no Space (an organization, or a non-Upbound context under a Cloud profile) | local KIND |
| 2 segments: `<org>/<space>`, `disconnected/<space>` | a Space | that Space, group from the kubeconfig namespace, else `default` (below) |
| 3 segments: `…/<space>/<group>` | a group | that group |
| 4 segments: `…/<group>/<control-plane>` | a control plane | its group |

Under a **disconnected** profile, a kubeconfig context that is not an Upbound one resolves to the
profile's own Space when its hub is reachable, so `up ctx .` prints `disconnected/<space>` and runs
go there (source, not measured).

## The group (`--control-plane-group`)

On a Space the group is, in order: `--control-plane-group`; the group in the current context; the
kubeconfig namespace; the literal `default`. So a run from a Space-level context creates its control
plane in group `default` — a real control plane in a real group, not a no-op. The `--help` text
("defaults to the group specified in the current context") omits the last two steps.

## `--kubeconfig` is an input

`--kubeconfig` (a global flag, "Override default kubeconfig path") names a file `up` **reads**; it
never writes it. A missing file is rejected at parse time. A file that exists but does not parse
resolves no Space, so the run silently goes local (*observed*: a leftover file holding an error string
turned a Space run into a local one). Write it fresh in this run and check it parses before passing
it:

```bash
KCFG=$(mktemp -t kubeconfig.XXXXXX)
up ctx . -f - > "$KCFG"
kubectl --kubeconfig "$KCFG" config current-context || echo "not a kubeconfig: $KCFG"
```

`up project run` also **rewrites** the current kubeconfig context to the dev control plane it
created, unless `--no-update-kubeconfig`. After a failed run it can point at a different control
plane than the one you are diagnosing (*observed*): run `up ctx .` before believing `kubectl`.

## Repository visibility and `--public`

On a Space, the run pushes the configuration package to `spec.repository` (or `--repository`), and
each embedded function to its own repository beside it. `up` creates a repository only when **all**
of these hold: it does not exist yet, it is on the Upbound registry, and the login is not a robot
token. A repository it creates is **private** unless `--public` is passed. It never changes an
existing repository.

`--public` ("Create new repositories with public visibility") is accepted by `up test run`,
`up project push`, `up project run` and `up project simulate create`.

| Repository | Without `--public` | With `--public` |
|---|---|---|
| does not exist yet | created private: the install cannot pull it | created public: the install can pull it |
| exists, public | pullable | pullable |
| exists, private | not pullable | **still not pullable**: the flag does not flip an existing repository |

**`--public` publishes the user's package.** Anyone can pull what was pushed, and setting the
repository private later does not take back what was already fetched. Treat it as an irreversible
disclosure, chosen only by the user, never as a debugging step and never as a retry after a hang.

`up repository` has its own traps:

- `up repository create <name>` creates a **public** repository unless `--private` is passed — the
  opposite of what a push creates.
- `up repository update <name>` requires both `--private` and `--publish` as booleans. `--publish`
  is the Marketplace listing policy, not visibility, and the policy string `up repository list`
  prints in its `PUBLISH POLICY` column is not accepted. It asks for confirmation unless `--force`.

## A run stuck on `Waiting for package to be ready`

On a Space, the push and the install are two halves of one run, minutes apart, and the control plane
the run creates gets no pull credential for a private repository. The install then fails to unpack
what the push just wrote, the run waits until its timeout (`up project run` default `--timeout 5m`),
and all it prints is:

```text
✗ Waiting for package to be ready
up: error: context deadline exceeded
```

That names neither half. The real error is on the `Configuration`, read while the control plane
exists:

```bash
up repository get <repository>                     # predicts it: private, and no pull secret on the Space
up controlplane list                                # usually Available/Healthy regardless
up ctx ./<control-plane>                            # from the group context (../<cp> from a sibling)
kubectl get configuration.pkg.crossplane.io
kubectl describe configuration.pkg.crossplane.io <name>
```

| `describe` shows | Cause |
|---|---|
| `cannot unpack package: … 401 Unauthorized … UNAUTHORIZED: authentication required` | private repository, and no pull credential for it on that control plane. Retrying changes nothing |
| `cannot resolve … not found` | pushed to a different repository than the one being installed: reconcile `spec.repository` |
| provider revision unhealthy | a provider still installing, or a bad version constraint: `kubectl get providers.pkg.crossplane.io` and its revisions |

The ways out of the first row are the user's choice: pull access on the Space (an existing pull
secret or `ImageConfig`), a public repository (`--public`, above), or `--local`, which pushes nothing
and so cannot hit it — but is not the Space they chose. `--local` is never a silent fallback.

## Teardown and leftovers

- **E2E** tears its control plane down after every test, pass or fail, unless `spec.skipDelete: true`
  or `--skip-control-plane-cleanup`. If control-plane creation fails partway, nothing is handed to
  teardown, so a half-built kind cluster or registry container can stay behind (source, not
  observed).
- **`up project run`** leaves its control plane running. `up project stop` from the project root
  removes it — for a local one, the kind cluster, its registry container and the registry directory.
  It finds the control plane the same way a run does, so pass `--local` when the context is a Space;
  it asks for confirmation unless `--force`.
- **`kind delete cluster --name up-<project>` leaves `up-<project>-registry` running** (*observed*).
  Remove it with `docker rm -f -v up-<project>-registry`.
