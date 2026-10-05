# Running the project on a dev control plane

`up project run`, step by step: which control plane your context gives you, the Space
pre-flight, the choice you hand back when a Space cannot pull, confirming the run reconciled,
and diagnosing a run that hangs on `Waiting for package to be ready`. The skill's Phase 5
holds the rules; this is the procedure behind them.

---

## The steps

**1. Detect what your context points at.** The context, *not* a flag, decides which kind of
dev control plane you get. One command settles it:

```bash
up ctx . --short | awk -F/ '{print NF" segments"}'   # 4 => you are on a Space
up ctp list >/dev/null 2>&1 && echo "Space reachable"
```

> **Bare `up ctx` cannot work for an agent.** With no terminal it fails with `could not open a new TTY: open /dev/tty: device not configured` and tells you nothing about the flag that would have worked. The non-interactive forms are `up ctx .` (current context) and `up ctx . --short` (bare path, no prose). Relative navigation (`up ctx ../<name>`) also works without a TTY.

**Test the shape, not the first word.** A Space context has **four** `/`-separated segments —
`<profile-type-or-org>/<space>/<group>/<controlplane>`. The first segment is your *profile
type*: it reads `disconnected` on a disconnected Space and your **org/domain** on Upbound
Cloud. So matching the literal string `disconnected/` is a false negative on every Upbound
Cloud Space — the agent concludes "not a Space, local is the default", runs `up project run`
with no flag, gets the **cloud** path anyway, and wedges exactly as before with a different
explanation. Four segments (or `up ctp list` succeeding) means cloud path, whatever the first
segment says. Fewer segments, or `up ctx .` erroring, means local KIND is the default.

**2. Not on a Space?** Local is already the default. Just run it:

```bash
up project run --timeout=20m     # the --timeout default is 5m, short for a first run
```

**3. On a Space? Pre-flight before you spend ten minutes.** On the cloud path
`up project run` pushes to a **private** repository and then installs onto a control plane
it gives no pull credential — two halves of one invocation that do not fit together. It
wedges on `Waiting for package to be ready` and exits `context deadline exceeded`, naming
neither half. Catch it in seconds instead:

```bash
up repository get <project-name>            # PUBLIC=false and no pull secret => it will wedge
kubectl get imageconfigs.pkg.crossplane.io
kubectl -n crossplane-system get secrets | grep -i pull
```

If it *can* pull, run it on the Space — that is the environment they chose.

