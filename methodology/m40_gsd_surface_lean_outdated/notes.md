GSD-B/L. m39_gsd_surface_full_outdated cut to what a single run can obey: the same phase cycle, the same gate
taxonomy and the same producer-never-certifies rule, with 33 roles collapsed to 8 and the phase
artefact set cut to four (CONTEXT, PLAN, SUMMARY, VERIFY). Composed 2026-09 from 39.

The collapse is stated explicitly in §2.1 rather than left implicit: the seven researchers are one
contract with different search targets; the ten checkers and auditors are two contracts — check the
plan before execution, check the artefact after — and their specialised concerns (security, UI,
integration, eval, Nyquist coverage) become checklist sections in the verifier's brief, not further
roles. Splitting the verifier six ways adds coverage of concerns, not independence, and independence
is the only thing the extra context costs buy. The docs pipeline, framework selection, profiling,
codebase mapping and debug session management are dropped outright with the workflows they serve.

§0 carries the source analysis the number rests on, and §7 scores the transcription at 7/10 by
capability: methodology and role separation reproduce whole, state accounting and blocking
enforcement do not.

Read against 39, the question is whether 25 dropped roles and 59 dropped verbs cost anything
measurable on one task, or whether the breadth was only ever reachable across a milestone. Read
against m42_gsd_core_lean_outdated, the question is whether four artefacts under `.planning/` behave differently
from three under `.work/`.

Adherence: `res_artifacts` contains CONTEXT, PLAN, SUMMARY and VERIFY, no more;
`res_subagents_spawned >= 4` with the checker never the planner and the verifier never the executor;
every PLAN.md task carries a verification command whose output is pasted into the report.
