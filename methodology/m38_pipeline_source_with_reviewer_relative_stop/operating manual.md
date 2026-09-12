# Operating manual — how this project is run

**Read by every role, every time; what only some roles need is in their briefings.** Kernel — paths,
roster, product and history are the project's files (`kernel/README.md`).

Living document · the Product Manager maintains it.

---

## 1. The cycle — how any piece of work is delivered

```
   PLAN ──▶ BUILD ──▶ REVIEW ──▶ VERIFY ──▶ TRIAGE ──▶ MEASURE ──┐
   (PM)     (RE)       (parallel, (refute)    (PM)       (the run)  │
      ▲                  blind)                                     │
      └─────────────────────────────────────────────────────────────┘

        PLAN does not reopen until MEASURE has produced a result.
```

| stage | who | what has to be true to leave it |
|---|---|---|
| **PLAN** | Product Manager | one work order exists in the shape `planning.md` §4 names — it serves a key result, carries priority, size and weight, and names what deliberately does not change |
| **BUILD** | Release Engineer | the test gate is green **as run by a verifier instance, not by the builder** (`kernel/verifier.md`), and the changelog says what moved and what did not |
| **REVIEW** | the reviewers the job's **weight** names (`_creating_a_role.md`), in parallel, **blind to each other** | every reviewer has returned findings in the schema |
| **VERIFY** | an independent instance per finding the weight names | each such finding has survived one attempt to refute it |
| **TRIAGE** | Product Manager | findings deduped and ranked; the Owner has what only he can decide |
| **MEASURE** | the run | a result exists and is written up |

**A failed check is a comprehension failure first.** It goes to the work order's author before it
goes back to the builder: was the task described wrongly or incompletely? Patching forward from a
misread task produces code that passes and is wrong.

**The research workflow** — which step, whose — is the project's `world_model.md` §4; every step is
delivered through this cycle. Creating an instance: `_creating_a_role.md`; building and releasing:
the project's `briefings/_build_and_release.md`.

## 2. Who decides, and who is told

Each role has one briefing, `briefings/<role>.md` — its charter (Owns / Not yours / Rules / Delivers),
what it reads, what it returns — and a seat knowledge base named there. The charter says what the
seat is **allowed to do**; the knowledge base holds what it has **learned**. An instance needs both,
and reads no other role's briefing.

**The Owner decides** scope, risk appetite, deployment and every open question. Roles escalate
rather than guess, and frame each decision as options + evidence + a recommended default **and the
date that default fires**.

**Escalation is aggregated.** The **Product Manager is the only seat that escalates to the Owner**,
and does so once per cycle, with the findings already deduped and ranked. Every other seat escalates
to the Product Manager. A seat reporting straight to the Owner is how ten roles turn into ten
inboxes.

---

## 3. Rules that govern all work

One copy each: in the project's `team_roles.md`, *Rules every role shares*, when two or more roles read
for a rule; in the role's briefing, *Rules you read for*, when one role alone does — each with its
reader, its stage and where its verdict lands.

---

## 4. Who is deliberately kept in the dark

Independence is the whole value of having several roles, and it is the easiest thing to break
by being helpful.

- **A reviewer reads the artefact and its behaviour — never the author's reasoning, never another
  review.** Given the plan it explains the code instead of attacking it; given a review it repeats it.
  What a creator must therefore withhold from a reviewer and from a builder — the four independence
  rules — is `kernel/_creating_a_role.md`.

- **No role writes another role's document.** The Product Manager does not write the review; the
  reviewer does not write the work order. **An approval you wrote yourself is not an approval.**

**Two things are called a review, and they are not the same document.**

- A **cycle review** is written at the REVIEW stage by the reviewers the job's weight names, in parallel and blind to each other, and is read by the
  Product Manager. Filename token: `<role_name>_review_…`.
- An **external review** is written by a seat outside the roster, carries no role authority, and is
  a proposal addressed to whoever it names. Filename token: `external_review_…`.
- The **Product Manager writes neither.** What the Product Manager delivers is the **triage** —
  findings deduped, ranked, and split blocking from non-blocking.

---

## 5. The finding schema and the severity ladder

Every review, verification and proposal returns findings in this shape. Not prose, not a summary.

```
role:        <the role name>
severity:    blocks | should | note
claim:       one sentence
evidence:    file:line, or a measurement with its run stamp
changes:     the decision this changes - if none, severity is note
confidence:  high | medium | low
verified_by: <the seat that tried to refute it, and the outcome>
```

| severity | means | what happens to it |
|---|---|---|
| `blocks` | one of the four blockers, or the release is wrong if it ships | fixed before the cycle closes; escalated if the fix is not obvious |
| `should` | changes a decision, but the release can ship without it | ranked into the backlog |
| `note` | **changes no decision** | filed, not surfaced |

`changes` is the field that controls volume. **A finding that changes no decision is filed, not
surfaced.** *"Every finding above `note`"*, wherever this manual says it, means `should` and
`blocks`.

---

## 6. Documents, draining, handovers — the rules; the tables are the project's

- **One writer per document type**, and every type has a reader; the table of types, writers and
  readers is the project's `document_types.md` (Product Manager and Key User read it; a role that is
  about to write a new kind of document asks one of them).
- **Facts and judgements are kept apart, and only judgements are capped:** a register grows without
  limit; a seat knowledge base holds at most eight judgements, each tagged with the kind of job it was
  learned on, the condition under which it applies and how it was verified; a brief may say *cold* to
  switch them off.
- **Every document carries a date in its name** except the standing ones; a dated file is never
  overwritten — corrections go at the top, named plainly.
- **Drained, not grown:** feedback is marked drained once it reaches the backlog or a ruling; the
  backlog is re-issued dated; a section past ~40 KB is a blocker to raise.
- **An instance does not hand over** — its report is the record. **A long-running chat hands over**
  at about half of its context, or when the Owner asks, to the pattern and folder the project names;
  the `handover-writer` skill in `kernel/skills/` says what one must contain, read then, not before.
  A successor reads its predecessor first.

---

## 7. The method measures itself

Every rule change names the observed failure that caused it and the run that will show whether it
helped, in the project's `method_changes_and_retro.md`; a change without a failure behind it is a new
idea, and new ideas wait. *The next plan waits for the last measurement* applies to this manual too.
