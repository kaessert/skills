# The project's ProviderConfig (Phase 8)

Why every project needs one, the default manifest, the two things to confirm rather than
guess, and the credential prerequisite for the README. The skill's Phase 8 states the rule.

---

A `--scratch` project has no `examples/providerconfig.yaml`. Only the *language templates*
ship one. So a scratch project builds, its tests pass, it installs on a control plane — and
every managed resource it composes sits unauthenticated, because Crossplane v2 defaults an
omitted `providerConfigRef` to `{kind: ClusterProviderConfig, name: default}` and **nothing
in the project creates that object**.

The failure mode is a managed resource with **no conditions and no events at all** — byte
for byte the same symptom as the `providerConfigRef` trap in the composition skills, so you
cannot tell the two causes apart from the cluster. Nothing in the workflow prompts for it,
and no check anywhere verifies that the ProviderConfig a composition implicitly depends on
exists.

Create it in Phase 8, matching the provider family you added in Phase 4. The default is a
`ClusterProviderConfig` named `default`, below. When the project's spec or API names another
config — a namespaced `ProviderConfig` in the XR's namespace, a non-`default` name — create
that one instead, so this example and the compositions' `providerConfigRef` name the same
object (`control-plane-project-charter` §5: defaults the project may override).

```yaml
# examples/providerconfig.yaml
apiVersion: aws.m.upbound.io/v1beta1     # family group, NOT kms.aws.m.upbound.io
kind: ClusterProviderConfig
metadata:
  name: default                          # must be "default" to match the v2 default ref
spec:
  credentials:
    source: Secret                       # or IRSA / WebIdentity / PodIdentity / Upbound
    secretRef:
      namespace: crossplane-system
      name: aws-creds
      key: creds
```

Two things worth confirming rather than guessing:

- **The apiVersion is the family group** (`aws.m.upbound.io/v1beta1`), not a service group.
  This is a different group shape from every other resource in the family, which is exactly
  the kind of thing that gets guessed wrong. Confirm it from the generated tree, where the
  module path *is* the reversed group:
  `python3 <author-composition>/scripts/probe_project.py --project <root> ClusterProviderConfig`
  → `models.io.upbound.m.aws.clusterproviderconfig` = `aws.m.upbound.io`. (A `grep` for
  `Literal` in that module shows the credential `source` values, not the apiVersion.)
- **`ClusterProviderConfig` (cluster-scoped) vs `ProviderConfig` (namespaced)** — use the
  cluster-scoped one named `default` unless the project's spec or API calls for per-namespace
  credentials, and remember the generated E2E test creates a `ClusterProviderConfig` too.

Also add the credential secret to the README's prerequisites, since it is not part of the
package:

```bash
kubectl -n crossplane-system create secret generic aws-creds \
  --from-file=creds="${AWS_SHARED_CREDENTIALS_FILE:-$HOME/.aws/credentials}"
kubectl apply -f examples/providerconfig.yaml
```
