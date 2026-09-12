# Kernel — the part of the method that moves to the next project unchanged

**Rule:** a kernel file names documents and roles by their function, never a path, a folder, a
project or a version. Where it must point at one, it points through the project's files —
`project_layout.md` for paths, `team_roles.md` for the roster and the shared rules, `skills_register.md` for which role invokes which skill, `world_model.md`
for what is being built, `briefings/_build_and_release.md` for the gates and how a run is executed,
`method_changes_and_retro.md` for what the method has learned here.
A project-specific fact found in a kernel file is a defect: move it out.

| kernel | project (stays in `00_methodology/`) |
|---|---|
| `operating manual.md` — the cycle, who decides, kept in the dark, the finding schema, document types, draining, handovers | `project_layout.md` — the directory table |
| `_creating_a_role.md` — who creates, what an instance is given, the brief, weights, limits; `planning.md` — intake, priority, size, the work order, done, leaving | `team_roles.md` — roster, shared rules, aliases; `document_types.md` — who writes what, who reads it; `skills_register.md` — which role invokes which skill |
| `verifier.md` | `world_model.md` |
| `multi_agent_collaboration_best_practices.md` — the Owner's source | `briefings/<role>.md`, `briefings/_build_and_release.md` (names the gates), `briefings/_multi_agent_practice.md` (carries this project's status) |
| `references/` — the research file; read by no role, cited by the practice briefing | `standards/` — the two naming standards |
| `skills/handover-writer_SKILL.md` | `method_changes_and_retro.md` |

Paths in kernel files are written relative to `00_methodology/`. To start a new project: copy
`kernel/` whole; write the six project files; nothing in `kernel/` changes. If it has to, the
split has been violated. Split 2026-09-03.