**4. If the pre-flight says it will wedge, hand the decision back. Do not decide it
yourself.** In particular do **not** "helpfully" fall back to `--local`: they connected to
that Space on purpose, and a local KIND cluster is a *different environment*, not a
transparent substitute. Put the choice to the user if you are interactive (the skill's mode line), and otherwise **report
these three options and their consequences to your caller and stop** — do not pick one.

| Option | Command | What it costs them |
|---|---|---|
| **A. Cloud control plane, with pull access** | `up project run --timeout=20m`, once the control plane can pull | Nothing, if the repo is pullable or they can point you at an existing pull secret / `ImageConfig`. **Ask where it is rather than assuming.** The only option that tests what they actually connected to |
| **B. Publish the repository** | `up project run --public --timeout=20m` | `--public` means *"create new repositories with public visibility"* — it **permanently publishes their package**. A disclosure decision, never made on their behalf |
| **C. Local KIND control plane** | `up project run --local --timeout=20m` | Side-loads, so the pull failure is unreachable, and it still creates real cloud resources through their provider credentials — a genuine end-to-end test. But it is *not* the Space they were pointed at, and Space-specific behaviour goes uncovered |

**5. Do not pipe the run into `tail`/`head`.** That buffers everything until the process
exits, so a run that is progressing normally looks like a hang and gets killed. Let it
stream, or `tee` it to a file.

**6. If it wedges anyway**, read *"When a run hangs on Waiting for package to be ready"*
below. Do not retry blindly — the cause is usually permanent and another attempt costs
another ~10 minutes.

**7. Confirm it actually reconciled**, rather than trusting the exit code:

```bash
kubectl get <xr-kind> -A
kubectl describe <xr-kind> <name> -n <ns>    # conditions AND events
```

A composed resource with **no conditions and no events at all** means no controller has
reconciled it yet. That is a symptom with several causes, so check it first but do not stop
there:

| Also produces silence | How to tell |
|---|---|
| `providerConfigRef` naming an object nothing created, or a missing `ClusterProviderConfig` | `kubectl get clusterproviderconfig,providerconfig -A` — is the referenced object there? |
| The provider package is not installed or not healthy | `kubectl get providers.pkg.crossplane.io` — `INSTALLED` and `HEALTHY` both `True`? |
| The provider pod is crashing or not yet running | `kubectl get pods -n crossplane-system`, then its logs |
| The MR's CRD is not established, so nothing watches the kind | `kubectl get crd <plural>.<group>` |

Only the first is peculiar to this plugin's guidance, and it is the one composition tests
cannot catch — which is why it is listed first, not why it is the answer.

**8. Read the effect back from the provider, not from your own input.** `Ready=True` is
Crossplane's report that it finished reconciling; it is not proof the provider holds the
configuration you meant. Drift, silently-ignored fields, and values the provider normalised
all survive `Ready=True`. Before teardown, run the provider's own read for at least the
field the change was about, and quote it:

```bash
aws s3api get-bucket-lifecycle-configuration --bucket <name>
az <service> show -n <name> -g <rg>
gcloud <service> describe <name>
```

Reading values back off the XR, the composed resource's `spec`, or the manifest you applied
proves only that your input round-tripped. If you did not run a provider read, say
"reconciled; not independently verified at the provider" rather than "verified".

---

## When a run hangs on "Waiting for package to be ready"

`up project run` (and cloud E2E runs) can sit on `Waiting for package to be ready` and then fail
with nothing but:

```text
✗ Waiting for package to be ready
up: error: context deadline exceeded
```

That message names no control plane and no package. **Do not retry blindly** — the cause is
usually permanent, and a second run wastes another ~10 minutes. Diagnose it:

```bash
up controlplane list                 # dev CP is named up-<project>; it will usually read Available/Healthy
up ctx ../up-<project>               # relative path from a sibling CP context
kubectl get configuration.pkg.crossplane.io
kubectl describe configuration.pkg.crossplane.io <project>   # <- the real error is here
```

### Prevent it: choose the right dev control plane

`up project run` does two things in one invocation, minutes apart: it **pushes** the
package to a registry, then **installs** it onto a control plane. On a cloud dev control
plane the push creates a **private** repository and the install is given no pull
credential, so the second half fails on what the first half wrote — and the error names
neither half.

Which kind of control plane you get is decided by your current context, not by a flag:

> Cloud dev control planes are used by default when the current `up` context is an Upbound
> Cloud Space. Local dev control planes are used by default otherwise, and can be
> explicitly requested with `--local`.

**`--local` cannot hit this.** It runs in a KIND cluster and serves images from a local
registry path, so there is no remote push, no repository, and no visibility decision at
all — the 401 class cannot occur. It still creates real cloud resources through your
provider credentials:

```bash
up project run --local --timeout=20m
```

The default `--timeout` is `5m`, which is short for a first run that has to pull providers.

**If you are on a Space and hit the 401**, do not switch targets yourself: put the three
options of step 4 to the user, or report them to your caller. `--local` is one of
them, and it is not the Space they connected to. Never reach for `--public` as a
workaround: it means *"create new repositories with public visibility"* — it permanently
publishes the user's package to a public repository. That is the user's decision to make,
not a debugging step. Use it only when they have explicitly asked for a public repository.

Retrofitting visibility afterwards is its own trap: `up repository update <name>` requires
an unrelated `--publish` flag, rejects the value `up repository get` prints for it, and has
no `--yes`, so it needs a TTY.

Note `up ctx default/up-<project>` is rejected with *"not available in the current profile"*; the
relative form (`up ctx ../up-<project>`) is what works from a sibling control-plane context.

**Check you are looking at the right cluster first.** A failed `up project run` may leave
kubeconfig pointed at a *different* control plane than the one it created, so `kubectl
describe` will happily describe a healthy unrelated package and send you chasing a
non-existent problem. Confirm with `up ctx .` before believing anything you read.

The control plane being `Available`/`Healthy` says nothing about the package. Read the
Configuration's conditions and events. Causes seen in practice:

| `describe` shows | Cause | Fix |
|---|---|---|
| `cannot unpack package: ... 401 Unauthorized ... UNAUTHORIZED: authentication required` | the control plane can't **pull** the package `up project run` just **pushed** — it pushes to a **private** repository by default and gives the control plane it created no pull credential (common on `disconnected` Spaces; check `up profile list`) | Hand back the choice of step 4: pull access for the Space, `--public`, or `--local` (KIND + local registry, so nothing is pushed and the failure class cannot occur). Do *not* use `--public` to work around it — that permanently publishes the package. See above |
| `cannot resolve ... not found` | pushed to a different repo than the CP is installing | reconcile `spec.repository` with the installed package reference |
| provider revision unhealthy | provider still installing, or a bad version constraint | check `kubectl get provider.pkg.crossplane.io` and its revisions |

Report the underlying condition message to the user — not "the run timed out".
