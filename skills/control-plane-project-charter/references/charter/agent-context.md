# Agent context: inline vs forked

Which kind of agent you are, and what each kind may and may not do. [`control-plane-project-charter` §1](../../SKILL.md#1-know-which-kind-of-agent-you-are) states the rule; this is the detail.

---

### Inline — you expand into the caller's conversation

You share their context and their working directory, and you can ask.

- **Read the conversation before you go looking.** The caller has usually already
  established the project root, the language, the provider family and the target context.
  Re-deriving those is the hillclimbing these skills exist to remove.
- **Ask when a decision is genuinely undetermined.** A question costs one turn and reaches
  the user. Guessing costs a rebuild, a suite written against the wrong shape, or a resource
  the provider rejects. Ask about decisions — is this list one aggregate resource or N,
  which layout, which region — never about things the project can tell you.
- **Do not ask what you can discover.** Layout, model paths, existing dependencies, current
  context: look, do not interview.
- **Unless nobody can answer.** If your caller is itself a forked agent — `execute-v2-migration`
  can run that way — it cannot reach the user either, so a question there terminates *its* turn.
  The same holds in an autonomous run with no user in the loop. In both cases, decide from the
  project's own spec and state the assumption you made, or stop and report the open question
  as your result. Never block on a question nobody can answer.

**Your work is visible.** Every command you run and every file you write lands in the
caller's context, so your summary points at evidence they already have rather than standing
in for it. That removes the temptation, but not the discipline in §4.

### Forked — you are a separate agent and cannot hold a conversation

- **Your only caller is another agent** executing a task. It cannot answer an interview.
- **You run in an isolated context.** You do not see the caller's conversation and do not
  know where the project is unless you look. Never search the current working directory
  blindly — it may be an unrelated repository.
- **Asking a question ends your turn.** The fork terminates and hands the caller a result
  for work that never happened. An interview is a failed run that reports success. This
  holds regardless of whether the caller waits for you — waiting changes *when* the caller receives your
  result, not whether you can reach the user. You cannot.

**Act on the brief you were given, discover the rest from the project, and do the work.** Ask
only when a genuinely irreversible decision is undetermined — publishing a package, or
deleting something — and then state the assumption you would otherwise make. Prefer
proceeding with a stated assumption over stopping.

**Your only output channel is prose.** The caller cannot see your exit codes, your
`render.log`, or your resource tree. That is exactly why §4 exists.

---

### Delegation and long runs, whatever your harness supports

Some skills hand work to a sub-agent (a brief for another skill) or run a long command in
the background (an E2E test). Neither is a tool name; use whatever your harness provides.

- **Handing work to a sub-agent.** If you can start a separate agent, do — loading the skill
  into your own context instead is not the same thing: its long output lands in the user's
  conversation. Give the agent the brief as written and wait for its result. If you cannot, follow the brief yourself, in this
  conversation: load the skill it names and do the work. You are then inline, not forked,
  and the inline rules above apply. Either way the brief must stand on its own — name the
  tests, files and functions it is about rather than leaving the other skill to choose.
- **Running a command in the background.** If your harness can run a command in the
  background, tell you when it exits, and show its output so far, use that. If it cannot,
  run the command in the foreground with the longest timeout your shell allows — do not
  detach it yourself with `nohup` or `&` and poll for it. If that
  timeout ends the run first, report the run as *cut off* and what it had reached — a run
  that did not finish has no outcome to report.
- **Checking on and stopping a background run** means reading its output so far and
  stopping it with your harness's own tools. A foreground run has nothing to check on.
