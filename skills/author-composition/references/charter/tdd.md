# The inner loop, and backfilling tests

How to iterate without paying a full build every time, and how to add tests to code that already works. [`../charter.md` §3](../charter.md#3-develop-test-first-red--green--refactor) states the discipline.

---

### The two-tier inner loop

**Every `up test run` pays a full project build** — schema generation, dependency check,
function build, package build, push to the local daemon. There is no flag to skip it;
`--no-build-cache` only makes it slower. Measured on a warm cache: ~12-16s for a one-function
**KCL** project, and **11-50s for Python**, scaling with the number of test cases (11s for two,
36s for six, on one embedded function) — minutes when dependencies have to be pulled. Use both
tiers:

| Tier | ~time | Catches |
|---|---|---|
| Fast — run the function body directly, if the language offers a way (see [`languages/`](../languages/)) | ~1s | exceptions, wrong resource count, missing fields, the minimal-XR branch |
| Assertion — `up test run "tests/<t>"` | tens of seconds warm, minutes cold | everything the suite asserts — this is the one that goes RED and GREEN |

The fast tier asserts nothing, so it never replaces the RED/GREEN cycle; it just stops you
paying a whole build to discover a typo.

### Backfilling tests for code that already exists

Migrations, coverage work and "add a test for this" all start from working code, so there is
no natural RED. That is fine — but a test written against passing code has never been
observed to fail, and is exactly where the false coverage claims come from.

**Prove it can fail with a deliberate mutation.** Break the thing the test is supposed to
catch, confirm *that test* goes red while the others stay green, then revert:

```bash
# 1. mutate the implementation (delete the field, move the block below an early return, ...)
up test run "tests/*"     # expect: exactly the new test fails, and it names the right field
git checkout -- <the file you mutated>
up test run "tests/*"     # expect: green again
```

Report which mutation you used and which tests it turned red. *"Moving the lifecycle block
below the versioning guard turned test 3 red and left the other three green"* is a coverage
claim with evidence behind it. *"Coverage: complete"* is not.

If a mutation you expected to break the test leaves the suite green, the test does not cover
what you thought — say so rather than reporting the coverage.
