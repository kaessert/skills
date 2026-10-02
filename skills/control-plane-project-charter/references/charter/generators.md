# What the CLI generators emit

The accepted `--language` slugs, what each generator actually produces, and the one file you should write yourself. [`control-plane-project-charter` §10](../../SKILL.md#10-language-dispatch) states the dispatch rule.

---

**The slugs the CLI actually accepts** — do not invent one, the flag is validated and will
reject it:

| Command | Accepted `--language` |
|---|---|
| `up function generate` | `go`, `go-templating`, `kcl`, `python` |
| `up test generate` | `go`, `go-templating`, `kcl`, `python`, `yaml` |
| `up project init` | `go`, `go-templating`, `kcl`, `python` (and the same set for `--test-language`) |

Never scaffold a **function or test directory** by hand. `up function generate` and
`up test generate` produce the layout the CLI expects — `pyproject.toml` pins, the models
path, the pipeline step in the composition — and the layout differs between a
template-initialised project and a generated one; match what the project already uses rather
than imposing a preference.

**The XRD is the exception**: it is one declarative file, not a layout, and you should write it
directly (§5). Nothing wires it up — `up project build` reads whatever is in `apis/`.

### What the generators actually emit

| Command | What you get |
|---|---|
| `up project init --template <t> --language <l>` | a **Crossplane v1** project: XRD at `apiextensions.crossplane.io/v1` with `claimNames` and no `scope`, and a function importing the **non-`.m.`** provider models. Establish the project's generation before applying §5 — its rules are for v2 and will break a v1 project. |
| `up test generate <n>` | `tests/test-<n>/` — the CLI prepends `test-` itself. Passing `test-<n>` gives you `tests/test-test-<n>/`. |
| `up composition generate <xrd>` | a pipeline containing **only** `function-auto-ready`. Your function is not wired in; a test pointed at it renders nothing and passes vacuously. `up function generate <n> <composition-path>` inserts the step. |
| `up xrd generate <example>` | a schema inferred from one example: no `required:`, no `default:`, no `minItems`, no `status` properties, `integer` widened to `number`, an open-ended map frozen into the keys the example used, and an array's item schema taken from the **last** element only. **Write the XRD yourself** (§5) — repairing all of that is more work than authoring it. |

The `functionRef` name in a composition is `<repository-org>-<repository-name><function-dir>`,
concatenated with no separator between the repository name and the directory — read
`spec.repository` in `upbound.yaml` if you have to write one by hand.
