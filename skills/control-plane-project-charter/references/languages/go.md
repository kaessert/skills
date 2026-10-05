# Go

Everything Go-specific for a control-plane project: composition functions **and** tests.

The language-agnostic rules — the TDD loop, what a v2 managed resource needs, what a green
run proves, reporting discipline — are in [`control-plane-project-charter`](../../SKILL.md) and are
**not** repeated here. Read the charter first; this file only tells you how Go expresses it.

| | |
|---|---|
| Scaffold a function | `up function generate <n> <composition-path> --language go` — then read [`go/functions.md`](go/functions.md): the generated `fn_test.go` tests nothing, and the generated condition targets a claim |
| Scaffold a test | `up test generate <n> --language go` (add `--e2e`) — then read [`go/tests.md`](go/tests.md) |
| Models | `.up/go/models`, written by `up project build`. `.up/` is gitignored, so on a fresh clone run `up dep update-cache`, then `up project build` |
| Fast tier | `go test ./...` in `functions/<n>/` — calls `RunFunction` directly, about a second, no project build |
| Run a test | `up test run tests/test-<n>` runs `go run .` with the test dir as CWD; the program must print `items: [<CompositionTest>…]`. `items: []` is zero tests, and a run with zero tests prints `No test files found` and exits 0 — nothing ran |
| Compile | `go vet ./...` or `go build -o /dev/null ./...` — plain `go build ./...` in a single-package module (every generated function) writes the executable into the function directory, and it ends up committed |
| Before committing | `gofmt -l .` (prints nothing), `go vet ./...`, `go mod tidy` in every function and test module |

## Where everything is

| File | What is in it |
|---|---|
| [`go/functions.md`](go/functions.md) | the scaffold and what to change in it, the function-sdk-go v0.5 calls, a function template, a unit-test template, failure modes |
| [`go/tests.md`](go/tests.md) | how `up` runs a Go test, a composition-test template that tests the function template, failure modes |

---

# Part 1 — Layout

| | Detected by | What is in it |
|---|---|---|
| Function | `functions/<n>/*.go` | its own module, `package main`: `main.go` (the gRPC server, leave it), `fn.go` (`RunFunction`), `fn_test.go` |
| Test | `tests/<t>/go.mod` | its own module, `package main`: `main.go` prints the tests as YAML |

Every function and every test directory is a separate Go module, so run `go` commands from inside it.

# Part 2 — Imports and models

**The import path is the API group reversed, then the version**, under `dev.upbound.io/models`:

| What | API group → import |
|---|---|
| Namespaced managed resource (v2) | `ec2.aws.m.upbound.io/v1beta1` → `dev.upbound.io/models/io/upbound/m/aws/ec2/v1beta1`, i.e. `…/io/upbound/m/<provider>/<service>/<version>` |
| Cluster-scoped managed resource (v1 projects only) | `ec2.aws.upbound.io/v1beta1` → `…/io/upbound/aws/ec2/v1beta1` |
| Your own XR | `demo.example.org/v1alpha1` → `…/org/example/demo/v1alpha1` |
| Test objects (`CompositionTest`, `E2ETest`) | `…/io/upbound/dev/meta/v1alpha1` |
| `ObjectMeta` | `…/io/k8s/meta/v1` |

**The non-`.m.` tree sits right beside the `.m.` one**, with the same file names:
`.up/go/models/io/upbound/aws/ec2/v1beta1/vpc.go` next to `.up/go/models/io/upbound/m/aws/ec2/v1beta1/vpc.go`.
A search for a Kind returns both. In a v2 project import the `m/` path; the other one is the same mistake as in
any language (charter §5: `.m.` groups only).

**Inside a model file**, each Kind is a struct (`Bucket`, `BucketSpec`, `BucketSpecForProvider`), and every
field is a pointer with `omitempty`. Read field names from the file rather than guessing them:

```bash
grep -n 'type BucketSpecForProvider struct' -A 60 .up/go/models/io/upbound/m/aws/s3/v1beta1/bucket.go
```

The `apiVersion` and `kind` constants are generated, and their spelling varies **per kind within one tree**:
v0.55.0 writes `VPCApiVersionec2AwsMUpboundIoV1Beta1` next to `InternetGatewayAPIVersionec2AwsMUpboundIoV1Beta1`.
Copy each from the `const (` block at the top of its own file; a grep for one spelling misses the other. They
are **typed** (`VPCApiVersion`, not `string`), so pass `string(c)` where a `string` is expected.

