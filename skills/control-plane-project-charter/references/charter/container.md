# The container boundary

Where manifest generation and function rendering actually run, and what crosses into them. [`../CHARTER.md` §7](../../SKILL.md#7-the-container-boundary) states the rule.

---

**Manifest generation does not run on your machine — in most languages.** `up test run` tars
the project, starts a Docker container from the language's build image, and runs your test
module inside it.

| Test language | Where generation runs |
|---|---|
| KCL | container (`kcl run -o test.yaml`) |
| Python, embedded (`main.py`) | container (`uptestpyrunner`) |
| Python, SDK (`pyproject.toml`) | container (`hatch run test`) |
| Go | **locally** — `go mod tidy` then `go run .` |
| go-templating | **locally** — in-process, no container |
| YAML | **locally** — in-process, no container |

So the boundary below applies to KCL and Python. It does not apply to Go, go-templating or
YAML tests, which see your real environment and your real credential files.

Two consequences, and they are the difference between a working test and two wasted runs:

1. **`~/.aws`, `~/.config/gcloud` and `~/.azure` are not mounted.** Nothing that reads a
   credentials file or a cloud CLI's config finds anything. A default credential chain
   resolves to nothing inside that container.
2. **Only environment variables whose names start with `UP_` are passed in.** The runner
   filters the environment on that prefix and forwards nothing else. `AWS_ACCESS_KEY_ID`,
   `AZURE_CREDENTIALS`, `GOOGLE_APPLICATION_CREDENTIALS` — all absent, whatever your shell
   has exported.

So a credential reaches a generated manifest by exactly one route: **export it under a `UP_`
name before the run, and read that name in the test module.**

```bash
export UP_AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id)
export UP_AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key)
up test run tests/e2etest-<n> --e2e --control-plane-group=<group>
```

**Read the variable in a way that fails loudly when it is missing.** A silent fallback to
`""` generates a syntactically valid Secret holding nothing; the run then proceeds all the
way to provisioning a control plane and real resources before the provider rejects the empty
key. Failing at manifest generation costs about a second and names the variable you forgot.

Prefer web identity (`source: Upbound`) wherever the platform supports it — no credential
crosses the boundary at all, and this whole section stops applying.

**There is a second boundary, and it is tighter than the first.** Rendering runs each
composition function as a Docker container, in *every* language including Go. Nothing mounts a
host path into those containers, and by default nothing forwards your shell environment into
them — a composition function never sees your credential files, whatever the table above says
about its tests.

The one deliberate escape hatch is the `render.crossplane.io/runtime-docker-env` function
annotation, set with `up test run --function-annotations render.crossplane.io/runtime-docker-env=KEY=VALUE`.
It injects explicit `k=v` pairs and nothing else. If a function genuinely needs a value at
render time, that is the supported route — not an env var you exported and hoped would arrive.
