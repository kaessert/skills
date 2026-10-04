# go-templating

Go templates with Sprig, used two ways in an `up` project: as **composition functions**
(`function-go-templating`) and as **tests**. They share a syntax and nothing else — different inputs, different
function sets — so do not carry idioms from one to the other unexamined.

The language-agnostic rules are in [`control-plane-project-charter`](../../SKILL.md). Read the charter first.

| | |
|---|---|
| Scaffold a function | `up function generate <n> --language go-templating` → `functions/<n>/00-prelude.yaml.gotmpl`, `01-compose.yaml.gotmpl` |
| Scaffold a test | `up test generate <n> --language go-templating` → `tests/test-<n>/test.yaml.gotmpl` (add `--e2e`) |
| Run tests | `up test run tests/test-<n>` |

## Functions

This reference does not yet cover writing go-templating **functions** beyond the scaffold. The function's own
template functions (`getCompositeResource`, `setResourceNameAnnotation`, `getComposedResource`, …) are
documented in the [function-go-templating README](https://github.com/crossplane-contrib/function-go-templating#using-this-function).
Everything the charter says about v2 managed resources (§5) and test-first development (§3) applies.

## Tests

### How `up` runs a go-templating test

Verified against `up` v0.55.0:

- A test directory is go-templating when **every** file in it ends in `.gotmpl` or `.tmpl`. One `README.md`
  next to the template and `up test run` stops with `No test files found`.
- All files in the directory are concatenated (lexical order, `---` between them) and rendered **once** with Go
  `text/template` plus [Sprig](https://masterminds.github.io/sprig/) — in-process, on your machine.
- **There is no input**: `.` is nil. The function-side helpers (`getCompositeResource` and friends) do not exist
  here, and neither do Helm's (`required`, `toYaml`, `include`): calling one fails with `function "…" not
  defined`. Sprig's `fail`, `hasKey`, `dict`, `list`, `toJson` are what you have.
- The output must be `items:` with a list of `CompositionTest` objects — the same object model as YAML tests
  ([`yaml.md`](yaml.md)).

What templating buys over plain YAML is a **test matrix**: one test body, ranged over a list of cases, with
per-case conditional expectations. If a test has no matrix, plain YAML is clearer — but match the language the
project's other tests use.

### Composition test template (`tests/test-<n>/test.yaml.gotmpl`)

Two cases of one input branch, each with an absence guard on the composite (`resourceRefs` is a list, and
lists match exactly), and a guard that turns a misspelt case key into a generation error:

```yaml
# code: language=yaml
# yaml-language-server: $schema=../../.up/json/models/test.schema.json
{{- $comp := "apis/buckets/composition.yaml" }}
{{- $xrd := "apis/buckets/definition.yaml" }}
{{- /* A misspelt key renders "<no value>" silently. "need" turns it into a generation error. */}}
{{- define "need" }}{{ range .keys }}{{ if not (hasKey $.case .) }}{{ fail (printf "test case %v: missing key %q" $.case . ) }}{{ end }}{{ end }}{{ end }}
{{- $cases := list
      (dict "name" "versioning-off" "versioning" false)
      (dict "name" "versioning-on" "versioning" true) }}
items:
{{- range $case := $cases }}
{{- template "need" (dict "case" $case "keys" (list "name" "versioning")) }}
- apiVersion: meta.dev.upbound.io/v1alpha1
  kind: CompositionTest
  metadata:
    name: tmpl-{{ $case.name }}
  spec:
    compositionPath: {{ $comp }}
    xrdPath: {{ $xrd }}
    timeoutSeconds: 120
    validate: false
    xr:
      apiVersion: demo.example.org/v1alpha1
      kind: Bucket
      metadata:
        name: example
        namespace: default
      spec:
        region: eu-central-1
        versioning: {{ $case.versioning }}
    assertResources:
    # The composite's resourceRefs is a list, and lists match exactly: a surplus composed resource fails here.
    # Names copied from render.log (renders are deterministic).
    - apiVersion: demo.example.org/v1alpha1
      kind: Bucket
      metadata:
        name: example
      spec:
        crossplane:
          resourceRefs:
{{- if $case.versioning }}
          - apiVersion: s3.aws.m.upbound.io/v1beta1
            kind: BucketVersioning
            name: example-41ed1f34c483
{{- end }}
          - apiVersion: s3.aws.m.upbound.io/v1beta1
            kind: Bucket
            name: example-963082b09556
    - apiVersion: s3.aws.m.upbound.io/v1beta1
      kind: Bucket
      metadata:
        annotations:
          crossplane.io/composition-resource-name: bucket
      spec:
        forProvider:
          region: eu-central-1
{{- if $case.versioning }}
    - apiVersion: s3.aws.m.upbound.io/v1beta1
      kind: BucketVersioning
      metadata:
        annotations:
          crossplane.io/composition-resource-name: versioning
      spec:
        forProvider:
          versioningConfiguration:
            status: Enabled
{{- end }}
{{- end }}
```

What the suite must contain beyond this — a minimal XR, one test per observed-state branch, every status field
asserted on the composite — is in [`python/tests.md` § Coverage](python/tests.md#coverage-what-the-suite-must-contain),
which is language-agnostic. Observed-state tests add `observedResources` to a case exactly as in [`yaml.md`](yaml.md).

### Failure modes (reproduced)

| What you do | What happens |
|---|---|
| Misspell a case key (`$case.versionin`) | **silently renders `<no value>`** into the manifest. In the reproduction the XR got `versioning: <no value>`, the function read it as false, and the test passed for the wrong reason. Guard keys with `hasKey` + `fail` as above, and never let `<no value>` reach a manifest |
| Template syntax error / unknown function | the **whole run** fails at generation (`failed to parse templates`) |
| A non-template file in the test directory | the run fails: `No test files found` |
| Expectation with the wrong shape (a list where the API has an object) | **passes** if the function writes the same wrong shape: assertions compare test against render, never against the CRD. Check field shapes in the provider's CRD (or the generated models) before writing them into a template |
| Expectation indented one level off | the assertion silently moves to another field or object; read the rendered manifest back if a test passes that should not |

**Indentation is the other trap.** A value that is itself a structure is safest as `{{ toJson $v }}` on one
line (JSON is valid YAML), and `{{-` / `-}}` trimming decides whether a block lands where you think. When a
change to a template makes a test pass or fail unexpectedly, render the template on its own and read the YAML
before changing the expectation.

### E2E tests

`--e2e` scaffolds the same shape around an `E2ETest`. Run-scoped values come from Sprig's `env` (the template
renders locally, inside `up`): `{{ env "UP_RUN_ID" }}`. Guard each with `{{ if not (env "X") }}{{ fail "X unset" }}{{ end }}`
so a missing value fails before a control plane is created. The rules in
`e2e-test-configuration` apply.