### `go.mod`: the models `replace`

`dev.upbound.io/models` cannot be fetched; it exists only as `.up/go/models`. A module reaches it through a
`replace`, and both scaffolds write one (observed on v0.55.0):

```
require (
	dev.upbound.io/models v0.0.0
	...
)

replace dev.upbound.io/models => ../../.up/go/models
```

- **`go mod tidy` drops the `require` while nothing imports a model**, and keeps the `replace`. That is
  expected: the first model import, followed by `go mod tidy`, adds the `require` back (as
  `v0.0.0-00010101000000-000000000000`).
- **Keep the `replace` even while it looks unused.** Without it the first model import fails with
  `unrecognized import path "dev.upbound.io/models"`. A module created by hand, with `mkdir` and a copied
  `go.mod`, often has none: scaffold with the CLI instead.
- The path is relative, so it holds only for a module two levels below the project root (`functions/<n>/`,
  `tests/<t>/`).

---

## What is different about Go

**Go test manifests are generated on your machine.** `up test run` runs `go mod tidy` and
then `go run .` locally rather than starting a build container (up v0.55.0 source), so the `UP_`
prefix filter and the unmounted `~/.aws` in
[`control-plane-project-charter` §7](../../SKILL.md#7-the-container-boundary) **do not apply to a Go test
module**. It inherits `up`'s full environment, whatever the variable is called, and reads your
real files. If a variable seems not to arrive, it was not exported in the shell that ran `up`.

Go is not unique in this — go-templating and YAML tests also run locally (in-process, without
a container at all). KCL and both Python layouts are the containerized ones.

Three consequences:

1. **Name test inputs `UP_*` anyway.** Go does not need the prefix, but the KCL and Python
   tests do, the same test ports to them unchanged, and one `grep` for `UP_` lists everything
   a run needs. Say in a comment that the prefix is a convention here, not a filter.
2. A Go test that works locally may depend on something no CI runner has. Whatever the test
   reads from the environment, name it explicitly.
3. **Every matched test program runs on every `up test run`, e2e ones too, even without
   `--e2e`.** An e2e program that exits non-zero on a missing input therefore fails a plain
   `up test run "tests/*"` at `✗ Parsing tests`. The composition gate is
   `up test run "tests/test-*"` (charter §7; [`go/tests.md`](go/tests.md#e2e-tests)).

### The function container is a different matter

None of the above applies to the composition function itself. Rendering runs **every**
function as a Docker container, Go included, with no forwarded environment and no host
mounts. A Go function never sees your shell environment or your credential files.

### And Go is the one language `up project build` actually compiles

The Go builder runs `go mod tidy` and a real `ko` compile, so a Go function that does not
compile **fails the build** — unlike KCL and single-file Python, where the build only tars
source into an image. That makes a green `up project build` worth slightly more here than
[`control-plane-project-charter` §8](../../SKILL.md#8-a-green-run-is-not-evidence) allows in general. It still
does not mean the function *runs*.

## Everything else is the same

Go tests render to the **same** `CompositionTest` / `E2ETest` objects
(`meta.dev.upbound.io/v1alpha1`) as every other language. The fields, the semantics of
`assertResources` (partial and positive for objects, **exact for lists**), timeouts, and the
`extraResources` structure are identical — [`yaml.md`](yaml.md) is the clearest reading of
that object model, because it shows the objects with no language in the way.

Namespaced APIs reach Go as plain `apiVersion` strings: `s3.aws.m.upbound.io/v1beta1`.

## Choosing the test language

**Go functions get Go tests**, unless the project already has tests in another language —
then match those ([`control-plane-project-charter` §10](../../SKILL.md#10-language-dispatch)). Only a
test that emits a `CompositionTest` or `E2ETest` counts: a Go program in `tests/` printing
`items: []` neither makes the project's tests Go nor keeps them from being Go. The tests
build their expectations from the same generated models the function uses, so a misspelt
field fails to compile instead of failing a render. The template, the model import paths and
the failure modes are in [`go/tests.md`](go/tests.md).

go-templating tests (`*.gotmpl`) are a different language with their own reference:
[`go-templating.md`](go-templating.md).
