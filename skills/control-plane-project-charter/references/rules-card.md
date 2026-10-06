# Rules card

The charter on one screen. **Read the card — between the two `---` lines below — when you
build, and the reviewer variant when you review**, whether or not a prompt included them. An
orchestrator can also paste them into agent prompts: loading a task skill does not load the
charter, so pasting reaches agents that never open it. Section numbers (§N) are the charter's
(`../SKILL.md`), which holds the reasons; the skills hold the checklists.

---

**If this card conflicts with the project's spec, the spec wins; say so.**

**Asking and deciding**
- Discover from the project before asking. When nobody can answer, never block: decide from
  the project's spec and state the assumption, or stop and report the open question (§1, §2).
- The project's own decisions — design document, work item, gate script — win over skill
  defaults. Say where you departed from a default and why (§2).
- Long runs lose old output. Before you write anything derived from a document — a work item,
  a test expectation, a quote, a field value — re-read the section you rely on in that step.
  Never quote from memory; if the re-read contradicts what you wrote, fix it first (§1).

**Building**
- New tests use the language of the existing `CompositionTest`/`E2ETest` dirs, else the
  composition language, else YAML. A program printing `items: []` is no test and sets
  nothing (§10).
- In a v2 project, managed resources carry `forProvider` only, on the `.m.` API groups, unless
  the project's spec or API sets more: no `deletionPolicy`, `managementPolicies` or
  `metadata.namespace`; omit `providerConfigRef` if and only if `ClusterProviderConfig/default`
  exists and is the right one. A v1 project keeps its v1 APIs; migrating it is separate work.
  Objects embedded in `forProvider`, such as a provider-kubernetes manifest, still need their
  own `metadata.namespace` (§5).
- The provider schema is a lower bound: check the cloud API's own rules (name formats,
  reserved prefixes, create-only fields) (§6).
- Test first: watch every new composition or unit test fail for the right reason before making
  it pass; for a new E2ETest this is optional. A broken test is not RED, even when it exits 1 —
  that includes a bug in the test's own logic (§3).
- Backfilling a test for working code: mutate the implementation, never the test's expected
  value, see the test go red, then revert (§3).
- Every value the function passes through gets, in at least one test, a value that is not the
  default and no sibling field shares; otherwise a hard-coded constant stays green (§3, `charter/tdd.md`).
- Never create a group, Space, control plane or cloud resource as a side effect; what you were
  asked to run (an E2E test, a deploy) is not one. Never pass `--public` yourself (§9).
- The composition gate is `up test run "tests/test-*"`: `up test run` runs every matched test
  program, e2e ones too even without `--e2e`, and one failing program fails the whole run.
  Name test inputs `UP_*`; only those reach KCL and Python programs (§7).

**Reporting**
- Name what ran and its exit code — the command's own, not that of a `| tail` after it
  (`${PIPESTATUS[0]}`, or redirect to a file and read `$?`). No command, no claim (§4).
- `up test run` printing `No test files found` means nothing ran, though it exits 0. A test
  program that prints `items: []` contributes zero tests (§8).
- For every new test, name the code change that turns it red, and say whether you saw it
  fail. Otherwise call the test unproven (§4, §8).
- Name the layer you reached — render, composition test, local control plane, cloud — and
  never claim one you did not reach (§4, §8).
- Comments, docs and READMEs claim no more than a named test or run (§4).

---

**Reviewer variant.** If this conflicts with the project's spec, the spec wins; say so.
- Re-run the gate yourself and read its output. `No test files found`, or a test program
  printing `items: []`, is zero tests: no vacuous green counts as a pass (§8).
- For each new test, the report names the implementation change that turns it red, and it was
  seen failing; an E2ETest may instead be reported unproven. Check one yourself; mutating the
  expected value does not count (§3, §4).
- The spec's requirements are met where they depart from skill defaults, and the departure is
  stated (§2).
- Re-read the spec section before you write a finding from it, never quote from memory, and
  check every quoted spec sentence verbatim against the spec, wherever it is quoted (§1).
- Flag `providerConfigRef`, `managementPolicies` or MR `metadata.namespace` as removable unless
  the project's spec or API sets them; flag `providerConfigRef.kind: ProviderConfig` as a bug
  only when no namespaced `ProviderConfig` of that name exists in, or is created in, the XR's
  namespace (§5).
- Flag an unbounded dependency: a `dependsOn` `version` with no cap on the major, such as the
  `'>=v0.0.0'` a bare `up dep add <ref>` writes (author-configuration-package).
- The report names the layer reached — render, composition test, control plane, cloud — and
  claims nothing beyond it (§4, §8).
