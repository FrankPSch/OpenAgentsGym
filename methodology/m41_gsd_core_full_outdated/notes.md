GSD-F. The Get Shit Done framework transcribed as a methodology — outside the ladder, a foreign
composite rather than a rung: a six-stage per-phase cycle behind pre-flight gates, a planning
artefact reviewed before it is executed, one fresh instance per plan, goal-backward verification
against declared must_haves, and a fifteen-role split. Source, read 2026-09: `open-gsd/gsd-core`
v1.13.0 — 78 `skills/*/SKILL.md`, ~30 `agents/*.md`, `gsd-core/workflows/*.md`, ~120
`references/*.md`, 46 templates. Map: `GSD Core - Faithful Methodology.md` §2-§5 = the workflow corpus and
`references/gates.md`; §4 = the templates plus `references/artifact-types.md`; §5.4 = the
plan-checker's dimension list and `references/nyquist-compliance.md`; §5.6 =
`references/verifier-evidence-gate.md`; §6 = `agents/`; §10 = the fifteen blocking hooks, the
lockfiles, the TDD red-evidence gate and the bounded-subprocess rule, each restated as a rule a
report can be read against.

Excluded, because they are enforcement rather than method and cannot survive the transcription: hook
denial (exit 2 cancels a tool call — a rule only asks), O_EXCL lockfiles and atomic rename, sha512
capability consent, bounded subprocesses, TAP parsing for red evidence, the 32-rule filesystem
health table, context-utilisation telemetry, invisible-character injection scanning, the 19-host
installer, the MCP server and `state.json`. §10 carries each as a stated discipline; the fidelity
this costs is the whole difference between the source and this file.

Also excluded, because one agent on one task in one run cannot obey them: the milestone and backlog
layer, the knowledge graph and memory palace, the debug archive, the user profile, workstreams and
worktrees, cross-AI reviewer lanes, the 78-verb command surface (the file keeps the stages, not the
verbs).

Adherence: `res_artifacts` must contain a spec, a plan and a summary per plan under `.planning/`;
`res_subagents_spawned >= 3` (planner, checker, executor) and the checker is never the planner;
`res_tests_tampered` is I-equivalent to §10.2-3; every verify command appears in the report with its
output pasted. Expect high artefact cost — this rung is the ceiling of the ladder for structure, and
the test is whether structure pays for itself on a single task.
