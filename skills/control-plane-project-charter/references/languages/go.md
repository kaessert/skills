# Go

Go is supported by the CLI for both composition functions and tests. This reference ships a
verified **test** template and the reproduced test pitfalls in [`go/tests.md`](go/tests.md);
it ships **no function templates** yet. That is a gap, not a prohibition: scaffold the
function with the CLI, then apply the charter.

The language-agnostic rules — the TDD loop, what a v2 managed resource needs, what a green
run proves, reporting discipline — are in [`control-plane-project-charter`](../../SKILL.md) and apply
unchanged.

| | |
|---|---|
| Scaffold a function | `up function generate <n> --language go` |
| Scaffold a test | `up test generate <n> --language go` (add `--e2e`) — then read [`go/tests.md`](go/tests.md) |
| Run a test | `up test run tests/test-<n>` runs `go run .` with the test dir as CWD; the program must print `items: [<CompositionTest>…]`. `items: []` is zero tests, and a run with zero tests prints `No test files found` and exits 0 — nothing ran |
| Compile | `go vet ./...` or `go build -o /dev/null ./...` — plain `go build ./...` in a single-package module (every generated function) writes the executable into the function directory, and it ends up committed |
| Before committing | `gofmt -l .` (prints nothing), `go vet ./...`, `go mod tidy` in every function and test module |

## What is different about Go

**Go test manifests are generated on your machine.** `up test run` runs `go mod tidy` and
then `go run .` locally rather than starting a build container, so the `UP_` prefix filter and
the unmounted `~/.aws` in
[`control-plane-project-charter` §7](../../SKILL.md#7-the-container-boundary) **do not apply to a Go test
module**. It sees your real environment and your real credential files.

Go is not unique in this — go-templating and YAML tests also run locally (in-process, without
a container at all). KCL and both Python layouts are the containerized ones.

Two consequences:

1. Do not carry the `UP_`-prefixed credential pattern across from the KCL or Python
   templates. It is not wrong, but it is not required either, and copying it without saying
   why leaves the next reader believing the boundary exists here.
2. A Go test that works locally may depend on something no CI runner has. Whatever the test
   reads from the environment, name it explicitly.

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
then match those ([`control-plane-project-charter` §10](../../SKILL.md#10-language-dispatch)). The tests
build their expectations from the same generated models the function uses, so a misspelt
field fails to compile instead of failing a render. The template, the model import paths and
the failure modes are in [`go/tests.md`](go/tests.md).

go-templating tests (`*.gotmpl`) are a different language with their own reference:
[`go-templating.md`](go-templating.md).
