# Failure taxonomy

The fourteen failure modes of MAST — the Multi-Agent System failure taxonomy of
[Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657), 200+ traces, three
groups — with the observable sign each leaves in one of our run directories. It is a reading aid
for chapter 17: a losing cell gets one line naming the mode and the file the sign was read from.

It is harness content, not a methodology. It is never deployed, and nothing in the harness reads
it: the classification is done by hand until it has proved stable.

**Print mode returns a result, not a transcript.** `result.json` carries the final answer, the
usage counters and `num_turns`, and nothing about the steps between. Three modes are properties of
the step sequence alone and are marked *not observable yet*; they become observable when the
harness captures `stream-json`.

## 1. Specification and system design

| Mode | Observable sign in a run directory |
|---|---|
| Disobey task specification | `res_score` below the field on a green run, or `res_score_holdout` well under `res_score`: the suite the task named was not the suite that was satisfied. `res_artifacts` missing the document a D arm demanded is the same failure on the methodology's own text. |
| Disobey role specification | `res_subagents_spawned=0` on an R or F arm — `03`, `06`, `07`, `08_process_doctypes_roles_guardrails`, `09_foureyes`, `13_domain_roles` — where the arm's text hands the review to a subagent. The reverse on an arm that forbids one (`23_self_review`) reads the same way. |
| Step repetition | *Not observable yet.* `prf_turns` far above the field with `res_diff_lines` at or below it is the closest proxy, and it does not separate repetition from deliberation. |
| Loss of conversation history | *Not observable yet.* A late edit contradicting an early one is visible in the diff only when both survive into it. |
| Unaware of termination conditions | `res_hit_turn_cap=true`, or `res_subtype` naming a budget stop, on an arm whose text states a stop rule (`11_stop_criteria`, `19_relative_stop`, `27_escalation`). The rule was read and the run still did not end on it. |

## 2. Inter-agent misalignment

| Mode | Observable sign in a run directory |
|---|---|
| Conversation reset | *Not observable yet.* Nothing in `result.json` distinguishes a reset context from a long one. |
| Fail to ask for clarification | On `00_fail`: a run that edits code and reports success. The project's contradiction is unresolvable, so `res_diff_lines > 0` with an answer that names no contradiction is the mode itself. |
| Task derailment | `res_files_added_src` and `res_sloc_delta` above the field while `res_score` is not: work was done somewhere the task did not point. `res_artifacts` carrying a file no arm asked for is the same sign in Markdown. |
| Information withholding | `review.md` naming a defect the implementer's answer in `result.json` does not mention, on a run whose own text asked for known risks to be stated (`12_handoff_schema`, the R arms' four-field handoff). |
| Ignored other agent's input | `res_review_fixed=1` with `res_score` unchanged against the same cell at `REVIEW_FEEDBACK=0`, or the same `issue:` line standing in `review.md` and still true in the post-fix diff: the findings arrived and nothing moved. |
| Reasoning-action mismatch | The answer text in `result.json` against the diff: tests reported as run where `res_permission_denials > 0` shows the shell call was denied, files claimed changed that the diff does not carry, a stop rule claimed followed with `res_files_added_src` above the field. |

## 3. Task verification and termination

| Mode | Observable sign in a run directory |
|---|---|
| Premature termination | `res_score` below baseline-plus-nothing with `prf_turns` and `tk_cost_usd` well under the field, and no budget or turn stop in `res_subtype`. The run stopped because it decided it was done. The empty patch of chapter 17 (`res_files_added=0` and `res_diff_lines=0`) is its extreme. |
| No or incomplete verification | `res_permission_denials > 0` with an answer that reports a test result, or `res_score` far below `res_score_baseline` expectations on a run whose text requires the suite to be run (`01_process`, `11_stop_criteria`). The oracle ran; the agent did not. |
| Incorrect verification | `res_tests_tampered=true` — the suite was weakened, deleted or narrowed and the agent's own green was read off that. `res_score` high with `res_score_holdout` far below it is the softer form: the visible suite was satisfied and mistaken for the contract. |

Two of our columns are evidence for several modes at once (`res_score_holdout`,
`res_permission_denials`), so a cell may carry more than one line. Name each mode with the file or
column it was read from; a mode asserted without one is a guess, and the point of the vocabulary is
that it is not.
