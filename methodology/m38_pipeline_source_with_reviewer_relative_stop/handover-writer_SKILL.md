---
name: handover-writer
description: "Writes a single all-in-one handover document that lets a fresh session (or a new person) pick up a long-running project with no other context. Use when a chat is about to hit its context limit, when handing a project to another thread/agent/colleague, when handing between agent surfaces such as Claude Cowork and Claude Code, when knowledge has spread across many review/plan/results files and needs consolidating, or when starting a successor thread. Triggers - \"write a handover\", \"hand this over\", \"the chat is full\", \"new thread\", \"consolidate the docs\", \"onboarding doc for the next session\", \"continuation document\", \"bring the next agent up to speed\"."
---

# Handover writer — one document, no other context required

A handover fails in one of two ways: it is a summary (readable, useless — the
next session still has to rediscover everything), or it is a pile (complete,
unusable — many files with no entry point). This skill produces the third
thing: **one document a fresh session reads start to finish and can then act
from**, with pointers to detail rather than copies of it.

The test: hand it to someone who has never seen the work, give them nothing
else, and they should be able to do the next task correctly — including knowing
what *not* to do.

## Before writing

- **Inventory what exists.** Every document, script, output directory and data
  store. Note which are authoritative and which are superseded — a handover that
  doesn't say "this is stale" is worse than none.
- **Read the trail, newest first.** Reviews, plans, changelogs, results,
  prior handovers. Look for decisions and their reasons, corrections of earlier
  claims, numbers with provenance, and anything learned the hard way.
- **Interview for the gaps.** What nobody writes down is usually the most
  expensive: why an obvious approach was abandoned, which tool has a quirk, what
  breaks at 3am, who decides what. Ask rather than guess.
- **Verify before asserting.** Every number should trace to a run, a file or a
  measurement. If it is cheap to check, check it. Mark anything unverified as
  unverified.

## What the document must contain

Every heading below is mandatory in the skeleton. If one is genuinely empty,
keep it and write "none yet" — an empty heading is information, a missing one is
a gap the reader will not know to look for.

### Orientation — what am I looking at?

- **What this is.** The goal in three sentences. What "done" looks like. Who the
  people are and who decides what.
- **Vocabulary.** Domain terms, internal jargon, abbreviations, naming
  conventions — anything appearing in the work without explanation.
- **Map of where things live.** Marked **authoritative** / **generated** /
  **superseded**, naming the single source of truth for each kind of thing.
- **Reading order.** A handful of documents, in order, one line each on why.
  This is what makes everything else optional.

### History — why is it like this?

- **Version chain.** One line per version: what shipped, what it was for. Enough
  that a version in a filename means something.
- **The intellectual arc.** What was learned, in order, including what was tried
  and abandoned and why. **Corrections of earlier claims go here, named
  plainly**, at the top. A quietly dropped belief gets reinvented.
- **Decision register.** For each decision: what, when, the reason, and **what
  evidence would reverse it**. That last field stops settled questions being
  re-litigated, and lets one be reopened legitimately.

### Present state — what is true right now?

- **Current state.** What is running, finished, half-done, broken. Carries its
  own date; this goes stale fastest.
- **Output and namespace map.** What exists in storage, which namespace each
  belongs to, which are authoritative, which can be regenerated and how, which
  must never be overwritten.
- **Known-good baselines.** Exact numbers: test counts, timings, memory, output
  magnitudes, expected ranges. Without these a regression is invisible and every
  anomaly looks normal.
- **Environment and session state.** What must be configured before the reader
  can work, and what state the last session left behind. Omit this and you have
  handed over a broken environment; the reader's first hour goes on rediscovering
  it. Cover whatever the surface in use requires — for a coding surface: branch,
  uncommitted or stashed work, worktrees, which instruction and rules files load,
  hooks that block actions, required extensions and servers, the permission
  posture assumed. For a chat or workspace surface: which folders or sources must
  be attached, what was published and where, which connectors are relied on, what
  was written to persistent memory. Always: tool and language versions, what must
  be installed, where credentials live (never the credentials), and **whether the
  work is under version control at all**.
- **In flight right now.** Anything running or scheduled that will land *after*
  this document is written: long jobs, background agents, scheduled tasks, reviews
  out with someone. For each: what it is, when it started, where it writes, and
  how to tell it finished cleanly. Name what will appear with nobody doing
  anything, or the successor treats a new file as a mystery.

### Working method — what do I actually do?

- **The working loop.** The repeating cycle, named as steps. Say where each
  step's input comes from and what "done" means for it.
- **Change mechanics.** How changes are made here specifically: the pattern, the
  tooling, the conventions. Include **hard rules learned from real failures**,
  each with the failure that produced it.
