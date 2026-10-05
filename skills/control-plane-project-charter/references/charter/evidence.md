# Reading a render, and making a suite exhaustive

How to find what a function actually emitted, how `assertResources` matches, and the one assertion that catches a surplus resource. [`control-plane-project-charter` §8](../../SKILL.md#8-a-green-run-is-not-evidence) states the rule.

---

**To find what a function actually emitted**, read the render rather than the assertions:

```bash
up test run "tests/<t>" --function-logs
# the run prints: Test artifacts written to <dir>
grep -h "composition-resource-name:" <dir>/*/render.log | sort
```

Three things about that path, each of which has cost a wasted attempt:

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

That lists every resource the function produced, including the ones nothing asserts (pipe to
`grep -c` if you want a count — resource names are unique, so `uniq -c` only ever prints 1). A
new resource is untested until it is named in an assertion.

### How `assertResources` matches, and how to make a suite exhaustive

An expected resource is matched on **`apiVersion` + `kind` + `metadata.name`**. Leave
`metadata.name` **out** of the expectation unless your function sets it: Crossplane derives the
name (§5), so you cannot know it, and an omitted name matches whatever was rendered. A failure
to match reads as `no actual resource found: <group>/<version>/<Kind>/<name>` — a trailing
slash means the expectation named no name.

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

**A generated name is safe to hardcode here**, even though §5 warns those names are not stable
across re-creations. That warning is about a live control plane, where the XR's uid is real.
A render has no live XR, so the renderer synthesizes a *deterministic* uid — measured
identical across repeated runs, which makes the composed names identical too
(`example-2a20761a185a` on every run). Copy the names out of a render and assert them.

The hash covers the XR's name and each composition resource name, so renaming either changes
every generated name — which is correct, because renaming a composition resource orphans
resources on a live platform (§5) and you want a test that says so.
