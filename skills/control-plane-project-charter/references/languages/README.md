# Language references

One file per language, shared by every skill in this plugin. Each file covers **both**
composition functions and tests for that language.

The rules that do not depend on language live in [`control-plane-project-charter`](../../SKILL.md) and are
deliberately absent from these files. Read the charter first.

| Language | Composition functions | Tests | File |
|---|---|---|---|
| KCL | yes | yes | [`kcl.md`](kcl.md) + [`kcl/`](kcl/) |
| Python | yes | yes | [`python.md`](python.md) + [`python/`](python/) |
| TypeScript | yes, but hand-built — the CLI has no TS builder yet | YAML (the fallback) | [`typescript.md`](typescript.md) |
| YAML | n/a | yes — the fallback test language | [`yaml.md`](yaml.md) |
| Go | yes, verified template | yes, verified template | [`go.md`](go.md) + [`go/`](go/) |
| go-templating | CLI only, no templates | yes, verified template | [`go-templating.md`](go-templating.md) |

## Detecting which one to read

The composition language and the test language are separate axes — `up project init` takes
`--language` and `--test-language` separately, and an existing project may mix them. Detect
each from its own directory:

```
functions/*/*.k                          → kcl.md
functions/*/main.py | function/fn.py     → python.md
functions/*/*.ts                         → typescript.md (hand-built; see its header)
functions/*/*.go                         → go.md
functions/*/*.gotmpl                     → go-templating.md

tests/*/*.k                              → kcl.md
tests/*/main.py | test/__main__.py       → python.md
tests/*/test.yaml (and no other source)  → yaml.md
tests/*/go.mod                           → go/tests.md
tests/*/*.gotmpl (every file in the dir) → go-templating.md
```

Existing tests decide the language of new ones. Only a test dir that produces a
`CompositionTest` or `E2ETest` counts; a program printing `items: []` does not. No tests
yet? Write them in the composition language (every language `up function generate` produces
is also a test language); else YAML — the fallback for TypeScript functions and projects with
no embedded function. The reasons are in [`control-plane-project-charter` §10](../../SKILL.md#10-language-dispatch).

## Adding a language

A language reference that outgrows one file becomes an index plus a same-named directory
of detail files (`python.md` + `python/`, `kcl.md` + `kcl/`) — keep each file small enough
to read in one go, since a large one gets redirected into a scratch file instead of
returned. The index keeps the layout detection and the toolchain commands.

A new file belongs here, not inside a skill, and it carries only what is specific to the
language: layout, import or type paths, the function bootstrap, how each agnostic pattern is
expressed, test templates, toolchain, and language-specific mistakes. If you find yourself
writing a rule that would be true in any language, it belongs in the charter — put it there
and link to it.