- **The verification gate.** The exact command, what green means, the current
  baseline numbers, and the rule about not shipping amber.
- **Running and resuming.** Execution profiles and their costs, how to resume
  after a failure, which outputs survive a crash and which do not, how to tell a
  real result from a stale one.
- **Reading results honestly.** Which number is the verdict, which are
  diagnostics, which are misleading and why. Include the arithmetic that keeps
  people from over-claiming.

### Guardrails — what must I not do?

- **Invariants.** Rules where violation is a bug rather than a choice. Short
  enough to remember; if the list grows long, some entries are preferences and
  belong under change mechanics.
- **Stop and ask.** The specific situations requiring a human decision before
  proceeding. Concrete: "before X" beats "when in doubt".
- **Traps already hit.** Anti-patterns with the scar tissue attached — the
  mistake, what it cost, how to recognise it early. Experienced readers value
  this most.
- **Where the previous session was wrong.** Traps-already-hit holds the *work's*
  hazards; this holds the *agent's* errors, and a successor with the same
  tendencies repeats them. For each: what was asserted, what was actually true,
  and **the signal that caught it** — the signal matters more than the error,
  because it is what the next session should watch for. Check explicitly for the
  four that recur:
  - an ambiguous reference resolved to the wrong artifact, with work built on it
    before anyone noticed;
  - a number invented to fill a blank, then treated as decided because it had
    been written down;
  - a claim about a file made from memory or a stale diff instead of re-reading;
  - scope widened past what was asked, one defensible step at a time.

### Next — what should I do?

- **Open topics, ranked.** For each: why it matters, what "done" looks like,
  rough effort. Ordered, not merely grouped.
- **Open questions, each with a default and a date.** Every unanswered question
  names its owner, a **recommended default, and the date that default fires**. A
  question without a default blocks the successor; one with a default lets work
  continue and makes the decision visible if nobody objects.
- **Deferred backlog.** Everything consciously not being done, **with the
  reason**. Undocumented deferrals get rediscovered as bugs.
- **Next scope.** The concrete work order for whoever picks this up.
- **Ready-to-paste kickoff prompt.** The handover's output, not just its input:
  a block the reader pastes into a fresh thread to start work — role, reading
  order, scope, constraints, deliverables, what to report back.

### Operational — what will waste my time?

- **Facts that save time.** Environment quirks, tool versions, gotchas,
  identifiers, where credentials live (never the credentials), formats, "the log
  lies about X", "this cache is stale after Y".
- **Handover log.** Append-only: who handed over, when, what changed since the
  previous handover. The chain is how a series of handovers stays honest.

## Writing rules

- **Evidence, not assertion.** "Takes about 23 minutes, peak 3.7 GB, measured on
  <date>" beats "it's slow". Numbers carry their provenance.
- **A result is run, not remembered.** Execute the verification command while
  writing and paste its actual output with the time it ran. A remembered green is
  how a successor inherits a broken build.
- **Say what is unknown.** An explicit "we never measured this" is worth more
  than confident silence.
- **Corrections at the top of the section they belong to**, named plainly,
  including corrections of your own earlier claims. A reversal buried mid-
  paragraph is guaranteed to be missed.
- **Point, don't copy.** Detail lives in its own document; the handover says what
  it contains and when to read it. Copied detail goes stale silently.
- **Separate the fast-moving from the durable.** Present state changes weekly;
  history and guardrails rarely. Date the fast-moving parts so staleness shows.
- **Write for a competent stranger**, not for yourself next week. Any sentence
  that only makes sense if you remember the conversation must be rewritten.

## File conventions

The pattern, the folder, the trigger and the clock are the project's — `project_layout.md`,
*Handovers*. A kernel skill names none of them.

## Length

**15–50 KB.** Below that the detail that makes it actionable has been cut; above
it, orientation stops being read. A single-seat handover sits at the lower end, a
project-wide one at the upper. When a section grows past a page, that is the
signal to spin it into its own document and leave a pointer rather than to spend
the budget.

## Finishing check

- A stranger could name the next task and start it, from this document alone.
- Every number is traceable; unverified claims are marked.
- The verification output was produced while writing, not recalled.
- Environment and session state is complete enough that the reader starts work
  without asking a configuration question — and it says whether the work is under
  version control.
- Everything in flight is named, with what it will write.
- The stale-output question is answered for every namespace.
- Invariants and stop-and-ask would actually stop the mistake they exist to
  prevent — read them as an adversary looking for a loophole.
- Every open question has an owner, a default and a date.
- The kickoff prompt stands alone: paste it into an empty thread and it works.
- The fast-moving sections carry their own date.
- **The file is 15–50 KB.** Under: something mandatory was skipped. Over: a
  section needs spinning out into its own document.
