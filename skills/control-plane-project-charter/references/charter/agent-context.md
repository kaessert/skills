# Agent context: the user's conversation vs a delegated run

Which kind of agent you are, and what each kind may and may not do. [The charter §1](../../SKILL.md#1-know-which-kind-of-agent-you-are) states the rule; this is the detail.

---

### In the user's conversation

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
- **One exception.** If the conversation you are in belongs to a delegated agent rather than
  the user — `execute-v2-migration` usually runs that way — it cannot reach the user either,
  so a question there ends *its* turn. State the assumption you would ask about and proceed.

**Your work is visible.** Every command you run and every file you write lands in the
caller's context, so your summary points at evidence they already have rather than standing
in for it. That removes the temptation, but not the discipline in §4.

### As a delegated agent

- **Your only caller is another agent** executing a task. It cannot answer an interview.
- **You run in an isolated context.** You do not see the caller's conversation and do not
  know where the project is unless you look. Never search the current working directory
  blindly — it may be an unrelated repository.
- **Asking a question ends your turn.** The run terminates and hands the caller a result
  for work that never happened. An interview is a failed run that reports success. Waiting
  for your result changes *when* the caller receives it, not whether you can reach the user.
  You cannot.

**Act on the brief you were given, discover the rest from the project, and do the work.** Ask
only when a genuinely irreversible decision is undetermined — publishing a package, or
deleting something — and then state the assumption you would otherwise make. Prefer
proceeding with a stated assumption over stopping.

**Your only output channel is prose.** The caller cannot see your exit codes, your
`render.log`, or your resource tree. That is exactly why §4 exists.
