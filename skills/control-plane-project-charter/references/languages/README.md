# Language references

One file per language, shared by every skill in this plugin. Each file covers **both**
composition functions and tests for that language.

The rules that do not depend on language live in [`../CHARTER.md`](../../SKILL.md) and are
deliberately absent from these files. Read the charter first.

| Language | Composition functions | Tests | File |
|---|---|---|---|
| KCL | yes | yes | [`kcl.md`](kcl.md) + [`kcl/`](kcl/) |
| Python | yes | yes | [`python.md`](python.md) + [`python/`](python/) |
| TypeScript | yes, but hand-built — the CLI has no TS builder yet | use YAML or KCL tests | [`typescript.md`](typescript.md) |
| YAML | n/a | yes | [`yaml.md`](yaml.md) |
| Go | CLI only, no templates | CLI only, no templates | [`go.md`](go.md) |

## Detecting which one to read

**The composition language and the test language are independent axes.** `up project init`
takes `--language` and `--test-language` separately, and a Python-function project commonly
ships YAML tests. Detect each from its own directory:

```
functions/*/*.k                          → kcl.md
functions/*/main.py | function/fn.py     → python.md
functions/*/*.ts                         → typescript.md (hand-built; see its header)
functions/*/*.go                         → go.md

tests/*/*.k                              → kcl.md
tests/*/main.py | test/__main__.py       → python.md
tests/*/test.yaml (and no other source)  → yaml.md
tests/*/*.go | *.gotmpl                  → go.md
```

No tests yet? Match an existing test anywhere in the project; else follow the composition
language; else default to YAML — it is the simplest and has no toolchain coupling.

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
