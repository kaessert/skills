# Python

Everything Python-specific for a control-plane project: composition functions **and** tests.

The language-agnostic rules — the TDD loop, what a v2 managed resource needs, the container
boundary, what a green run proves, reporting discipline — are in
[`control-plane-project-charter`](../../SKILL.md) and are **not** repeated here. Read the charter first; this
file only tells you how Python expresses it.

The two helper scripts referenced below ship with the `author-composition` skill, not with
the project under test. Resolve them once, from that skill's own directory
(`<author-composition>` is its absolute path):

```bash
SCRIPTS=<author-composition>/scripts
# A wrong path makes every call below die with a bare "No such file".
[ -f "$SCRIPTS/probe_project.py" ] || echo "probe_project.py not found — pass its path explicitly"
```

| | |
|---|---|
| Scaffold a function | `up function generate <n> --language python` |
| Scaffold a test | `up test generate <n> --language python` (add `--e2e`) — writes `tests/test-<n>/`; the CLI prepends `test-` itself, so do not pass it |
| **Set up the venv — do this first** | `python3 "$SCRIPTS/setup_venv.py" --project <root>` — right after the first `up project build`, so imports resolve for whoever is reading along |
| Probe the project | `python3 "$SCRIPTS/probe_project.py" --project <root>` |
| Fast inner loop | `python3 "$SCRIPTS/run_function.py" --project <root> --minimal examples/<x>/example.yaml` — the only host-side step that needs a venv; see below |


## Host-side Python: set the venv up first

**Do this once, at the start, before you write any function or test code** — right after the
first `up project build`, which is what creates the models it installs. It takes ~11s.

```bash
python3 "$SCRIPTS/setup_venv.py"
```

**The person you are working for is reading this code in an editor while you write it.**
Without the venv on the interpreter path, every `from models.io...` and
`from crossplane.function import ...` is underlined in red, go-to-definition on a generated
model goes nowhere, and autocomplete for `forProvider` fields is dead — on code that is
completely correct. Someone trying to follow along cannot tell your mistakes from the
environment's, and the natural response is to "fix" imports that were right. That alone is
reason enough to run it before writing a line.

Deferring it is the common mistake, and the reason is that the charter's loop genuinely does
not need it: your function never runs on your host, so a project with no venv still builds and
still goes green. That is true and it is beside the point — going green is not the only thing
happening.

| What | Runs where | Needs a venv |
|---|---|---|
| The function, under `up test run` / `up project build` | container | no |
| `probe_project.py` | host | **no** — standard library only |
| `run_function.py` (the fast tier) | host | **yes** — no venv, no fast tier |
| Your editor / language server | host | **yes**, or every model import is underlined |

Both of those bite *after* the point where it is convenient to stop and fix them. Without the
venv the fast tier simply is not available, so the two-tier loop collapses to one tier and
every iteration pays a full build. And your editor marks `from models.io...` and
`from crossplane.function import ...` unresolved on code that is correct — which invites
"fixing" an import that was right all along.

**Build the venv from the project's own pins, not by package name.** `pip install
crossplane-function-sdk-python` gets the newest release, and `resource.update()` has changed
across versions — 0.5.0 serializes with `exclude_defaults` and does *not* re-add
`apiVersion`/`kind`, 0.11.0 adds them back, 0.14.0 switched to `exclude_unset`. A fast tier
running a different serializer from the container is not a proxy for the real run.

```bash
up project build                       # .up/python must exist first
python3 "$SCRIPTS/setup_venv.py"       # ~11s
```

That creates `.venv` at the project root, installs every function and test directory from
its own pins, installs the generated models **editable and last**, verifies the imports
resolve, and writes `.vscode/settings.json` so VS Code offers the right interpreter. Re-run
it when you add a function or test directory. Do **not** re-run it after `up project build`
— see below.

<details>
<summary>What it does, and why the order matters</summary>

```bash
# 0. Pick the interpreter deliberately. Every generated pyproject.toml — the models
# package included — declares `requires-python = ">=3.11,<3.14"`, and `python3` on a
# current machine is often already 3.14:
PYBIN=$(for v in 3.13 3.12 3.11; do command -v python$v && break; done)
echo "using ${PYBIN:?no supported Python found — brew install python@3.13}"

