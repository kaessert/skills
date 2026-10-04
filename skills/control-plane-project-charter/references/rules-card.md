# Rules card

The charter on one screen, for an orchestrator to paste into an agent's instructions when
loading the full skills on every short session costs too much. It is a reminder, not a
replacement: the reasons and the evidence are in the charter (`../SKILL.md`), and the skills
hold the checklists.

**Asking and deciding**
- Discover from the project before asking. When nobody can answer, never block: decide from
  the project's spec and state the assumption, or stop and report the open question (§1, §2).
- The project's own decisions — design document, work item, gate script — win over skill
  defaults. Say where you departed from a default and why (§2).
- Never create a group, Space, control plane or cloud resource as a side effect (§9).

**Building**
- Test first: watch every new test fail for the right reason before making it pass (§3).
- Managed resources carry `forProvider` only. No `deletionPolicy`, no `managementPolicies`,
  no `metadata.namespace`; omit `providerConfigRef` if and only if
  `ClusterProviderConfig/default` exists and is the right one (§5).
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
