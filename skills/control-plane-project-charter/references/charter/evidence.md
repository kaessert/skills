# Reading a render, and making a suite exhaustive

What a clean `up project build` checks per language, how to find what a function actually emitted, how `assertResources` matches, the one assertion that catches a surplus resource, and what a suite must contain. [`control-plane-project-charter` §8](../../SKILL.md#8-a-green-run-is-not-evidence) states the rule.

---

### What a clean `up project build` checks

The package was assembled; a clean build never proves the function *runs*. Per language:

- **KCL and single-file Python:** nothing is imported, type-checked or executed — a function
  with an `AttributeError` on its normal path builds cleanly.
- **Python SDK layout:** the builder runs `hatch build` + `pip install`, so packaging and
  dependency errors fail, but `fn.py` is still never imported.
- **Go:** the build runs `go mod tidy` and a real compile, so a Go function that does not
  compile fails here.

---

**To find what a function actually emitted**, read the render rather than the assertions:

```bash
up test run "tests/<t>" --function-logs
# the run prints: Test artifacts written to <dir>
grep -h "composition-resource-name:" <dir>/*/render.log | sort
```

Three things about that path:

- **`--function-logs` is what writes the artifacts.** `--output-dir` alone writes nothing — it
  only changes the base directory. `--function-logs` is also rejected outright with `--e2e`.
  A plain `up test run` writes no `_output/composition_test/<ts>/`, so any directory already
  there is stale: re-run with `--function-logs` before reading `render.log`.
- **Do not construct the path.** The directory carries a `YYYYMMDD-HHMMSS` timestamp you cannot
  know in advance; the run prints it.
- **One test *directory* produces one subdirectory per `CompositionTest`**, named for the
  object's `metadata.name`, not the directory's. `tests/test-storagebucket/` with two tests
  yields `test-storagebucket-bucket-created/` and `test-storagebucket-bucket-not-yet-created/`.
  Glob the run directory rather than guessing a name.

That lists every resource the function produced, including the ones nothing asserts; `uniq -c`
adds nothing, since every name is unique. A new resource is untested until it is named in an
assertion.

### How `assertResources` matches, and how to make a suite exhaustive

An expected resource is matched on **`apiVersion` + `kind` + `metadata.name`**. For the name:

- **Your function sets it:** assert it.
- **Crossplane generates it, and the kind appears once in the render:** omit `metadata.name`.
  An omitted name matches whatever was rendered.
- **Crossplane generates it, and the kind appears more than once:** assert each one by the name
  copied from the render, so each expectation matches exactly one resource.

**A generated name copied from a render is stable in a render.** §5's warning that generated
names change across re-creations is about a live control plane, where the XR's uid is real. A
render has no live XR, so the renderer synthesizes a deterministic uid — measured identical
across repeated runs, which makes the composed names identical too (`example-2a20761a185a` on
every run).

The hash covers the XR's name and each composition resource name, so renaming either changes
every generated name — which is correct, because renaming a composition resource orphans
resources on a live platform (§5) and you want a test that says so.

A failure to match reads as `no actual resource found: <group>/<version>/<Kind>/<name>` — a
trailing slash means the expectation named no name.

Because `assertResources` ignores what it does not list, a *surplus* resource is invisible: a
function that composes a resource it should have skipped leaves the suite green. Assert the
composite's **`spec.crossplane.resourceRefs`** to close that. It is a list, and lists are
matched exactly in length and order, so an unexpected resource fails it:

```
* spec.crossplane.resourceRefs: Invalid value: [...]: lengths of slices don't match
```

This is the one assertion that catches a resource nothing else names. Its order is the
renderer's and is not part of any published contract — a reordering upstream breaks the
assertion loudly rather than letting a real surplus through, which is the safe direction.

**That covers surplus resources, not absent fields.** `assertResources` has no absence
operator, so "this field is not set" cannot be asserted in a composition test, and searching
the CLI for one is wasted time. Assert it in a unit test on the function's desired state, in
the function's own language, or confirm it once in `render.log` and report it as not asserted.

### Coverage: what the suite must contain

The scaffold generates **one** test, against **one** example XR, asserting **only** composed
resources. That suite is green over a function that crashes on a minimal XR, silently drops
status fields, and never runs its readiness branch. "The tests pass" is not a verification
claim until the suite covers these three shapes. Each language file shows them in its own
syntax (Python: `languages/python/tests.md`; Go: `languages/go/tests.md`; YAML:
`languages/yaml.md`).

**1. One test per input shape — including a minimal XR.** Use the inline `xr` field instead of
`xrPath`, with only the XRD-required fields set and every optional one omitted; you do not need
a second example file. Inline `xr` and `xrPath` are mutually exclusive, so a test helper that
takes `xrPath` needs an `xr` parameter, never both at once. This is where "the user wrote the
obvious minimal manifest" bugs live: the shipped example usually sets every optional field, so
the omitted branch never renders.

**2. One test per observed-state branch.** Code gated on observed resources or on readiness
**never executes** when `observedResources` is empty — it is unexercised, not merely
unasserted. Supply the observed state explicitly:

- Every observed resource needs the `crossplane.io/composition-resource-name` annotation: the
  renderer rejects the whole test without it (`encountered composed resource without required
  "crossplane.io/composition-resource-name" annotation`). It is required, but it is **not** what
  matches a mock to the XR's composed resource.
- **For a namespaced XR, every `observedResources` entry also needs `metadata.namespace` set to
  the XR's namespace, and `metadata.name` set to the name the render gave that resource.** Copy
  the names from `render.log` (run with `--function-logs`, above); they are stable in a render.
  A mock without the XR's namespace is silently not observed: no error, the function sees no
  observed resources, and the test fails only on its own assertions, as if the function were
  wrong (observed with up v0.55.0).
- **Prove the mocks are used** with a case that fails when they are ignored: assert a value only
  an observed resource can supply, such as a status field copied from a mock. A case that
  expects empty or default status passes whether the mocks are observed or not.
- Without `status.conditions` the resource is observed but **not** ready, which is its own
  useful test case. Add `Ready` and `Synced` conditions with status `True` to drive the ready
  branch.

Writing *observed but not ready* and *observed and ready* as two cases is what separates a
readiness check from an existence check in your assertions; with only the ready case, a
function that never checks readiness passes.

**3. Assert every `status` field the function writes, on the composite.** `assertResources`
matches the composite ([§8](../../SKILL.md#8-a-green-run-is-not-evidence)). Without this, a
status write that clobbers nested keys — writing the status more than once can drop all but the
last (Go: `languages/go/functions.md`, several status fields) — passes silently, and you blame
the provider.

Other inline fields worth knowing, all optional: `composition` and `xrd` (inline instead of
`*Path`), `extraResources`, `context`, and `functionCredentialsPath`.

**A conditional resource needs all three:**

1. A test for the omitted case asserting the resources that *should* be there. This catches
   crashes on that branch — the common failure — and is a real regression guard.
2. A **`resourceRefs` assertion on the composite** (above), which turns absence into a real
   automated guard: a surplus resource fails the list comparison.
3. A read of `render.log` confirming the conditional resource is absent, quoted in your
   summary — that is where you get the `resourceRefs` order from anyway.

Report it accurately. With a `resourceRefs` assertion: *"test 4 covers the
omitted-lifecycleRules branch; the composite's resourceRefs assertion fails if a lifecycle
resource appears."* Without one: *"absence was confirmed once by reading render.log and is not
asserted by the suite."* Never *"validates that no lifecycle resource is created"* unless
something actually fails when one is.

**Out of scope for any composition test.** Assertions are partial-positive, so a *stray*
field — an external-name annotation on a resource whose external name the provider assigns —
is never flagged. That class fails only on a live control plane.
