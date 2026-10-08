# Agent context: inline vs forked

Which kind of agent you are, and what each kind may and may not do. [`control-plane-project-charter` §1](../../SKILL.md#1-know-which-kind-of-agent-you-are) states the rule; this is the detail.

---

### Inline and forked

- **Inline** (in the caller's conversation): read the conversation before you go looking — it
  usually has the project root, the language and the target. Ask about decisions the project
  cannot answer (one aggregate resource or N, which region), never about what it can (§2).
- **Forked** (a separate agent): you do not see the caller's conversation, so find the project
  rather than searching the working directory blindly; it may be an unrelated repository.
  Asking ends your turn and hands back a result for work that never happened. Act on the brief
  with stated assumptions — except an irreversible decision nobody made (publishing a package,
  deleting something): stop and report it as the open question. Your only output channel is
  prose: the caller sees no exit code, `render.log` or resource tree, which is why §4 exists.

---

### Delegation and long runs, whatever your harness supports

Some skills hand work to a sub-agent (a brief for another skill) or run a long command in
the background (an E2E test). Neither is a tool name; use whatever your harness provides.

- **Handing work to a sub-agent.** If you can start a separate agent, do: loading the skill
  into your own context instead puts its long output in the user's conversation. Give the
  agent the brief as written and wait for its result. If you cannot, follow the brief
  yourself, in this conversation: load the skill it names and do the work. You are then
  inline, not forked, and the inline rules above apply. Either way the brief must stand on its
  own — name the tests, files and functions it is about rather than leaving the other skill to
  choose.
- **Running a command in the background.** If your harness can run a command in the
  background, tell you when it exits, and show its output so far, use that. If it cannot,
  run the command in the foreground with the longest timeout your shell allows — do not
  detach it yourself with `nohup` or `&` and poll for it. If that timeout ends the run first,
  report the run as *cut off* and what it had reached: a run that did not finish has no
  outcome to report.
- **Long commands keep a timeout that fits them.** In the background or not, the call's
  timeout must be no shorter than the command's worst case: set it on the call itself. A
  killed `up` run can leave its kind cluster or containers behind (observed: a background E2E
  run cut off by a default command timeout leaked its kind cluster and registry; a composition
  gate over 9 test directories was cut off the same way, likely leaving its render containers).
- **Checking on and stopping a background run** means reading its output so far and
  stopping it with your harness's own tools. A foreground run has nothing to check on.
