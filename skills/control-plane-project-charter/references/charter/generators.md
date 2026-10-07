# What the CLI generators emit

The accepted `--language` slugs, and what each generator actually produces. [`control-plane-project-charter` §10](../../SKILL.md#10-language-dispatch) states the dispatch rule.

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

The XRD is the exception (§5): nothing wires it up, and `up project build` reads whatever is in
`apis/`.

### What the generators actually emit

| Command | What you get |
|---|---|
| `up project init --template <t> --language <l>` | a **Crossplane v1** project: XRD at `apiextensions.crossplane.io/v1` with `claimNames` and no `scope`, and a function importing the **non-`.m.`** provider models. Establish the project's generation before applying §5 — its rules are for v2 and will break a v1 project. |
| `up test generate <n>` | `tests/test-<n>/` — the CLI prepends `test-` itself. Passing `test-<n>` gives you `tests/test-test-<n>/`. The stub does not run: `assertResources: []` plus empty `xrPath`, `compositionPath` and `xrdPath`, and the empty `compositionPath` fails before any assertion with `cannot load Composition from "": not a composition: /`. That is a broken test, not RED (§3): fill the paths in first. |
| `up composition generate <xrd>` | a pipeline of auto-ready steps only. It adds a `crossplane-contrib-function-auto-ready` step and `crossplane-contrib/function-auto-ready` at `'>=v0.0.0'` to `dependsOn`, even when the project already declares an auto-ready function (`upbound/function-auto-ready`), which then gets a step of its own as well (observed with up v0.55.0). When the project declares its own function set, delete the duplicate step and its dependency, and say so in your report. Your function is not wired in; a test pointed at it renders nothing and passes vacuously. `up function generate <n> <composition-path>` inserts the step. |
| `up xrd generate <example>` | a schema inferred from one example: no `required:`, no `default:`, no `minItems`, no `status` properties, `integer` widened to `number`, an open-ended map frozen into the keys the example used, and an array's item schema taken from the **last** element only (§5). |

The `functionRef` name in a composition is `<repository-org>-<repository-name><function-dir>`,
concatenated with no separator between the repository name and the directory, taken from
`spec.repository` in `upbound.yaml` when you generate. **Set the project metadata before
`up composition generate` and `up function generate`:** the embedded function's name follows
`spec.repository`, so changing it afterwards leaves every `functionRef` naming the old function,
and they must be regenerated or rewritten with this formula.

A `functionRef.name` that departs from the formula names no function the render knows: every
render fails with `unknown function`, the same error as an external function missing from
`dependsOn`. Keep the generated name; don't hand-edit it, and don't take a name from a work item
over the formula.

`up function generate <n> <composition-path>` on an existing `functions/<n>` asks whether to
overwrite it. Without a TTY it prints `operation cancelled by user` and exits 1 (observed with
up v0.55.0). To wire a function that already exists, add the step by hand instead: a
`functionRef.name` from the formula above and `step: <n>`, before the auto-ready step.
