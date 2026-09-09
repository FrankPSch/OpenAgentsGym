GSD-S. The same framework as 35_gsd_core_faithful, transcribed at its full published surface: all 33
agent roles and all 67 commands kept as roles and verbs, against 35's fifteen. The surface area is
the variable; nothing else is.

Source note, and the reason this is not a second framework: `gsd-build/get-shit-done` and
`open-gsd/gsd-core` are one repository. Identical root commit (`1fe3fa42`), merge base `b533f718` on
2026-05-21. After the split gsd-build added 13 commits, all deprecation and rebrand notices, and
froze at v1.9.9; gsd-core added 2865 and is at v1.13.0. This file was read from the frozen snapshot,
so it is gsd-core as of May 2026, not an independent line. Attribute any finding here to the
surface, never to a repository.

What the May snapshot and the current head share, checked file by file: `references/gates.md`
differs by two lines, the roadmap template is byte-identical, the role set is the same 31 plus
`dom-verifier` and `mempalace-curator`, the command surface is 67 against 72. What the head adds is
enforcement depth — the verifier evidence gate, Nyquist compliance, the honest-verifier and
untrusted-input-boundary rules, the compact-content gate, eight debugger references, and the
skills/capabilities repackaging. None of it changes the stages, and 35 already carries it. So the
only thing this rung can measure that 35 cannot is breadth.

Map: `Get-Shit-Done Full Methodology.md` §2 = the template corpus and the `.planning/` layout; §3 =
all 33 agent files with their input/output/must-not contracts; §4 = `references/gates.md` in
structure (pre-flight / revision / escalation / abort, plus the gate matrix); §5 = the workflow
corpus including the specialist contract phases (spec, ui, ai-integration, mvp, ultraplan) that the
lean rungs drop; §6 = the 67 verbs, grouped as the repo's own `ns-*` namespaces group them; §7 = the
reference rules (goal-backward derivation, universal anti-patterns, context budget, SPIDR, decimal
phases); §9 = the 15 hooks restated one by one as stated discipline.

Excluded, because they are enforcement rather than method: hook denial (PreToolUse exit 2 cancels a
tool call — a rule only asks), commit-message validation, prompt-injection scanning on Read and
Write, the context monitor and statusline, and the CLI/SDK layer that computes state, holds locks,
archives milestones and drives worktrees.

The readable question: what does surface area cost when almost none of it is reachable on a single
task? 35 states up front what one run cannot obey and keeps fifteen roles; this rung keeps all 33
and 67 and leaves the pruning to the agent, so over-delivery and unread artefacts are the expected
failure mode and are visible as such.

Adherence: `res_artifacts` contains at minimum a CONTEXT, PLAN, SUMMARY and VERIFICATION per phase
under `.planning/`; `res_subagents_spawned >= 4` (planner, plan checker, executor, verifier) with the
checker never the planner and the verifier never the executor; every task in PLAN.md carries a
verification command and every command appears in the report with its output pasted. Expect the
highest artefact cost on the ladder.
