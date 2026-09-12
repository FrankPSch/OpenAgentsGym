F. Four eyes: blind review by a subagent that sees only task and diff, blocking on `issue:`.
Stronger than m03_roles, which hands the reviewer a self-authored summary and is advisory.
Adherence checks: `res_subagents_spawned` >= 1 and the presence of REVIEW.md in the project_workspace.
Costs a second pass over the diff; expected to raise cost and lower defect rate.