"$PYBIN" -m venv .venv
.venv/bin/pip install --upgrade pip     # NOT optional — see below

# 1. SDK layout — pyproject.toml pins the SDK and wires the generated models:
cd functions/<fn> && ../../.venv/bin/pip install -e .
# The cd is load-bearing. pip resolves the pyproject's relative
# `crossplane-models @ file:./../../.up/python` against the CURRENT DIRECTORY, not against
# the pyproject's own directory. From the project root it fails with a confusing
# "No such file or directory" naming a path two levels above the project.

# 1b. Embedded layout — requirements.txt has the pins, and the models reach the function
# through the `model -> ../../.up/python/models` symlink already in the directory:
.venv/bin/pip install -r functions/<fn>/requirements.txt

# 2. Every test directory too — SDK layout like the function, embedded via requirements:
cd ../../tests/<test> && ../../.venv/bin/pip install -e .          # SDK layout
.venv/bin/pip install -r tests/<test>/requirements.txt             # embedded layout

# 3. The models LAST, and editable:
.venv/bin/pip install -e .up/python

# 4. run_function.py reads examples with PyYAML, which only a test pyproject pins:
.venv/bin/pip install pyyaml
```

**Upgrading pip is not optional.** The pip bundled with a fresh 3.11 venv (23.2.1) cannot
parse the relative `crossplane-models @ file:./../../.up/python` requirement and fails with
`InvalidRequirement: Invalid URL given`. Nothing in the message names pip's version or the
requirement, so it reads as a broken project. `setup_venv.py` upgrades pip before it installs
anything, which is why the script works where a hand-typed sequence often does not.

**A venv on the wrong interpreter is worse than no venv.** `python3.14 -m venv .venv`
succeeds; it is the *installs* that fail, each with `Package '...' requires a different
Python: 3.14.4 not in '<3.14,>=3.11'`. What is left behind is an empty `.venv` at the
project root — which VS Code discovers on its own and then reports every `models.*` and
`crossplane.function.*` import unresolved, on correct code, no matter which interpreter you
select afterwards. A venv is bound for life to the interpreter that created it and cannot be
re-pointed, so the only repair is `rm -rf .venv` and a rebuild on a supported interpreter.
`setup_venv.py` reads the constraint out of the project's own pyprojects before it creates
anything, picks the newest `python3.N` on PATH that satisfies it, and replaces an existing
venv that does not (pass `--no-recreate` to be told instead of having it done).

**Last is not a style choice.** Every function and test `pyproject.toml` declares
`crossplane-models @ file:./../../.up/python` as an ordinary dependency, so installing one of
them *copies* the models into `site-packages` and silently replaces an editable install. Do
it in the other order and `pip list` still shows `crossplane-models`, but a regenerated model
is invisible.

Installed last and editable, pip writes a plain `.pth` holding the path to `.up/python`, so
the whole directory is on `sys.path`. Verified end to end: `up dep add` a new provider,
`up project build`, and `import models.io.upbound.m.aws.kms.key.v1beta1` resolves with **no
pip step at all**. New Kinds, new versions and changed fields all arrive for free.

</details>

**The editor is the reason to bother.** Without a venv on the interpreter path, every
`from models.io.upbound.m...` and `from crossplane.function import ...` shows as an unresolved
import, on code that is completely correct. Do not "fix" an import in response to that
diagnostic — verify the path with `probe_project.py` instead, which needs no venv and reads
the generated models directly.

The interpreter is *all* VS Code needs: no `python.analysis.extraPaths`, and no
`__init__.py` for the embedded layout's relative `.model.*` imports — the in-directory
`model` symlink already resolves for the language server. Measured with pyright against both
layouts: **0 unresolved imports**.

One diagnostic does survive on the SDK-layout scaffold —
`Method "RunFunction" overrides class "FunctionRunnerService" in an incompatible manner`.
The generated function subclasses the gRPC *client* stub, whose `RunFunction` is a
ten-argument `@staticmethod`; registration is duck-typed
(`add_FunctionRunnerServiceServicer_to_server` only reads `.RunFunction`) and the SDK's own
`runtime.py` annotates the same base, so the scaffold is correct and the diagnostic is noise.
`setup_venv.py` switches off that one rule via `python.analysis.diagnosticSeverityOverrides`.
Do not restructure the scaffold to silence it.

**A stored interpreter choice beats `settings.json`.** `python.defaultInterpreterPath` only
applies when the workspace has no interpreter selected yet. If one was picked earlier — or
the *parent* folder was opened and a choice made there, which stores it for every project
inside — that choice wins and the file the script wrote is ignored. Clear it with
**Python: Clear Workspace Interpreter Setting**, then **Developer: Reload Window**. Open the
project directory itself as the workspace root, not the directory holding several projects.

---

## Where everything is

This file is the index: setup, the toolchain commands, and layout detection. Everything else
sits in [`python/`](python/), so each file stays small enough to read in one go.

| File | What is in it |
|---|---|
| [`python/imports.md`](python/imports.md) | deriving the import path for any Kind, and the class names inside a generated model |
| [`python/patterns.md`](python/patterns.md) | the function bootstrap, what a v2 managed resource needs, tag maps, `resource.update()` semantics, optional XRD objects, namespace propagation, XRD schema design |
| [`python/readiness.md`](python/readiness.md) | connection details by composition key, ProviderConfig readiness, safe conditional creation, manual secrets, reading a render |
| [`python/tests.md`](python/tests.md) | what a suite must contain, assertion semantics, the two dump modes |
| [`python/test-templates.md`](python/test-templates.md) | annotated composition-test and E2E-test scaffolds |
| [`python/examples.md`](python/examples.md) | two complete functions, plus `upbound.yaml` and `pyproject.toml` |
| [`python/pitfalls.md`](python/pitfalls.md) | mistakes that produce a green run and a broken platform, debugging, v1 → v2 |

---

# Part 1 — Layout

## SDK vs embedded — detect before you write a line

There are **two** current Python layouts. How `up` picks between them is **not** the same
question for functions and for tests, and the difference has cost people time:

| | How `up` selects |
|---|---|
| **Function** | SDK when the function directory has **both** a `pyproject.toml` *and* a `function/` subdirectory; otherwise a `main.py` at the function root selects the embedded builder |
| **Test** | SDK when the test directory has a `pyproject.toml`; that is checked before `main.py` |

Note the trap: the SDK layout *also* has a `functions/<n>/function/main.py` (the click
entrypoint). Only a `main.py` at the **function root** means embedded.


| | SDK project | Embedded |
|---|---|---|
| Function | `functions/<n>/function/fn.py` — a `FunctionRunner` class with `async def RunFunction(self, req, _)` | `functions/<n>/main.py` — `def compose(req, rsp)` |
| Test | `tests/test-<n>/test/__main__.py` — builds the CompositionTest and ends with `print(yaml.dump({"items": [...]}))` | `tests/test-<n>/main.py` — module-level `CompositionTest` objects (e.g. `test1`, `test2`); the runner collects them, there is **no** `items` list and nothing is printed |
| Model import | `from models.io...` (installed pkg) | `from .model.io...` (`model` symlink) |
| Deps | `pyproject.toml` (hatch) + `crossplane-models @ file:./<rel>/.up/python` | `requirements.txt` + `functions/<n>/model` symlink |

**Match the layout the project already uses — do not convert one to the other.** Both layouts are
current and you will meet both:

- **`up function generate` / `up test generate --language python` produce the SDK layout.** Use it for anything you scaffold yourself.
- **`up project init`'s language templates (e.g. AWS Bucket + Python) produce the embedded layout.** A project started from a template therefore has `main.py` functions and `main.py` + `resources.py` tests, and new code you add there must stay embedded.

Detect it before writing a line — the probe script reports it per directory:

```bash
python3 "$SCRIPTS/probe_project.py" --project <project-root>
# function  functions/compose-bucket     layout=embedded  import prefix='.model.'
# test      tests/test-storagebucket     layout=embedded  import prefix='.model.'
```

Both layouts build one embedded OCI function image referenced by the composition's `functionRef`; only the source layout and model-import prefix differ.

**Create scaffolds with the CLI — never hand-write the `pyproject.toml` or package layout.**
New composition test: `up test generate <name> --language python`; new E2E test: add `--e2e`;
new function: `up function generate <name> [<composition-path>] --language python`. Then edit
**only** the logic files.

> **The CLI has no embedded Python templates.** `cmd/up/test/templates/python/` holds the SDK
> shape only, so running `up test generate --language python` inside a template-derived
> (embedded) project produces an **SDK** test in an embedded project — two layouts in one tree.
> In an embedded project, copy an existing test directory instead, and keep the
> module-level-objects shape.

A missing `crossplane-models` dependency breaks your imports, but it does not change how `up`
detects the layout — that is the `pyproject.toml` + `function/` rule above.

> **Sequencing gotcha:** the `crossplane-models` dependency is written into the function/test `pyproject.toml` only when the schemas already exist. Make sure `.up/python` exists *before* `up function generate`/`up test generate` — `up project build`, `up dependency add`, and `up xrd generate` all create it. Otherwise add `"crossplane-models @ file:./<relative-path>/.up/python"` to `dependencies` yourself, or the `from models.io...` imports won't resolve.

### SDK function skeleton (`functions/<n>/function/fn.py`)

```python
import grpc
from crossplane.function import logging, resource, response
from crossplane.function.proto.v1 import run_function_pb2 as fnv1
from crossplane.function.proto.v1 import run_function_pb2_grpc as grpcv1
from models.io.k8s.apimachinery.pkg.apis.meta import v1 as k8s
from models.io.upbound.m.azure.resourcegroup import v1beta1 as rgv1beta1
from models.io.example.platform.network import v1alpha1 as networkv1alpha1


