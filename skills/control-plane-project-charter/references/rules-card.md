# Rules card

The charter on one screen, for an orchestrator to paste into an agent's instructions. Loading
a skill does not load the charter, and agents often skip it, so pasting is the reliable route.
Paste the card — between the two `---` lines below — into prompts for agents that build, and the
reviewer variant into prompts for agents that review. Section numbers (§N) are the charter's.
It is a reminder, not a replacement: the reasons and the evidence are in the charter
(`../SKILL.md`), and the skills hold the checklists.

---

**If this card conflicts with the project's spec, the spec wins; say so.**

**Asking and deciding**
- Discover from the project before asking. When nobody can answer, never block: decide from
  the project's spec and state the assumption, or stop and report the open question (§1, §2).
- The project's own decisions — design document, work item, gate script — win over skill
  defaults. Say where you departed from a default and why (§2).
- Never create a group, Space, control plane or cloud resource as a side effect (§9).

**Building**
- Test first: watch every new test fail for the right reason before making it pass. A broken
  test is not RED, even when it exits 1 — that includes a bug in the test's own logic (§3).
- Backfilling a test for working code: mutate the implementation, never the test's expected
  value, see the test go red, then revert (§3).
- New tests use the language of the existing `CompositionTest`/`E2ETest` dirs, else the
  composition language, else YAML. A program printing `items: []` is no test and sets
  nothing (§10).
- Managed resources carry `forProvider` only, unless the project's spec or API sets more. No
  `deletionPolicy`, no `managementPolicies`, no `metadata.namespace`; omit `providerConfigRef`
  if and only if `ClusterProviderConfig/default` exists and is the right one (§5).
- Use the namespaced `.m.` API groups. Objects embedded in `forProvider`, such as a
  provider-kubernetes manifest, still need their own `metadata.namespace` (§5).
- The provider schema is a lower bound: check the cloud API's own rules (name formats,
  reserved prefixes, create-only fields) (§6).

**Reporting**
- Name what ran and its exit code — the command's own, not that of a `| tail` after it
  (`${PIPESTATUS[0]}`, or redirect to a file and read `$?`). No command, no claim (§4).
- `up test run` printing `No test files found` means nothing ran, though it exits 0. A test
  program that prints `items: []` contributes zero tests (§8).
- For every new test, name the code change that turns it red, and say whether you saw it
  fail. Otherwise call the test unproven (§4, §8).
- Name the layer you reached — render, composition test, local control plane, cloud — and
  never claim one you did not reach (§4, §8).
- Comments and docs claim no more than the test checks (§4).

---

**Reviewer variant.** If this conflicts with the project's spec, the spec wins; say so.
- Re-run the gate yourself and read its output. `No test files found`, or a test program
  printing `items: []`, is zero tests: no vacuous green counts as a pass (§8).
- For each new test, the report names the implementation change that turns it red, and it was
  seen failing. Check one yourself; mutating the expected value does not count (§3, §4).
- The spec's requirements are met where they depart from skill defaults, and the departure is
  stated (§2).
- Flag `providerConfigRef`, `managementPolicies` or MR `metadata.namespace` as removable unless
  the project's spec or API sets them; flag `providerConfigRef.kind: ProviderConfig` as a bug
  only when no namespaced `ProviderConfig` of that name exists in, or is created in, the XR's
  namespace (§5).
- The report names the layer reached — render, composition test, control plane, cloud — and
  claims nothing beyond it (§4, §8).
