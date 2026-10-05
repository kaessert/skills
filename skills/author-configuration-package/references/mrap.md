# Activating managed resources: ManagedResourceActivationPolicy (MRAP)

What an MRAP manifest looks like, where it must sit, what `up project build` does and does not
check, how to see its effect, and the `up dep add --api` tag. The skill's MRAP line states the
rule.

---

`kind: ManagedResourceActivationPolicy`, `apiVersion: apiextensions.crossplane.io/v1alpha1`,
with `spec.activate:` listing MRD names (`vpcs.ec2.aws.m.upbound.io`). Observed with up v0.55.0:

- **The manifest must sit under `apis/`** (any subdirectory, e.g. beside the XRD). Anywhere
  else (`policies/`, `examples/`) it is silently left out of the package.
- **`up project build` barely validates it.** A field typo ships an MRAP that activates
  nothing; a wrong `kind` or `apiVersion` is silently dropped; only a wrong value type fails.
  `activate` entries are not checked against any CRD. Verify an MRAP on a control plane.
- **The default policy hides its effect.** UXP's default MRAP activates `*`. To see yours, start
  the control plane with the Crossplane Helm value `provider.defaultActivations: []` (e.g.
  `up project run --local --helm-values <file>`; charter §9 decides whether you may) and check
  that exactly the MRDs you listed are Active.
- **`up dep add --api crossplane:<tag>` only adds MRAP models** for Go/Python/KCL; the build
  does not need it. The tag must be a UXP version in both `upbound/crossplane` and
  `upbound/controller-manager`: `v2.1.4-up.1` worked; `v2.1.0`, `v2.1.3` and `v2.1.3-up.1`
  returned 404. Look the tag up; don't guess.
