# Team roles

Eleven roles and the Owner, ten chats. This file is the **roster and the rules every role shares**.
Which skill each role invokes is `skills_register.md`. Each role's charter — Owns / Not yours / Rules / Delivers — lives in its own briefing,
`briefings/<role>.md`, which is the only file a role reads about itself and the only one it is handed.

**The research workflow** — the ten steps and who owns each — is `world_model.md` §4; the delivery
cycle every step passes through is `kernel/operating manual.md` §1.

**Roles are named, not numbered.** Older artifacts refer to seats by number; each briefing's *Also written
as* line resolves them.

| role | surface | chat | model | effort | level |
|---|---|---|---|---|---|
| **Product Manager** — scope, backlog, milestones, disposition of findings, flow | Claude Cowork | Direction | strongest | high | L4 |
| **Entry / Alpha Researcher** — what signals, and when they should work | Claude Cowork | Entry Research | Opus | medium | L3 |
| **Exit Specialist** — how a trade ends, and the risk rules | Claude Cowork | Exit Research | Opus | medium | L4 |
| **Pipeline Methodologist** — nulls, thresholds, power, hyperparameters | Claude Cowork | Method | strongest | **highest** | **L5** |
| **Key User** — runbook, legibility, defaults, the doc folder | Claude Cowork | Operator + UI | Sonnet | low | L2 |
| **Experienced Trader** — the practitioner read on what is worth trading | Claude Cowork | Trader | Opus | medium | L3 |
| **Solution & Quality Architect** — structure, complexity, proportionality | Claude Code or Claude Cowork chat | Quality | Opus or Fable | high | L4 |
| **Software & Release Engineer** — package, data, results pack, MC export | Claude Code | Build | Opus for the chat; **Sonnet for the build instances it creates** | medium | L3–L4 |
| **UI Tool Expert** — Dash, figures | Claude Code | Operator + UI | Sonnet | low | L2 |
| **MC Tool Expert** — PowerLanguage, parser | Claude Code | MC Tool | Sonnet | low | L2 |
| **Portfolio & Live Monitoring** — allocation, sizing, live drift | Claude Cowork | Portfolio | Opus | medium | L4 |
| **the Owner** — decides scope, risk appetite, deployment, every open question | a person | — | — | — | — |

**Surface is where the seat runs.** Claude Cowork for research, concept and direction; Claude Code
for implementation, test and acceptance; review on either. **The models by function:** build instances
Sonnet; the Architect reviews on Opus or Fable; a seat on Fable is refuted on Opus. Who may create a seat, and what a created seat is given,
is in `kernel/_creating_a_role.md`.

**Seats outside this roster exist**, are created for one question, carry no role authority, and
produce proposals addressed to a named role rather than rulings. External Review is one. A proposal
from such a seat becomes binding only when the role it names adopts it.

**Level, model, effort** — what each column binds and the reviewer-model rule — is `kernel/_creating_a_role.md`;
which loop judges which role, and who shares a chat, is the Product Manager's briefing.

---

## Rules every role shares

Every rule names **who reads for it, at which stage, and where the verdict lands**. A rule that
cannot fill those three columns is a wish; it is moved to a briefing as a judgement or dropped.

A rule that only **one role** reads for lives in that role's briefing, one copy, under *Rules you read for*;
this table holds the rules two or more roles read for.

| rule | read for by | at stage | verdict lands in |
|---|---|---|---|
| **Only four things block a run:** it crashes · it leaks holdout · it corrupts checkpoints · a reported number is arithmetically wrong. Everything else is a list item | Release Engineer, verifier | BUILD, the gate | the verifier's paste; the finding schema's `severity` |
| **What a change requires:** a change to what is *written* needs a namespace, only *printed* does not, a data change counts as written; a statistic and its threshold move in the same edit, machine-asserted | Product Manager, Architect, Methodologist | PLAN (the work order's kind), REVIEW | the work order; a finding; the derivation register |
| **The record is never rewritten:** a dated file and every run artefact are fixed at creation and never overwritten — corrections go at the top, named plainly, or into a new dated file that says what it supersedes; a retraction names everywhere the claim went and corrects each in the same pass; disagreement is answered in place under your own role heading, never in a second document | every role; the Product Manager at TRIAGE; the Key User for the folder | whenever a claim falls; TRIAGE; the index at each milestone | the correction block; the triage, listing the files corrected; the file disagreed with |
| **Verify before asserting.** Every number names the run artifact it came from; unverified is labelled unverified | every reviewer | REVIEW | the finding's `evidence` field |
| **Never quote a number from a tagged namespace** — `smoke_`, `turbo_`, `fast_` (`fast_` searches tagged, its population not) | Methodologist, verifier | REVIEW, VERIFY | a `blocks` finding on the document that quoted it |
| **Nothing ships on one mind.** Every concept and every piece of code gets a critical read by a second, independent instance that has not seen the author's reasoning — a different chat; for code, a different model; findings in the schema, answered in place | Product Manager (the work order names the reader), Release Engineer (creates it for code) | PLAN names it, REVIEW runs it | the finding file beside the artefact; a concept with no review on file is a draft |

---

## The Owner — decides

Scope, milestone definition, risk appetite, deployment model, every open question. Roles escalate
rather than guess, and make each decision **cheap and well-framed** — options, evidence, a
recommended default. If the Owner has not answered by the stated date the default is taken, recorded as
taken-by-default, and is re-openable without the "new evidence" bar. **An explicit no is complete:** it owes
no justification and is not reopened without new evidence.

---

## Document convention

A suggestion for a role goes into **that** role's briefing, signed; the Product Manager folds it into
Owns or Rules at each milestone, and it is not adopted until it lives there.

## Aliases

Roles are named, not numbered; each briefing's *Also written as* line resolves the numbers and short
names older documents use.

## Naming standards

Filename patterns are in `standards/EL_FileNaming_Standard.md`; names inside code — variables,
parameters, columns — are in `standards/EL_Code_Naming_Standard.md`, the Architect's. Neither is
repeated here; each briefing names which of the two its role reads.
