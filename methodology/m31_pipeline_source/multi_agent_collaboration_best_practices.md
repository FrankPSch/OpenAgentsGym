# Multi-Session Agent Collaboration — Best Practices

**Goal — best practices for collaboration between one or more Claude Cowork sessions
and one Claude Code chat or agent.**

The rules are written generically — any runtime, any count — so several concrete methods
can be derived from them. Each names the failure it prevents and prescribes no tool.

**Read by the Architect and the Release Engineer** — the seats that design and run multi-instance work; named in their briefings, read by no other role.
**Owner-written.** Amend when a rule is falsified by an observed failure, not when a new idea sounds good. Date amendments.
*Amended 2026-09-02: §5.9 and §7.7 added, each from an observed failure named at the rule.*
**Tags:** `Q` quality · `P` cost · `OD` over-delivery · `OC` over-complication.
**Precedence:** independence beats deduplication — a fact declared twice on purpose, with a check comparing the copies, is not a duplicate. Otherwise single source wins.

## 1. Why

1. Sessions share **no context, only artifacts**. Every other rule follows. `Q`
2. Multi-session buys parallel reading, independent judgement and fresh context — not faster sequential work. `OC`
3. Add a session only against a **named bottleneck**, and pick the smallest topology that clears it before picking tools. `OC` `P`

## 2. Symptom index

| Symptom | Rule |
|---|---|
| Silent overwrite, lost edits | §6.1 |
| Two copies of the work, quietly diverging | §4.2 |
| Reviews that agree with everything | §3.5 |
| Checks pass on work that never ran | §4.7, §8.3 |
| A failing check closed by moving the target | §4.3 |
| Decisions nobody can locate later | §1.1, §5.6 |
| Each side assumed the other did the other half | §3.3 |
| Scope grows every cycle | §5.4 |
| Releases ship before the last one was read | §5.9 |
| A remembered lesson made a later run worse | §7.7 |
| Cost rising faster than output | §5.8, §7.2, §7.3 |
| A system nobody can explain | §1.3 |

## 3. Roles and models

1. The **owner** states requirements, holds acceptance data and resolves conflicts; peers never settle a disagreement between themselves. The one role that may be a person. `Q`
2. One role = one responsibility, one output artifact. `Q`
3. **Work is owned end to end by whoever is closest to the artifact.** Splitting one task across roles produces two halves, each assuming the other did the rest. `Q` `P`
4. **Producer never certifies.** `Q`
5. **Manufacture independence** — fresh context stops persuasion, a different model or data slice stops a shared blind spot, and reviewers do not see each other's findings before verdict. Identical agents are one opinion counted N times. `Q`
6. Match capability to role; maximum everywhere buys budget consumption, not quality. `P`
7. Roles declared in a readable artifact, so a fresh session learns what it is. `Q` `P`

## 4. Data and documents

1. **One writer per artifact class**, enforced mechanically — conventions decay unattended. Parallel producers of one class write to disjoint paths. `Q`
2. **One canonical working copy per artifact.** A second copy is drift with a delay. `Q`
3. **Acceptance data is owner-owned and unreachable by producers**, or a failing check gets closed by moving the target. `Q`
4. Single source of truth per fact, subject to the precedence rule. `Q` `OC`
5. **Interfaces over contents** — neighbours read a contract, never the implementation. `P` `OC`
6. Append-only journals, not one shared file many sessions edit. `Q`
7. **Provenance on every artifact** — author, base revision, inputs. Without it you cannot quarantine, only halt. `Q` `P`

## 5. Process and workflow

1. Handoff = brief + constraints + acceptance criteria + the exact check that proves it. `Q` `OD`
2. **Done means a check passes**, never prose. `Q`
3. Checks are code; opinions belong to a review role. `Q`
4. **Acceptance criteria written before production, by another role**, stating what is out of scope. `OD`
5. Smallest increment a check can accept, so a failure names one cause. `Q` `OD`
6. Boundary crossings are compact artifacts, not transcripts. `P`
7. **A thread that must continue elsewhere hands over one self-sufficient artifact**, never replayed context. `P` `Q`
8. Escalation aggregates — if every producer can interrupt the owner, the owner reads none of them. `P`
9. **The next plan waits for the last measurement.** One increment in flight per lane. Producing faster than measuring is how a backlog outgrows its reviews and a gate runs for versions before anyone asks whether it predicts anything — observed here, twelve versions. `Q` `P`

## 6. Concurrency and state

1. **One writer per working copy** — two sessions in one copy clobber each other silently, both holding stale views. `Q`
2. Isolate parallel writers, merge at exactly one point. `Q`
3. **Hold the pen explicitly**: a lock naming holder, time and heartbeat; a blocked writer refuses rather than waits; stale locks are broken by the owner. `Q`
4. Every remote or bridged read is a snapshot — re-verify before deriving from it. `Q`
5. **Immutable checkpoints are the ledger**: one per role boundary, a marker on each accepted state, the difference as evidence. `Q`
6. **Runs are reversible and repeatable** — same inputs, same result; undo without rebuilding state by hand. `Q` `P`
7. Unattended runs are standalone, lane-scoped and no-op when locked. `Q`

## 7. Context and knowledge domains

1. Cut domains where **two facts never need to be held at once** — role, then artifact layer, then module. `P` `OC`
2. Each session gets a **scoped path list**; unbounded exploration is the largest cost driver. `P`
3. Prefer a check's answer to reading the material; delegate broad search and take the conclusion. `P`
4. Entry point small enough for competence in one read — expensive onboarding suppresses needed restarts. `P` `Q`
5. **Restart at role boundaries**; long sessions carry superseded work and lose review independence. `Q` `P`
6. Diagnostic: onboarding cost rising per cycle means the cut is wrong. `P`
7. **Carried judgement is tagged with the task kind it was learned on, and can be switched off.** A routine from one kind inverts on another — *preserve what looks like a defect* is right in a refactor and keeps every bug in a fix; and without a cold run no two runs are comparable. `Q`

## 8. Trust at scale

1. **Trust attaches to the claim, not the agent** — a claim is trusted because something re-derives it. `Q`
2. **Verification must be cheaper than production**, or throughput caps at what a human can read. `P`
3. What is trusted migrates with what you can still read: `Q` `P`

   | Once you can no longer read… | trust shifts to | add |
   |---|---|---|
   | every change | the handoff boundary | checks at each boundary |
   | every boundary | the checks | sampling, evidence a run happened |
   | every escalation | the aggregate | provenance, canaries, quarantine |
   | every exception | the statistics | audit rate, blast-radius limits, budget as governor |

4. Blast radius narrows to a lane as the population grows, paired with §6.6. `Q`
5. **Seeded canaries with known answers** are the only measurement of trust; agreement without independence is not evidence. `Q`
6. Budget is a governor, not a report. `P`
