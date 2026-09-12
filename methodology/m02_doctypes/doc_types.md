# Document types

Three files in the project_workspace root, each about fifteen lines at most. This methodology asks for them,
so they are part of the task; no other documents are.

1. **`PLAN.md`** — written before the first code edit. What the task asks for, which files you intend
   to change, in what order.
2. **`DECISIONS.md`** — written as decisions are made, one line each: the choice and what it rules out.
3. **`SUMMARY.md`** — written last. What changed, what the tests said, what was left undone.

A document that grows past about fifteen lines is costing more than it carries. Cut it, do not
continue it in a second file.

When `doc_types` is `adr`: one file per decision under `docs/adr/NNNN-title.md`, numbered from
0001, each with the three headings **Context**, **Decision**, **Consequences** — instead of
`DECISIONS.md`, not beside it. `PLAN.md` and `SUMMARY.md` are unchanged, and the fifteen-line cap
applies to each record.

`AGENT_BACKLOG.md` is the one further document this feature may ship: one line per item the task named
and this run deliberately did not do, so the next session gets the list rather than the reasoning.
Write it only when there is something to put in it.
