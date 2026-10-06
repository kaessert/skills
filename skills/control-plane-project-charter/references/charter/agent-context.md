# Agent context: inline vs forked

Which kind of agent you are, and what each kind may and may not do. [`control-plane-project-charter` §1](../../SKILL.md#1-know-which-kind-of-agent-you-are) states the rule; this is the detail.

---

### Inline — you expand into the caller's conversation

You share their context and their working directory, and you can ask.

- **Read the conversation before you go looking.** The caller has usually already
  established the project root, the language, the provider family and the target context.
- **Ask when a decision is genuinely undetermined.** A question costs one turn and reaches
  the user. Guessing costs a rebuild, a suite written against the wrong shape, or a resource
  the provider rejects. Ask about decisions — is this list one aggregate resource or N,
  which layout, which region — never about what the project can tell you (§2).
- **Unless nobody can answer** — a caller that is itself a forked agent, or a run with no user
  in the loop. Then §1's never-block rule applies.

**Your work is visible.** Every command you run and every file you write lands in the
caller's context, so your summary points at evidence they already have rather than standing
in for it. That removes the temptation, but not the discipline in §4.

### Forked — you are a separate agent and cannot hold a conversation

- **Your only caller is another agent** executing a task. It cannot answer an interview.
- **You run in an isolated context.** You do not see the caller's conversation and do not
  know where the project is unless you look. Never search the current working directory
  blindly — it may be an unrelated repository.
- **Asking a question ends your turn.** The fork terminates and hands the caller a result
  for work that never happened: an interview is a failed run that reports success. A caller
  that waits for you changes when it gets your result, not whether you can reach the user.

**Act on the brief you were given, discover the rest from the project, and do the work.**
Prefer proceeding with a stated assumption over stopping. The exception is an irreversible
decision nobody made — publishing a package, deleting something: do not make it; stop and
report it as the open question, with the assumption you would otherwise have made.

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
- **Long commands keep a timeout that fits them.** Whatever runs a command, in the background or
  not, must not have a shorter timeout than the command's worst case: set it on the call itself.
  A killed `up` run can leave its kind cluster or containers behind (observed: a background E2E
  run cut off by a default command timeout leaked its kind cluster and registry; a composition
  gate over 9 test directories was cut off the same way, likely leaving its render containers).
- **Checking on and stopping a background run** means reading its output so far and
  stopping it with your harness's own tools. A foreground run has nothing to check on.
