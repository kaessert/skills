# Go

Go is supported by the CLI for both composition functions and tests, but this skill ships
**no Go templates**. That is a gap, not a prohibition: scaffold with the CLI, then apply the
charter.

The language-agnostic rules — the TDD loop, what a v2 managed resource needs, what a green
run proves, reporting discipline — are in [`../charter.md`](../charter.md) and apply
unchanged.

| | |
|---|---|
| Scaffold a function | `up function generate <n> --language go` |
| Scaffold a test | `up test generate <n> --language go` (or `--language go-templating`; add `--e2e`) |
| Compile | `go build ./...` |

## What is different about Go

**Go test manifests are generated on your machine.** `up test run` runs `go mod tidy` and
then `go run .` locally rather than starting a build container, so the `UP_` prefix filter and
the unmounted `~/.aws` in
[`../charter.md` §7](../charter.md#7-the-container-boundary) **do not apply to a Go test
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
[`../charter.md` §8](../charter.md#8-a-green-run-is-not-evidence) allows in general. It still
does not mean the function *runs*.

## Everything else is the same

Go tests render to the **same** `CompositionTest` / `E2ETest` objects
(`meta.dev.upbound.io/v1alpha1`) as every other language. The fields, the semantics of
`assertResources` (partial and positive for objects, **exact for lists**), timeouts, and the
`extraResources` structure are identical — [`yaml.md`](yaml.md) is the clearest reading of
that object model, because it shows the objects with no language in the way.

Namespaced APIs reach Go as plain `apiVersion` strings: `s3.aws.m.upbound.io/v1beta1`.

## Choosing Go

**Prefer YAML tests unless the project already commits to Go.** The test language is
independent of the function language, so a Go-function project can perfectly well have YAML
tests, and those have templates here. Pick Go tests when the project's team already maintains
Go, or when the test needs real programmatic generation.

If you do write Go here, the useful contribution is to add the templates this file is missing.
