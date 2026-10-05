# Language references

One file per language, shared by every skill in this plugin; each covers both composition
functions and tests. Language-neutral rules live in [`control-plane-project-charter`](../../SKILL.md)
and are not repeated here.

## Detecting the language

Detect each directory on its own: the composition language from `functions/<n>/`, the test
language from `tests/<n>/`. They are separate axes, and a project may mix them. The markers are the
ones `up` itself checks (up v0.55.0), in its order — **the first match wins**:

| Directory contains | Language | Functions: read | Tests: read |
|---|---|---|---|
| `pyproject.toml` **and** a `function/` dir (functions); `pyproject.toml` (tests) | Python, SDK layout | [`python.md`](python.md) + [`python/`](python/) | [`python/tests.md`](python/tests.md), [`python/test-templates.md`](python/test-templates.md) |
| `kcl.mod` | KCL | [`kcl.md`](kcl.md) + [`kcl/`](kcl/) | [`kcl/tests.md`](kcl/tests.md) |
| `main.py` | Python, embedded layout | [`python.md`](python.md) + [`python/`](python/) | [`python/tests.md`](python/tests.md), [`python/test-templates.md`](python/test-templates.md) |
| `go.mod` | Go | [`go.md`](go.md), [`go/functions.md`](go/functions.md) | [`go.md`](go.md), [`go/tests.md`](go/tests.md) |
| only `*.gotmpl` / `*.tmpl` files (subdirectories allowed) | go-templating | [`go-templating.md`](go-templating.md) — covers the function scaffold only | [`go-templating.md`](go-templating.md) |
| `test.yaml` (tests only) | YAML | — | [`yaml.md`](yaml.md) |
| `package.json` / `*.ts` (functions) | TypeScript: `up` has no builder, so `up project build` fails with `no suitable builder found` | [`typescript.md`](typescript.md) — its header says how these projects are built | — (no TypeScript test language) |

Order matters in two places. For **tests**, `kcl.mod` is checked first and `pyproject.toml` before
`main.py`; for **functions**, the Python SDK layout (`pyproject.toml` plus `function/`) is checked
before `kcl.mod`. A Python SDK function also has `function/main.py`; only a `main.py` at the
directory root means embedded.

A test directory that matches no row is skipped without a message. One that matches but produces
no `CompositionTest` or `E2ETest` — a Go program printing `items: []` — contributes zero tests
(charter §8).

**Which language to write *new* tests in** is a choice, not a detection:
[`control-plane-project-charter` §10](../../SKILL.md#10-language-dispatch).

## Adding a language

A language reference that outgrows one file becomes an index plus a same-named directory
of detail files (`python.md` + `python/`, `kcl.md` + `kcl/`) — keep each file small enough
to read in one go, since a large one gets redirected into a scratch file instead of
returned. The index keeps the toolchain commands; the detection marker goes in the table above.

A new file belongs here, not inside a skill, and it carries only what is specific to the
language: layout, import or type paths, the function bootstrap, how each agnostic pattern is
expressed, test templates, toolchain, and language-specific mistakes. A rule that would be true
in any language belongs in the charter: put it there and link to it.
