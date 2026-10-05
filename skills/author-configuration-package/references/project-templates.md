# Starting from a language template

`up project init` without `--scratch`: what the wizard offers, what a template gives you, and
how its layout differs from what the generators produce. The `up project init` facts that
hold for `--scratch` too stay in the skill.

---

`up project init <name>` runs a wizard: template (AWS Bucket / Azure Storage / GCP Storage /
Kubernetes WebApp / from scratch) → composition language → test language → AI tooling configs.
Non-interactively: `up project init <name> --template project-template-aws-s3 --language python
[--test-language python]`.

A template gives you a **complete, passing** project — XRD, composition, function, composition
test, E2E test, `examples/providerconfig.yaml` — which is usually a better starting point than
scaffolding from scratch. Know that:

- **The templates are v1.** Do not copy a template's XRD as a starting point for a v2 API;
  write it yourself (`control-plane-project-charter` §5).
- **The language templates emit the *embedded* Python layout** (`functions/<n>/main.py` +
  `requirements.txt`, `from .model.io...`), not the SDK layout that `up function generate`
  produces. Code you add must match what the project already has.
