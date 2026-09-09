<!-- mth_version: 31_pipeline_source.v1 -->

# CLAUDE.md

Every line here binds a session unless marked *convention*. Restructured 2026-09-03: this file holds
only what **every** session needs; what a role needs is in its briefing.

---

## 1. Why, what, and the goal

`00_methodology/world_model.md` §1–§2 — the gap the pipeline closes, what it does, the goal, the one number,
and what it deliberately does not do. The Owner's full specification is in `20_target_picture`
(`00_methodology/project_layout.md` says which file is active).

---

## 2. Way of working, and what to read

Research and concept chats run in **Claude Cowork**; the Product Manager runs in Claude Cowork and
writes the work orders; implementation, test and acceptance run in **Claude Code**, agentically, and
may create new role instances.

**Every session reads the standard set, in this order, and nothing else unasked:**

| document | what it settles |
|---|---|
| `../methodology/operating manual.md` | the cycle, who decides, the finding schema, document types — the portable kernel |
| `00_methodology/project_layout.md` | the directory table — where this project keeps what the kernel names |
| `00_methodology/team_roles.md` | the roster, and the rules every role shares |
| `00_methodology/briefings/<your role>.md` | your charter, **what you read beyond this table**, what you return |
| `00_methodology/world_model.md` §1–§5 | what the pipeline is and the order the research is done in — a planner reads all of it; a builder is handed §6 Invariants |

**Nothing ships on one mind.** Every concept and every piece of code gets a critical read by a second,
independent instance before it counts — the rule row in `00_methodology/team_roles.md` says who names
the reader and where the verdict lands.

Everything else — `../methodology/_creating_a_role.md`, `briefings/_build_and_release.md`,
`../methodology/multi_agent_collaboration_best_practices.md`, `src/pipeline/PACKAGE_RULES.md`, the two naming
standards, the skills — is named in the briefing of the role that needs it, and read by no one else.
A created instance is handed its briefing whole; how, is in `../methodology/_creating_a_role.md`.

---

## 3. Change discipline — against over-delivery and over-complexity

Over-delivery is a measured property of every coding model, including this one: verbosity and
structural erosion rise over long tasks, and an instruction at the start reduces the starting level
but not the rate. So this section is re-read, not remembered.

**Over-delivery is a defect, not enthusiasm.** The test is not *is this good?* but *what would a
person with limited time and no interest in impressing anyone have done here?*

1. **Build the smallest thing that satisfies the definition of done.** Anything beyond it is a
   proposal stated in one sentence, not a change made.
2. **Prefer editing a file to adding one.** A new file needs a reason you can say out loud.
3. **Do not abstract to avoid duplication until the duplication has caused a bug.** Three copies of
   thirty lines is fine; a layer of indirection to save them usually is not.
4. **When the Owner names a shape** — three files, one section, two commands — **build that shape.**
   If you think it is wrong, say so in one sentence and build it anyway unless he agrees.
5. **Answer in the length the question deserves.** Long explanation is the same failure in prose.
   *A judgement — self-applied; no reader.*
6. **Re-check size against the previous turn, not against the start.** The drift is per turn; the
   Architect's complexity note reads for it.
7. **No new toggle and no new threshold** unless it names the failure it prevents.
8. **Run what you wrote before handing it over.** A criterion is met when its command has been run
   and its output recorded — and a builder's own green is a claim until a verifier has pasted it.

**The one thing never to trim: honesty about what you did not verify.** Cutting scope is good;
cutting the sentence *this has never actually been executed* is not. Every return ends with one line
per check that could not run.