class FunctionRunner(grpcv1.FunctionRunnerService):
    def __init__(self):
        self.log = logging.get_logger()

    async def RunFunction(
        self, req: fnv1.RunFunctionRequest, _: grpc.aio.ServicerContext
    ) -> fnv1.RunFunctionResponse:
        rsp = response.to(req)
        observed_xr = networkv1alpha1.Network(
            **resource.struct_to_dict(req.observed.composite.resource)
        )
        # ...build managed resources (forProvider only — see below), then:
        resource.update(rsp.desired.resources["rg"], desired_group)
        return rsp
```


## Test file shapes

The same SDK/embedded split applies to `tests/`, and the *test* directory decides — a
project can have SDK functions and embedded tests or the reverse.

| | SDK test | Embedded test |
|---|---|---|
| Test file | `tests/test-<n>/test/__main__.py` — builds the test and ends with `print(yaml.dump({"items": [...]}))` | `tests/test-<n>/main.py` — defines **module-level `CompositionTest` objects** (e.g. `test1`, `test2`); the runner collects them. There is no `items` list and nothing is printed |
| Helper file | as you like | templates split assertions into `tests/test-<n>/resources.py` |

Never hand-write `pyproject.toml` or the package layout — the CLI wires the
`crossplane-models` dependency for you.

### Embedded test shape (what the templates actually generate)

```python
# tests/test-storagebucket/main.py
from .model.io.upbound.dev.meta.compositiontest import v1alpha1 as compositiontest
from .model.io.k8s.apimachinery.pkg.apis.meta import v1 as metav1
from . import resources

