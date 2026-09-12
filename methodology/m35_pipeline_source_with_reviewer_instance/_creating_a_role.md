# Creating and running a role

*Read by the Product Manager and the Release Engineer — the two seats that create instances — and
handed to every instance they create, because a created instance may not create another.*

## Who may create a role
- The **Product Manager** may create any role, on either surface.
- The **Release Engineer** may create roles **in Claude Code** for implementation, test and
  acceptance — including the verifier instance every build hands its gate to.
- **No other role creates one.** A seat that needs a role that does not exist asks the Product Manager.

## What a created instance is given — and nothing else
1. `CLAUDE.md` by path — it reads the standard set `CLAUDE.md` §2 names itself (the manual, the roster, `project_layout.md`, the world model).
2. **Its briefing, `briefings/<role>.md`, pasted whole** — charter, reads, returns. Never the roster:
   it drifts from the file and costs context every cycle.
3. `world_model.md` §1–§5 by path; **§6 Invariants pasted if it builds**; all of it if it plans.
4. Its **seat knowledge base**, by path, named in its briefing.
5. The **task**: one artefact, one question, and only the backlog or feedback lines that bear on it.

The verifier is the exception to this list: it is given `kernel/verifier.md` and the gate
command — which carries its own environment activation — nothing more.

## Who is deliberately kept in the dark

- **Reviewers do not read each other.** Already the rule; it is repeated here because it is the
  one most often broken by pasting one review into another's prompt.
- **A reviewer sees the artifact and its behaviour, not the reasoning behind it.** Give a
  reviewer the plan and the assumptions and it starts explaining the code instead of attacking
  it. The role stops being worth its cost.
- **A builder sees the acceptance criteria but never the expected values.** These are different
  things and conflating them fails in both directions. *What must be true at the end* — which
  outputs, which messages, which exit codes — goes to everyone, because withholding it makes
  the task undecidable rather than harder. What the builder must not have is the **oracle
  content**: the stored calibration, the reference numbers, the hidden fixtures. It gets the
  command that checks them and reads pass or fail.
  Code written with the expected numbers in view drifts toward satisfying them directly — the
  hard-coded value, the branch keyed to the fixture. *Honest limit:* this buys measurement
  hygiene, not quality. Keep it because it protects the number, not because it raises it.
- **Keep the oracle where the run cannot reach it.** An exclusion rule you have to remember is
  a rule you will forget; a file that is simply not on the path cannot leak.

## The brief — static first, task last
The prompt is ordered so its unchanging part is a cacheable prefix shared by every instance of the
cycle: `CLAUDE.md`, the manual, the briefing, the world model — then the task, last. Cache reads are
a fraction of the price of fresh tokens, so a 1,000-line prefix costs little; the same lines pasted
in a different order each time cost full price every time.

```
You are the <role name> on <the project, as world_model.md §1 names it>.
Surface: <Claude Cowork | Claude Code>
Model:   <the model this instance runs on - a reviewer of a build never runs on the builder's model>
Effort:  <from the roster's effort column - the lever; raised only by a Product Manager ruling in the decision register>

YOUR BRIEFING      (briefings/<role>.md, pasted verbatim - do not paraphrase)

WHAT YOU WRITE     <the one artifact, and where it goes>
WHAT YOU READ      <your knowledge base, the directory table, the cycle, the extract below;
                    world_model.md §6 if you build, all of world_model.md if you plan>
WHAT YOU DO NOT READ  <the other reviewers, the full backlog, the full feedback file,
                       the oracle content - stored calibrations, reference numbers, hidden fixtures>

RETURN
  First line: the model you ran on (effort is what the brief requested; an instance cannot observe its own tier). Then exactly the shape your briefing's "Returns" names. Nothing else - no prose report, no summary.
  Everyone, last: one line per check that could not run. An absent line reads as a check nobody ran.

THIS TASK   (always last - everything above it is the same for every instance and is cached)
  Artifact:   <file or run stamp>
  Question:   <the one question you are answering>
  Extract:    <only the backlog or feedback lines that bear on it>
```
**The third line is the one most often forgotten.** *What you do not read* is what makes a
reviewer worth its cost; without it a reviewer explains the code instead of attacking it.

## Level, model, effort

**Level is binding, model is advice, effort is the lever.** Effort is set per seat in the roster's effort column, `team_roles.md` (the
verifier instance runs at the lowest) and raised only by a Product Manager ruling in the decision
register. One exception is binding: **the reviewer of a build never runs on the builder's model** —
a fresh context stops persuasion, only a different model stops a shared blind spot; where only one
model is available the review says so and a finding it did not make is evidence of less.

| level | what its output gets | on what model |
|---|---|---|
| L5 | independently verified, always, by a **named refuter** — without one the verification has not happened | a model other than the seat's |
| L4 | a design review before build | the reviewer's, per the exception above; a review written on the strongest model is refuted on another, as L5 |
| L2–L3 | a normal read | the reviewer's, per the exception above |
| build instances | the review the weight names | a model other than the builder's |

Which model each seat runs on, and which refutes it, is the roster (`team_roles.md`).

## The weight of a job — how many instances a cycle spends
- **Standard** — a fix or a measure. Builder · verifier · the Architect plus one domain reviewer,
  blind · triage. Refutation for `blocks` findings only.
- **Full** — a change: anything that alters what a section writes, an indicator, a threshold, a cost
  model. Builder · verifier · all five reviewers, blind · refutation of every finding above `note` ·
  triage · a pre-registered MEASURE.

The weight is a line in the work order, written before build; the Architect may raise it, never
lower it; a job that outgrows its weight halts and is re-issued. There is no weight without a review.

## The plain-instance control
A weight rule is tested against a **single instance** given the same brief and criteria, nothing
else, judged by the same verifier and blind reviewers; the design, cadence and decision rule are the
project's (`briefings/_multi_agent_practice.md`, P3). It is pre-registered like any measurement.

## Limits
- **One work order in build per lane** — a lane is a set of write paths no other build touches.
  PLAN does not reopen until MEASURE has produced a result.
- **Reviewers are blind to each other.** Independence is the entire value of having several.
- **Ten findings to the Owner per cycle**, deduped and ranked, through the Product Manager.
- **The orchestrating seat never does the work itself.** An approval you wrote yourself is not an approval.
- **Instances are ephemeral.** A role is a definition on disk; an instance is created for one task,
  writes its output, and ends. It returns a report; it does not write a handover.
- **An instance halts** when the same check fails three times against three different fixes, when a
  finding reaches its third fix round, or when the work in front of it is not in the work order. It
  writes why, carries on with whatever is independent of it, and says so at the end.
- **A tool whose output is large** (hundreds of megabytes) is run once; a verifier or reviewer checks
  the artefact's stamp and size rather than re-running it. State the output size in the budget.

## Stop and ask the Owner — through the Product Manager
- A work order would add capability during a stability milestone.
- Two roles disagree and the boundary rules do not resolve it.
- A finding is `blocks` and the fix is not obvious.
- The cycle produced more than thirty findings — that is a signal about the machine, not a list.
- MEASURE has not completed and backlog pressure is pushing you to start anyway.
