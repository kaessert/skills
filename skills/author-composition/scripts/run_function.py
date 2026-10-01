#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Execute a composition function locally against one or more example XRs.

`up project build` is a packaging step. It does not import, type-check, or run your
function, so an `AttributeError` on the function's normal path survives a green build.
Composition tests are better but render-only and partial-positive, so they miss anything
that depends on a branch your single example XR does not take.

This runs the real function body in-process against real XR YAML and prints what it
produced, so a crash or a missing field shows up in one second instead of on a live
control plane.

Usage
-----
    python3 scripts/run_function.py --project <root> examples/encryptedtable/example.yaml
    python3 scripts/run_function.py --project <root> --minimal examples/*/example.yaml

    --minimal   Also synthesise a second run with every optional top-level spec field
                stripped, keeping only what the XRD marks required. This is the branch
                that ships broken most often, because the shipped example usually sets
                every optional field.
    --function  Pick a function directory when the project has more than one.
    --json      Emit the desired-resource payload as JSON instead of a summary.

Requirements
------------
Needs the function SDK, pydantic, PyYAML, and the generated models importable. The models
come from the project's own `.up/python` tree, which this script puts on `sys.path` for
you. If the SDK is missing, the script prints the exact commands to create a venv.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# --- shared with probe_project.py -------------------------------------------------------

def find_root(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        if (d / "upbound.yaml").is_file():
            return d
    return None


def layout_of(d: Path) -> str:
    if (d / "pyproject.toml").is_file():
        return "sdk"
    if (d / "main.py").is_file():
        return "embedded"
    return "unknown"


# --- dependency check -------------------------------------------------------------------

def require_deps(root: Path, fn_dir: Path | None = None, layout: str = "unknown") -> None:
    missing = []
    for mod, pkg in (("yaml", "pyyaml"),
                     ("pydantic", "pydantic"),
                     ("crossplane.function", "crossplane-function-sdk-python")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return
    print("ERROR: missing dependencies: " + ", ".join(missing), file=sys.stderr)
    print("", file=sys.stderr)
    print("Build the venv from the PROJECT'S OWN pins. Installing the SDK by name instead "
          "gets the latest release, whose resource.update() serializes differently from the "
          "version your function is built against.", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"    python3 {Path(__file__).with_name('setup_venv.py')} --project {root}",
          file=sys.stderr)
    print("", file=sys.stderr)
    print("does all of it (and sets VS Code's interpreter). By hand:", file=sys.stderr)
    print("", file=sys.stderr)
    print("    python3 -m venv /tmp/fnprobe", file=sys.stderr)
    # A fresh 3.11 venv ships pip 23.2.1, which cannot parse the relative
    # `crossplane-models @ file:...` requirement in a generated pyproject.toml and dies with
    # "InvalidRequirement: Invalid URL given" without naming pip or the requirement.
    print("    /tmp/fnprobe/bin/pip install -q --upgrade pip", file=sys.stderr)
    if layout == "sdk" and fn_dir is not None:
        rel = fn_dir.relative_to(root) if fn_dir.is_relative_to(root) else fn_dir
        print(f"    cd {rel} && /tmp/fnprobe/bin/pip install -q -e .   # the cd matters: pip",
              file=sys.stderr)
        print("        # resolves the pyproject's relative `crossplane-models @ file:...`",
              file=sys.stderr)
        print("        # against the CWD, not against the pyproject's own directory",
              file=sys.stderr)
        print("    /tmp/fnprobe/bin/pip install -q pyyaml", file=sys.stderr)
    elif layout == "embedded" and fn_dir is not None:
        rel = fn_dir.relative_to(root) if fn_dir.is_relative_to(root) else fn_dir
        print(f"    /tmp/fnprobe/bin/pip install -q pyyaml -r {rel}/requirements.txt",
              file=sys.stderr)
    else:
        print("    /tmp/fnprobe/bin/pip install -q pyyaml pydantic "
              "crossplane-function-sdk-python", file=sys.stderr)
    print(f"    /tmp/fnprobe/bin/python {Path(__file__).resolve()} "
          f"--project {root} <example.yaml>", file=sys.stderr)
    sys.exit(2)


# --- request construction ---------------------------------------------------------------

def build_request(xr_doc: dict):
    """Wrap an XR dict in a synthetic RunFunctionRequest, as Crossplane would."""
    from crossplane.function.proto.v1 import run_function_pb2 as fnv1
    from google.protobuf import json_format, struct_pb2

    req = fnv1.RunFunctionRequest()
    req.meta.tag = "local-probe"
    struct = struct_pb2.Struct()
    json_format.ParseDict(xr_doc, struct)
    req.observed.composite.resource.CopyFrom(struct)
    return req


def _prune(value, schema):
    """Recursively keep only schema-required properties of an object value.

    A top-level-only prune is useless on the shape every Upbound project uses: the XRD
    requires `spec.parameters`, every real field lives under it, so nothing is stripped
    and the run is byte-identical to the full one. Recursing is what makes --minimal
    mean anything.
    """
    if not isinstance(value, dict) or not isinstance(schema, dict):
        return value
    if (schema.get("type") or "object") != "object":
        return value
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    if not props:
        # A free-form map (additionalProperties / x-kubernetes-preserve-unknown-fields)
        # has no required keys to speak of; keep it whole rather than emptying it.
        return value
    return {k: _prune(v, props.get(k) or {}) for k, v in value.items() if k in required}


def strip_optionals(xr_doc: dict, xrd_path: Path | None) -> dict | None:
    """Return the XR with every non-required spec field removed, at every depth.

    Returns None when there is no XRD to read, or when pruning changed nothing — an
    unchanged XR is not a minimal variant, and reporting one as if it were is a false
    coverage claim.
    """
    if xrd_path is None or not xrd_path.is_file():
        return None
    import yaml

    xrd = yaml.safe_load(xrd_path.read_text())

    # Match the example's own apiVersion. Taking the first version that happens to carry a
    # schema strips against the wrong one whenever an XRD serves more than one version —
    # dropping fields the example's version requires, or keeping fields it does not have.
    api_version = str(xr_doc.get("apiVersion", ""))
    xr_group, _, xr_version = api_version.rpartition("/")
    xrd_group = (xrd.get("spec") or {}).get("group")
    if xr_group and xrd_group and xr_group != xrd_group:
        return None

    spec_schema = None
    for ver in (xrd.get("spec", {}).get("versions") or []):
        if xr_version and ver.get("name") != xr_version:
            continue
        root_schema = ver.get("schema", {}).get("openAPIV3Schema", {}) or {}
        candidate = (root_schema.get("properties", {}) or {}).get("spec", {}) or {}
        if candidate:
            spec_schema = candidate
            break
    if spec_schema is None:
        return None

    pruned = _prune(xr_doc.get("spec") or {}, spec_schema)
    if pruned == (xr_doc.get("spec") or {}):
        # Every field in this example is required all the way down. There is no minimal
        # variant to run, and saying otherwise would be the unearned coverage claim the
        # charter exists to stamp out.
        return None

    slim = {k: v for k, v in xr_doc.items() if k != "spec"}
    slim["spec"] = pruned
    slim.setdefault("metadata", {})
    slim["metadata"] = dict(slim["metadata"])
    slim["metadata"]["name"] = (slim["metadata"].get("name", "probe") + "-minimal")[:63]
    return slim


# --- function invocation ----------------------------------------------------------------

def load_embedded_main(fn_dir: Path):
    """Import an embedded-layout `main.py` so its relative imports resolve.

    The embedded templates start with `from .model.io.upbound...`, a relative import.
    Importing `main` as a top-level module gives it no parent package, so that line dies
    with "attempted relative import with no known parent package". Registering a synthetic
    parent whose __path__ is the function directory gives `.model` something to resolve
    against, without requiring the directory to contain an __init__.py.
    """
    import importlib
    import types

    pkg_name = "_upfn_" + re.sub(r"\W", "_", fn_dir.name)
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(fn_dir)]  # noqa: A003 - namespace package by hand
        pkg.__package__ = pkg_name
        sys.modules[pkg_name] = pkg
    # Importing the project's own function is this script's purpose: it runs the code the
    # user is authoring. The name is built from the function directory, not from input.
    return importlib.import_module(f"{pkg_name}.main")  # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import


def invoke(fn_dir: Path, layout: str, req):
    """Import the function and run it, returning the RunFunctionResponse."""
    import asyncio
    import importlib

    sys.path.insert(0, str(fn_dir))
    if layout == "sdk":
        mod = importlib.import_module("function.fn")
        runner = mod.FunctionRunner()
        return asyncio.run(runner.RunFunction(req, None))
    # embedded layout: def compose(req, rsp)
    from crossplane.function import response as fnresponse

    mod = load_embedded_main(fn_dir)
    rsp = fnresponse.to(req)
    mod.compose(req, rsp)
    return rsp


def report(rsp, label: str, as_json: bool) -> None:
    from crossplane.function import resource as fnresource

    print(f"\n=== {label} ===")
    desired = rsp.desired.resources
    if as_json:
        out = {name: fnresource.struct_to_dict(r.resource) for name, r in desired.items()}
        out["__composite__"] = fnresource.struct_to_dict(rsp.desired.composite.resource)
        print(json.dumps(out, indent=2, sort_keys=True))
        return

    print(f"desired composed resources: {len(desired)}")
    for name in sorted(desired):
        d = fnresource.struct_to_dict(desired[name].resource)
        # apiVersion/kind are only reliably present on SDK >= ~0.11, which re-adds them
        # after model_dump drops them as unset model defaults. On the 0.5.0 the project
        # templates pin, both come back None for a perfectly correct function — printing
        # a bare "None None" there reads as "your function forgot the GVK". Say what is
        # actually true instead.
        gvk = " ".join(x for x in (d.get("apiVersion"), d.get("kind")) if x) \
              or "(GVK not in the desired struct — older SDK; check the model you built)"
        # Crossplane derives the name from the composition resource name, so a function
        # that leaves it unset is doing the right thing.
        mname = (d.get("metadata") or {}).get("name") or "(generated by Crossplane)"
        print(f"  [{name}] {gvk} name={mname}")
        spec = d.get("spec") or {}
        # Only managed resources have a forProvider, so only they can have a "stray" spec
        # key. A composed Deployment, Secret or child XR legitimately has spec.selector,
        # spec.template, spec.parameters and so on — warning about those is noise that
        # trains people to ignore the warning that matters.
        if "forProvider" in spec:
            stray = sorted(set(spec) - {"forProvider"})
            if stray:
                print(f"      WARNING: managed-resource spec has more than forProvider: {stray}")
                print(f"      Crossplane v2 defaults providerConfigRef/managementPolicies; "
                      f"remove them.")

    composite = fnresource.struct_to_dict(rsp.desired.composite.resource)
    status = composite.get("status") or {}
    print(f"  composite status keys: {sorted(status) or '(none)'}")
    for cond in rsp.results:
        sev = fnv1_sev(cond.severity)
        print(f"  result[{sev}]: {cond.message}")


def fnv1_sev(sev: int) -> str:
    from crossplane.function.proto.v1 import run_function_pb2 as fnv1

    return {fnv1.SEVERITY_FATAL: "FATAL",
            fnv1.SEVERITY_WARNING: "WARNING",
            fnv1.SEVERITY_NORMAL: "NORMAL"}.get(sev, str(sev))


# --- main -------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("examples", nargs="+", help="example XR YAML file(s)")
    ap.add_argument("--project", metavar="PATH", default=".",
                    help="project root (dir containing upbound.yaml); default: cwd")
    ap.add_argument("--function", metavar="NAME",
                    help="function directory name under functions/ (if more than one)")
    ap.add_argument("--minimal", action="store_true",
                    help="also run a variant with all optional spec fields stripped")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="print desired resources as JSON")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    if not project.is_dir():
        print(f"ERROR: --project path is not a directory: {project}", file=sys.stderr)
        return 10  # validation failure
    root = find_root(project)
    if root is None:
        print(f"ERROR: no upbound.yaml in {args.project} or any parent.", file=sys.stderr)
        return 2  # not found

    models = root / ".up" / "python"
    if not (models / "models").is_dir():
        print("ERROR: no .up/python/models — run `up project build` first.", file=sys.stderr)
        return 2  # not found
    sys.path.insert(0, str(models))

    fn_root = root / "functions"
    candidates = [d for d in sorted(fn_root.iterdir())
                  if d.is_dir() and layout_of(d) != "unknown"] if fn_root.is_dir() else []
    if args.function:
        candidates = [d for d in candidates if d.name == args.function]
    if not candidates:
        print("ERROR: no function directory found under functions/.", file=sys.stderr)
        return 2  # not found
    if len(candidates) > 1:
        print("ERROR: multiple functions; pass --function <name>: "
              + ", ".join(d.name for d in candidates), file=sys.stderr)
        return 10  # validation failure: ambiguous input
    fn_dir = candidates[0]
    layout = layout_of(fn_dir)
    require_deps(root, fn_dir, layout)
    print(f"project:  {root}")
    print(f"function: {fn_dir.relative_to(root)}  (layout={layout})")

    import yaml

    xrds = sorted((root / "apis").rglob("definition.yaml")) if (root / "apis").is_dir() else []
    def xrd_for(doc: dict) -> Path | None:
        """The XRD that defines this example's Kind, or None.

        With one XRD this is trivially it — strip_optionals still checks that the group and
        version match. With several, an unrelated XRD's schema would strip the wrong fields.
        """
        if len(xrds) == 1:
            return xrds[0]
        want_group = str(doc.get("apiVersion", "")).rpartition("/")[0]
        want_kind = doc.get("kind")
        for candidate in xrds:
            try:
                spec = (yaml.safe_load(candidate.read_text()) or {}).get("spec") or {}
            except Exception:
                continue
            if spec.get("group") == want_group and (spec.get("names") or {}).get("kind") == want_kind:
                return candidate
        return None

    failures = 0
    missing_examples = 0
    for ex in args.examples:
        ex_path = Path(ex)
        if not ex_path.is_absolute():
            ex_path = root / ex
        if not ex_path.is_file():
            print(f"ERROR: no such example: {ex_path}", file=sys.stderr)
            missing_examples += 1
            continue
        doc = yaml.safe_load(ex_path.read_text())
        runs = [(ex_path.name, doc)]
        if args.minimal:
            slim = strip_optionals(doc, xrd_for(doc))
            if slim:
                runs.append((f"{ex_path.name} [MINIMAL: only XRD-required spec fields]", slim))
            else:
                print("NOTE: --minimal needs exactly one apis/*/definition.yaml with "
                      "spec.required, or every field in the example is required all "
                      "the way down; skipping the minimal variant.")
        for label, d in runs:
            try:
                rsp = invoke(fn_dir, layout, build_request(d))
                report(rsp, label, args.as_json)
            except Exception as exc:  # noqa: BLE001 - this is the whole point
                failures += 1
                print(f"\n=== {label} ===")
                print(f"  FUNCTION RAISED {type(exc).__name__}: {exc}")
                import traceback

                traceback.print_exc()

    print()
    if missing_examples and not failures:
        print(f"{missing_examples} example file(s) not found.")
        return 2  # not found
    if failures:
        print(f"{failures} run(s) failed. A green `up project build` would not have "
              f"told you this.")
        return 1  # the function itself failed
    print("all runs completed without raising. Read the output above — completing without "
          "an exception is not the same as emitting the right resources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