def buildTest(name, observed, expected) -> compositiontest.CompositionTest:
    return compositiontest.CompositionTest(
        metadata=metav1.ObjectMeta(name=name),
        spec=compositiontest.Spec(
            observedResources=[o.model_dump(exclude_unset=True) for o in observed],
            assertResources=[e.model_dump(exclude_unset=True) for e in expected],
            compositionPath="apis/storagebucket/composition.yaml",
            xrPath="examples/storagebuckets/example.yaml",
            xrdPath="apis/storagebucket/definition.yaml",
            timeoutSeconds=120,
            validate=False,
        ),
    )

# One module-level object per test. Names are arbitrary; the runner collects them.
test1 = buildTest("bucket-not-yet-created", observed=[], expected=[...])
test2 = buildTest("bucket-created", observed=[resources.observed_bucket], expected=[...])
```

`observedResources` is how you drive a multi-pass composition: a function that returns early until
a dependency is observed needs one test with `observed=[]` and another with the dependency present.

> **Sequencing gotcha:** `crossplane-models` is written into the test's `pyproject.toml` only when the schemas already exist. Run `up project build` (or `up dependency add`) so `.up/python` exists **before** `up test generate` - otherwise the `from models.io...` imports won't resolve.


---

# Part 3 — Composition functions
