# Refactoring a test suite

Read before planning or executing a test refactor. Planning writes a plan and stops; executing
does one item per run.

## Planning

1. Analyze the `tests/` directory structure.
2. Identify duplication and consolidation opportunities (the structuring patterns in
   [test-model.md](test-model.md#patterns)).
3. Create `.agents/tasks/REFACTOR_TESTS.md` with prioritized items, from the template below.
4. Do not execute: report the plan and how to proceed.

## Executing

1. Check for `.agents/tasks/REFACTOR_TESTS.md`.
2. If it is missing, do the Planning steps above and stop there; report the plan rather than
   executing it (charter §1: never block on a question nobody can answer).
3. Execute only the highest-priority unchecked item.
4. Run the gate once the suite is green, as in SKILL.md Phase 6: the project's own gate if it
   has one, else `verify-configuration`. E2E or a deploy only where the project, the user or
   your instructions allow it (charter §9).
5. Mark the item complete with the date.
6. Report completion and the next item.

## Plan template

Create at `.agents/tasks/REFACTOR_TESTS.md`:

```markdown
# Test Refactoring Plan

Last updated: YYYY-MM-DD

## High Priority

- [ ] **P1: [Title]** - [Description] (reduces [metric] by [amount])
- [ ] **P2: [Title]** - [Description]

## Medium Priority

- [ ] **P3: [Title]** - [Description]
- [ ] **P4: [Title]** - [Description]

## Low Priority

- [ ] **P5: [Title]** - [Description]

## Completed

- [x] **P0: Initial analysis** - Identified refactoring opportunities (YYYY-MM-DD)
```
