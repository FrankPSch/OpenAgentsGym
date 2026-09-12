# Planning — backlog, priority, size, the work order, done, leaving

*Read by the Product Manager, who owns all of it, and by the Architect for §4. Kernel: it names
documents and classes, never a path; the project's `document_types.md` and naming standard say where
the backlog and its archive live.*

## 1. Intake
Everything enters the backlog as a finding in the schema (`operating manual.md` §5), written by its
source — a review, a feedback line, a handover's *open* section, a concept's proposals, an Owner wish,
a register the Architect keeps. The Product Manager disposes, never transcribes. An item needs a
**done-when** and a **decision it changes**; without them it is a wish or a `note`, filed. A gap
between the target picture and the pipeline is not an item — it becomes a key result, and only key
results generate P2 work.

## 2. Priority — four classes
- **P1 break** — a wrong number, a run that cannot run, a leak, a wrong concept that invalidates
  results. Starts now; a conceptual break goes to the spec author first; dependent in-flight orders halt.
  **A break carries its reproduction:** the finding names the command that reproduces it, the run stamp
  and environment it ran in, expected versus actual, and what is not affected — the fixer never asks.
- **P2 better at its job** — moves the verdict number (`world_model.md` §1) or increases the output.
  Full weight, pre-registered, against a key result only.
- **P3 new baseline** — a recalibration, a new population, a fixture rebuild. A measure job, on the
  Owner's word.
- **P4 fixes and debt** — non-breaking fixes, register-measured deletions. Standard weight; **owns the
  idle lane** while a P2, a P3 or a run occupies the machine — so it never starves and never displaces.

Within a class: soonest decision first, then smaller. The Product Manager ranks; whether something is
a P1 is appetite and goes to the Owner.

## 3. Size — four classes, calibrated
**S** one file, one instance · **M** a standard-weight cycle · **L** a full-weight cycle with a run ·
**XL** more than one cycle — split into lanes before it is an order. An order is sized against the
**last three closed jobs of its class** (tokens and wall-clock — the calibration rows at the head of the
current backlog issue, filled from the triages), never estimated fresh. Its budget is three numbers — lines the deliverable may add, output a tool may write, tokens
the cycle may spend. An overrun halts and re-sizes; it never finishes under the old size. A job that
costs double its class is a finding on the method.

## 4. The work order — one page, one lane
Kind (fix · measure · change) · weight (`_creating_a_role.md`) · priority · size · the key result it
serves · acceptance criteria written by someone other than the builder · what deliberately does not
change · the check that proves it · the domain reviewer (standard) or the concept's reader · the
pre-registered outcome, with a timestamp, for a change.

## 5. Done
The verifier's paste against the acceptance criteria; the weight's reviews with no open `blocks`; the
Architect rules *definition of done: met / not met*; the closing line of the item names the evidence
— a run stamp, a file, a measurement. *Looks done* is not a verdict.

## 6. Leaving the backlog
An item leaves as **closed** (its proof), **withdrawn** (the ruling and its reason) or **stale**
(unranked for two milestones, withdrawn with *no decision depended on it*). It moves whole, reasoning
included, to the dated backlog archive; a one-line stub with the verdict stays in the backlog for one
issue. The archive is never edited — a closure that turns out wrong returns as a **new** item naming
the old.
