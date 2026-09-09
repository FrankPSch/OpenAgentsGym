# OpenAgentsGym

**Version of 8 September 2026, 11:13 UTC.**

This document defines behaviour. `oam_manual.md` explains use.

**How to read it.** Each chapter states its subject and its design decisions first, and keeps the
exact rules, edge cases, exit codes and measured constants in a closing **Further details** section.
Reading only the leads gives the whole design; the details are what to read before changing
something.

**Where this document and the code disagree, the code is the truth.** The build has repeatedly run
ahead of the text: configuration keys, columns, whole methodologies and whole projects were made to
work first and written up afterwards. So expect
this document to be behind the repository rather than the other way round, and treat a passage that
contradicts `run_master.py`, `lib/oracle.py` or a project's `run_verification.py` as a defect in the
document — corrected here, never worked around in the code. The authoritative record of what
actually ran is never this document either: it is the run directory, which keeps the frozen
methodology snapshot, the launch line and the raw output of every invocation.

## Contents

| # | Chapter | Settles | Details |
|---|---|---|---|
| 0 | Terms | the vocabulary every other chapter uses | — |
| 1 | Situation | why methodology is the variable worth measuring | — |
| 2 | Solution | what the apparatus does about it | — |
| 3 | Framework or methodology | why the unit under test is prose and not code | — |
| 4 | Conventions | anchors, the ladder, and how an arm joins | — |
| 5 | Methodologies | the arms and what each one isolates | ✓ |
| 6 | Parameter catalogue | the `{{key=value}}` menu and what is wired | ✓ |
| 7 | Projects | the task ladder and which project ranks a campaign | ✓ |
| 8 | Directory structure | where everything lives, file by file | ✓ |
| 9 | Configuration | the campaign constants and their validation | ✓ |
| 10 | Environment | who owns the runtime, and pre-flight | ✓ |
| 11 | Verification and scoring | the oracle contract, the score and the metrics | ✓ |
| 12 | Run sequence | what happens between the call and the row | ✓ |
| 13 | Results | the columns, what they mean, and the logs | ✓ |
| 14 | Verified CLI | what was established about the CLI by probe | ✓ |
| 15 | Invariants | the properties no run may violate | — |
| 16 | Validity gate | what must hold before a result may be read | ✓ |
| 17 | Campaign protocol | how to run and read a comparison | — |
| 18 | Open | what is deliberately unsettled | — |
| 19 | Methodology content requirements | what a methodology must contain to be worth deploying | — |

A ✓ marks a chapter that closes with a **Further details** section: the exact rules, edge cases,
exit codes and measured constants. Reading only the leads gives the whole design.

## 0. Terms

| Term | Meaning here |
|---|---|
| **harness** | the scripts that set a run up, launch the CLI, verify the result and record the row — `run_master.py` and its callers. It never does the task itself. |
| **methodology** | one candidate being compared: a directory under `methodology/`, e.g. `03_roles`. |
| **entry file** | the single Markdown file a methodology deploys into the project_workspace. Held on disk as `agents_or_claude.md` and deployed as `CLAUDE.md` — the only engine there is. `AGENTS.md` is the name the same file takes under the GPT branch, which is open (chapter 18). |
| **project** | one task the agent is asked to do: a directory under `projects/` with a prompt, a reset template and an oracle. |
| **project_reset_template** | the pristine copy of a project. Every run starts from a fresh copy of it; it is never modified. |
| **project_workspace** | the working copy the agent actually edits, inside the run directory. |
| **run** | one execution of one methodology against one project, in its own directory under `local/runs/`. |
| **repeat** | one of several identical runs of the same pair, distinguished by the `_rNN` suffix. |
| **campaign** | a set of runs compared against each other; constants such as model and effort are fixed across it. |
| **anchor** | a deliberately degenerate methodology or project (`00_*`) that exists to bound the measurement, never to be improved. |
| **oracle** | the project's own verification script: it decides whether the task was done and produces the score. |
| **held-out suite** | a second test suite the project keeps in `holdout_tests/` and the agent never sees: the same contract as the visible suite on different inputs, copied into the run directory at verification time and scored as `res_score_holdout` (chapter 11). |
| **baseline** | the measurement taken on the pristine project_workspace before the agent starts. |
| **pre-flight** | the baseline check itself: environment built, oracle run, run aborted if the project cannot measure anything. |
| **review pass** | a second, independent invocation the harness makes between the agent exiting and the oracle running (chapter 12, step 7b). It is given the reviewer prompt, the project's `prompt.md` and the diff — never the implementer's output — and its findings are counted. `none` by default; `REVIEW_WEIGHT` sets how many independent reviewers one pass runs. The in-session variant of the same idea is the methodology `09_foureyes`. |
| **feedback** | `REVIEW_FEEDBACK=1`: the review pass acted on rather than only counted. One further implementer invocation on the reviewer's `issue:` lines (chapter 12, step 7c), after which the oracle scores the fixed code. Off by default, and meaningless without a review pass. |
| **validity gate** | the conditions that must hold before any result is interpreted (chapter 16). |
| **snapshot** | the frozen copy of the methodology stored inside the run directory — the record of what actually ran. |
| **parameter** | a `{{key=value}}` placeholder inside an entry file, rendered to its value on deploy and recorded as a column. |
| **SLOC** | source lines of code: non-blank, non-comment lines of every non-test `.py` file in the project_workspace, packages included. Docstring lines count — they are lines of the file, and excluding them would make a docstring free where MI already prices it. |
| **parsimony factor** | the multiplier that scales the test result by the maintainability of the code written: `clamp(MI_run / MI_REF, 0.8, 1.0)`, applied to the post-run score only (chapter 11). |
| **MI** | Maintainability Index, SEI-normalised, computed from Halstead volume, cyclomatic complexity and SLOC. |
| **effort** | the CLI's reasoning-effort setting (`low`…`max`), fixed per campaign. |
| **turn** | one agent step in a session; `prf_turns` counts them, and the turn cap bounds them. |
| **cache tokens** | tokens written to or read from the prompt cache. Cache reads cost a fraction of fresh input, so they are recorded separately. |

## 1. Situation

To have an LLM execute a project autonomously, we give it either a bare prompt or a methodology.

A methodology is a text describing process, roles, document types, tool policy and review
authority. It also carries the guardrails against common LLM failure modes such as overdelivery or
hallucination.

That methodology is the largest uncontrolled variable in agentic software development. Claims about
how to run an agent team are folklore — untested, unmeasured, and rarely separable from the model
that happened to run them.

## 2. Solution

OpenAgentsGym turns methodology into a measured variable. The same project and model are run under
different methodologies, and each run records what it cost and what it achieved.

The unit of comparison is a directory of plain Markdown, not code. Three consequences follow: the
same methodology can be handed to any model or CLI, a human can write one today, and an evolution
job can mutate it tomorrow against a chosen metric — tokens spent, cost, wall-clock, or the
project's own success criterion.

## 3. Framework or methodology

A **methodology** is prose the agent reads and may or may not comply with; a **framework** is code
the agent runs inside, which spawns agents, routes messages between them and can block a step until
a condition is met. Prose was chosen because the object of study is the CLI agents already in daily
use — a framework would replace them and become part of the treatment — and because adherence then
stays an outcome to be measured rather than something the harness forces.

| Goal | Pick |
|---|---|
| Improve the agent tools already used daily | methodology |
| Compare models under equal conditions | framework |
| Enforced gates, per-step cost caps, per-phase attribution | framework |
| Portability across vendors, operating systems and releases | methodology |

## 4. Conventions

The prefix `00_` marks an **anchor**: a degenerate case that exists to bound the measurement range,
never a candidate to be improved. Arms `01`–`08` form a feature ladder over four features — process
(P), document types (D), roles (R), guardrails (G): the low numbers are single features, the high
numbers combinations, and `08_process_doctypes_roles_guardrails` is the full stack. It was the
incumbent to beat until the level-3 screen of 8 September put it last on the ranking project;
the incumbent is now `29_invariants_test_first_relative_stop`, the composition that led that
screen at the lowest cost — provisional until repeats confirm it (chapter 16). A name is its
feature list, as every combination's is; `08` was `08_all` until the arms outside the ladder made
"all" untrue. The convention applies identically to
methodologies and projects.

Arms `09` and upwards sit outside the ladder. Each is one prose feature of its own — a candidate
the ladder's four do not express — read against `00_empty` for the main effect and against the
incumbent for whether it beats it, never combined into a grid. `28` and `29` are the exception
that proves the rule: compositions of screen winners, built from data rather than from a guess. A new one joins by existing: the harness reads the two directory listings rather than a
matrix, so nothing outside the arm's own directory is edited to add it. That is what makes the
ladder finite and the set of arms open, and `09`–`27` is what it holds today rather than what it
can hold.

Anchors are never tuned. Tuning an anchor destroys the reference it provides.

## 5. Methodologies

Methodologies are structural contrasts. Length is not controlled: the harness records `mth_chars`, the byte
count of the deployed entry file (0 for `00_empty`), and length is treated as a covariate in the
analysis.

Four features, one file each: **P** `process.md` (plan → implement → run tests → stop), **D**
`doc_types.md` (`PLAN.md`, `DECISIONS.md`, `SUMMARY.md`, each ≤ ~15 lines), **R** `roles.md`
(implementer hands off to a reviewer subagent, one round), **G** `guardrails.md` (the prohibitions).

| Methodology | Features | Contains |
|---|---|---|
| `00_empty` | — | nothing; the model works from the task prompt alone — anchor, does methodology matter at all |
| `00_sabotage` | — | contradictory instructions, vague done-criteria — anchor, if this does not score worse the apparatus is broken |
| `01_process` | P | `process.md` |
| `02_doctypes` | D | `doc_types.md` |
| `03_roles` | R | `roles.md` |
| `04_guardrails` | G | `guardrails.md` |
| `05_process_doctypes` | P+D | `process.md`, `doc_types.md` |
| `06_process_roles` | P+R | `process.md`, `roles.md` |
| `07_process_doctypes_roles` | P+D+R | `process.md`, `doc_types.md`, `roles.md` |
| `08_process_doctypes_roles_guardrails` | P+D+R+G | all four — the practical baseline |
| `09_foureyes` | F | `four_eyes.md` — blind subagent review of task and diff only; every `issue:` blocks |
| `10_planner_executor` | Pl | `planner_executor.md` — plan as a numbered file list in the reply, then execute exactly it; deviations stated |
| `11_stop_criteria` | S | `stop_criteria.md` — explicit stop rules; nothing built that the task did not name |
| `12_handoff_schema` | H | `handoff_schema.md` — five fixed hand-off fields; no roles, no process |
| `13_domain_roles` | Dr | `domain_roles.md` — two roles as persona briefs: Owns / Not yours / Rules / Delivers, plus an authority line each; the reviewer is a subagent, one round |
| `14_negative_scope` | N | `negative_scope.md` — an explicit do-not-read / do-not-consider list, and the omissions stated in the answer |
| `15_invariants` | I | `invariants.md` — five task-independent never-violate rules and a three-row table of what a change costs |
| `16_product_goal` | Pg | `product_goal.md` — one line above the task saying what the result is for and who reads it; every change justified against it |
| `17_finding_schema` | Fs | `finding_schema.md` — reviewer findings as severity / claim / evidence / changes / confidence, one per line |
| `18_justify_file` | J | `justify_file.md` — one written reason per new or reopened file, listed in the answer |
| `19_relative_stop` | Rs | `relative_stop.md` — each step compared with the previous one, not only with the task |
| `20_clean_restraint` | Cr | `clean_restraint.md` — the material issues worth fixing and the prohibitions that bound the fix; the smallest coherent change |
| `21_clean_catalog` | Cc | `clean_catalog.md` — named rule families with IDs, strict enforcement, the whole unit suite after every change |
| `22_clean_both` | Cr+Cc | both files, byte-identical copies — the catalog enforces, the restraint bounds it |
| `23_self_review` | Sr | `self_review.md` — once the tests pass, read the diff as a reviewer would, list the defects, fix that list; one round, no subagent |
| `24_two_proposals` | Tp | `two_proposals.md` — two approaches drafted in the reply before the first edit, one chosen with a stated reason, only that one built |
| `25_context_discipline` | Cd | `context_discipline.md` — what to read before the first edit, when to re-read, when to summarise; never re-read what has not changed |
| `26_test_first` | Tf | `test_first.md` — the test for the change written before the change; the agent's own tests are allowed and are not scored |
| `27_escalation` | Es | `escalation.md` — when the task, the tests and the code cannot all be satisfied, stop and name the contradiction; a guessed resolution is a failed run |
| `28_invariants_test_first` | I+Tf | `invariants.md` + `test_first.md`, byte-identical copies — the two single-feature arms that led the level-3 screen on `04_python_xlarge`; composed, not restated |
| `29_invariants_test_first_relative_stop` | I+Tf+Rs | `28` plus `relative_stop.md` — three short output constraints against the four long process layers of `08` |
| `30_delivery_kernel` | DK | `kernel.md` — a working real-world methodology's kernel transcribed, composite by intent: staged cycle with an exit condition per stage, producer never certifies (a reviewer subagent, `review_rounds=1`), finding schema with a severity ladder, change discipline against over-delivery, escalate rather than guess, halt after three. What needs a second task, a second seat or a person is left out (its `notes.md` lists it) |
| `31_pipeline_source` | PS | the same source untranscribed: its own entry file as it stands (4 KB) and its kernel directory verbatim — dangling project references, vendor names and role talk included, declared as deviations from 19.5. Read against `30`: what the transcription lost or added |
| `32_invariants_relative_stop` | I+Rs | `invariants.md` + `relative_stop.md` — the two cheapest arms on the level-3 front composed, without test first |
| `33_justify_file_invariants` | J+I | `justify_file.md` + `invariants.md` — the cheapest front arm with the strongest single constraint |
| `34_pipeline_source_with_reviewer` | PS+R | `31` plus the source's `team_roles.md` verbatim, which carries its reviewer rule; the reviewer seat's cost and benefit |
| `35_pipeline_source_with_reviewer_instance` | PS+R+i | `34` plus two sentences: the second reader is a separate instance with a fresh context, never the author's own — forces the seat `34` satisfied by self-check |
| `36_pipeline_change_discipline` | Cd | `change_discipline.md` — section 3 of the source's entry file verbatim (the eight over-delivery rules) behind the standard frame; the cheapest cut of the source |
| `37_pipeline_team_roles_only` | TR | `team_roles.md` verbatim behind the standard frame — the one file that separated `34` from `31`, alone |
| `38_pipeline_source_with_reviewer_relative_stop` | PS+R+Rs | `34` plus `relative_stop.md` first on its reading list — the best front arm with the cheapest stopping rule |
| `39_gsd_core_full_surface` | GSD-B/F | `Get-Shit-Done Full Methodology.md` — the archived `gsd-build/get-shit-done` repository transcribed at its final state; `doc_types=planning_tree`, `review_rounds=3`. Human gates, git and cross-vendor review are named in the text and cannot act in a run |
| `40_gsd_build_lean` | GSD-B/L | `Get-Shit-Done Lean Methodology.md` — `39` cut to what one run can obey: 33 roles to 8, four phase artefacts |
| `41_gsd_core_full` | GSD-F | `GSD Core - Faithful Methodology.md` — `open-gsd/gsd-core` v1.13.0 transcribed: the planning tree under `.planning/`, planner / checker / executor / verifier as separate instances; `doc_types=planning_tree`, `review_rounds=3` |
| `42_gsd_core_lean` | GSD-L | `GSD Core - Lean Methodology.md` — `41` cut to a single run: six roles, three artefacts under `.work/` (`doc_types=spec_plan_report`) |

### Further details

The ladder is the author's chosen subset of the 2⁴ factorial, not the full grid: the four
single-feature methodologies give the main effects, `05`–`07` the interactions with process, and
`08_process_doctypes_roles_guardrails` the full stack. The six unbuilt cells are the ones no
current question needs.

`09`–`27` are single-feature arms outside that ladder (chapter 4), one file each and no
combinations except `22`: `09_foureyes` isolates review, `10_planner_executor` plan-then-act without the roles
feature, `11_stop_criteria` the stopping rule without the rest of G, `12_handoff_schema` the
reporting format alone. `13`–`19` are the second set, each taken from a working multi-agent
methodology and reduced to the one thing it does: a role written as a charter rather than a
procedure (`13`), scope stated as what not to read (`14`), rules that hold whatever the task says
(`15`), a purpose above the task (`16`), a review output that is a schema (`17`), a price on every
file (`18`), and a stopping rule measured against the previous step (`19`). `20`–`22` are the
third set, taken from a pair of working code-quality standards: the restraint that says what not to
build (`20`), the rule catalog that says what quality is and cites an ID for every finding
(`21`), and both together (`22`). The pair is the first case of two features designed to pull
against each other — the catalog's "enforce everything, leave no debt" is the energy that
produces speculative abstraction, and the restraint is written against exactly that — so `22`
measures whether the restraint bounds the catalog. `23`–`27` are the fourth set, each a dimension
the ladder does not reach: the agent reviewing its own diff without a second agent (`23`), a choice
made between two drafted approaches rather than taken from the first one to arrive (`24`), reading
budgeted like any other cost (`25`), the test written before the code (`26`), and stopping on a
contradiction instead of resolving it silently (`27`). Twenty-nine methodologies in total.

A feature file is byte-identical in every methodology that includes it. A diff between two methodologies' copies of
the same file is a bug, not a variant.

The repository is under git from the first file; that is the reset point.

## 6. Parameter catalogue

Parameters appear in an active entry file as `{{key=value}}`, are rendered to their value when the
file is deployed into the project_workspace, and are extracted into `results_run.csv` as `mth_param_<key>`.
The agent therefore reads plain prose, and the configuration cannot drift out of sync with it.

### Further details

Rendering, the campaign stance and the per-key reference in 6.1 below.

**Rendering.** The pattern is `{{key=value}}` with key `[a-z_]+` and value `[^}]*`; the rendered
text is the value verbatim. Each key occurs at most once per entry file — a duplicate aborts the
run. Only the entry file is rendered, never project code.

This chapter is the author's reference and the evolution job's menu. It is not deployed: an agent
must not see the options it is not running under.

**Campaign 1 varies methodologies only.** `definition_of_done=strict` and `constraint_order=first` are
written into every methodology at that fixed value, so the methodologies render identically on those points and the
values are still extracted into the CSV. `doc_types` is not held constant: it is `full` in the methodologies
that contain D and `none` in the rest, set by the methodology rather than varied against it, and extracted
the same way. `00_empty` deploys nothing and therefore carries no parameters; its `mth_param_*`
columns are blank.

The anchors are outside the scheme in the same way. `00_empty` deploys no entry file at all and
`00_sabotage` deploys one that carries no placeholders and no Constraints/Task split — a degenerate
case is not a rendering of the ladder's template, and giving it one would make it a candidate. Both
therefore leave every `mth_param_*` column blank.

Campaign 1 was 37 runs: `03_python_large` × 11 methodologies × 3 repeats = 33, the validity gate
`00_fail` × {`00_empty`, `00_sabotage`, `08_process_doctypes_roles_guardrails`} × 1 repeat = 3, and
1 smoke run on `01_python_small`. Campaign 2 is the same shape over the twenty-nine methodologies of
chapter 5 and is **91 runs**: `04_python_xlarge` × 29 × 3 = 87, the same gate = 3, and 1 smoke run
(chapter 17). The formula is `ranking project × arms × REPEATS + 3 + 1`, so a new arm costs three
runs and nothing else.

**Exactly one parameter is wired at a time.** Unwired is not absent. Campaign 2 wires
`definition_of_done` inside `08_process_doctypes_roles_guardrails`. `review_rounds`, `gate_style`,
`phase_budget` and
`retry_policy` are present at one fixed value each and are therefore held constant, not wired: they
render, they are extracted, and nothing varies them.

The catalogue lists what is wired or held constant. A candidate that is not on an entry file at all
has no column.

### 6.1 Wired or held constant

**`definition_of_done`** — `strict` | `loose`. `strict`: "Stop when the stated task is done. Do not
add files, tests, documentation or refactorings that were not requested." `loose`: "Complete the
task and anything you judge necessary to leave the code in good shape." When the agent stops is the
largest single cost driver.

**`constraint_order`** — `first` | `last`. Identical content, permuted: constraints precede or
follow the task description in the entry file. Tests position effects on adherence and costs
nothing to vary.

**`doc_types`** — `none` | `notes` (a short decision log) | `full` (plan, decision log and summary); a transcribed arm may declare its own value naming its artefact set (`planning_tree`, `spec_plan_report` — arms `39`–`42`), recorded as-is in `mth_param_doc_types` and matched by no `res_artifacts` name, so its documents count in the diff columns like any other added file
| `adr` (plan and summary, and one numbered record per decision under `docs/adr/` instead of the
decision log). Documents are pure cost on single-session work with no downstream consumer and are
expected to pay off only on handover or multi-session tasks; `adr` and the `AGENT_BACKLOG.md` the feature
may ship are the multi-session shapes (chapter 19.3). No arm is on `adr` today.

**`review_rounds`** — a whole number, `1` on `09_foureyes`. How many blind review rounds the
methodology asks for; `four_eyes.md` refers to the number in the entry file rather than stating one,
so the round count is a rendered value and not a text edit. Held at `1`.

**`gate_style`** — `none` | `self_declared` | `artifact`. Whether a phase may be left on the agent's
own word (`self_declared`), only against a file it had to write (`artifact`), or not gated at all.
`artifact` is the only one that leaves evidence a later reader can check. Held at `none` on
`01_process`.

**`phase_budget`** — `none` | `<n>`. A cap on the steps a phase may take before it must report and
stop, borrowed from the frameworks that bound a phase rather than a run. Held at `none` on
`01_process`; the harness's own bound is the budget cap, which is a different thing.

**`retry_policy`** — `none` | `once_different_approach`. What happens after a failed attempt: stop
and report, or one further attempt that must differ in approach rather than in effort. Held at
`none` on `01_process`.

The last three are on `01_process` at their off value on purpose: a documented candidate that
renders and is extracted is a column ready to carry a treatment, and an arm that reads `none` for it
is the control the first wired campaign will need.

## 7. Projects

| Project | Content | Held-out tests | Role |
|---|---|---|---|
| `00_fail` | a task whose `prompt.md` contradicts the shipped test — the prompt specifies `f(2) == 5` in one place and `f(2) == 6` in another | — | anchor — the oracle cannot pass; catches a pipeline that reports success regardless |
| `01_python_small` | one function in `textstats.py`, 4 tests | — | smallest real oracle; the one harness smoke run |
| `02_python_medium` | three functions and a small class over closed integer intervals, 20 tests | 10 | the default pair of `run_smoke_model_02.bat`: real oracle, short run |
| `03_python_large` | a `ledger/` package of four sub-modules, three of them imported by `cli.py`, a 10-step work order in `prompt.md`, 24 tests, reference solution 82 SLOC | 12 | the ranking project for campaign 1; the first project large enough for structure to matter |
| `04_python_xlarge` | order intake and stock allocation: a `warehouse/` package — 11 source files over three packages, a semicolon CSV price list and a JSON order feed in `fixtures/` as the only definition of the two formats, a 14-step work order in `prompt.md`, 50 tests, reference solution 177 SLOC | 26 | the ranking project for campaign 2 |
| `05_python_refactor_large` | working but over-complex module, behaviour pinned by golden tests | 9 | refactor against fixed expected results; passes only if the golden tests stay green *and* SLOC falls below baseline. Saturates at level 3 (20 arms tie at 1.00): a cost check, not a ranking project |

The two anchors carry no held-out suite: `00_fail` cannot pass its visible tests and
`01_python_small` is a smoke run, so on neither would the gap mean anything. The four ranking
projects carry one each, sized at roughly half the visible suite (chapter 11).

`00_fail` runs the same pytest oracle as the others; only the task is unsatisfiable. It
bounds the project side exactly as `00_sabotage` bounds the methodology side. Together they answer
the only question that matters before a campaign: can this apparatus detect *worse*.

A project on which every methodology scores 1.00 ranks methodologies by cost alone and is not used for
ranking — the cheapest methodology wins by construction, which is a statement about the project, not about
methodology. `01_python_small` is that case by design and is used for exactly one smoke run.

### Further details

`04_python_xlarge` is the ranking project: on the level-3 screen of 8 September every arm passed
all 50 visible and 26 held-out tests and the 0.86–0.99 spread was the maintainability factor alone,
which is the discriminator this project was built to expose. `05_python_refactor_large` on the same
screen had 20 of 29 arms at 1.00 and a 0.94–1.00 field: it separates nothing at that level and is
kept as a cost and sanity check. `03_python_large` is the retained secondary. On `03` the visible fraction is 24/24 on every run of
campaign 1, so correctness carries no variance there and the whole ranking is produced by the
parsimony factor — a clamped one-decimal ratio that has already reached both ends of its range
(0.911 at the top, 0.801 on the floor). `04_python_xlarge` moves the discriminator back to the
tests and leaves MI as the tiebreaker; `03` stays in the campaign for continuity, not for the
ranking.

`05_python_refactor_large` inverts the usual shape: the baseline already passes its tests, so baseline
verification fails on the metric instead — the module is by definition not yet simplified. A no-op
therefore keeps every test green and still does not pass, which is what makes the project measure
simplification rather than caution. Its post-run score is 0.80, not 1.00: the untouched module's MI
of 34.1 against `MI_REF` 45.6 puts the parsimony factor on its floor, so the two signals agree — the
score says the code is unimproved and the exit code says the task is not done. `res_score_baseline`
is 1.00 on the same workspace, because the baseline is the unscaled test fraction. Reference values: baseline
75 SLOC / complexity 23 / MI 34.1; the stored reference reaches 30 SLOC / complexity 14 / MI 45.6
with all 17 golden tests and all 9 held-out tests green.

Build order: `00_fail` and `01_python_small` first, then `02_python_medium`, then
`03_python_large` as the campaign-1 ranking project, `05_python_refactor_large` once that has
produced a first campaign, and `04_python_xlarge` last, built from what campaign 1 showed about
where the variance was not.
The retired intervals project `03_python_tests` is superseded by `02_python_medium`, which is the
same shape with a class and 20 tests instead of 12.

## 8. Directory structure

```
OpenAgentsGym/
├─ oam_targetpicture.md                      # this document
├─ oam_manual.md                         # the user manual: how to use the apparatus. It explains
│                                       #   use and cites the chapter for every rule; this
│                                       #   document remains the definition of behaviour
├─ .llm_config.model_01                 # capability level 1: cheapest model, lowest effort (chapter 9)
├─ .llm_config.model_02                 # level 2: workhorse model; run.bat and run_smoke_model_02.bat
├─ .llm_config.model_03                 # level 3: frontier model, low effort; run_all_model_03.bat
├─ .llm_config.model_04                 # level 4: above the frontier tier; run_all_ and run_selected_model_04.bat
├─ .gitignore                           # local/ (runs, archive, to_delete), __pycache__/,
│                                       #   .pytest_cache/, .claude_config/
├─ run_smoke_model_02.bat               # one pair on level 2; no arguments
├─ run.bat                              # single run: run.bat <project> <methodology> [--config <path>]
├─ run_master.py                        # the only file that does work; stdlib only
├─ run_selected_model_04.bat            # the validity gate on level 4: a list of run.bat calls
├─ run_turbo_model_01.bat               # the whole matrix once on level 1
├─ run_screen_model_03.bat              # every methodology once on 04_python_xlarge, level 3, 3 workers
├─ run_all_model_03.bat                 # full matrix on level 3: every methodology on every project
├─ run_all_model_04.bat                 # full matrix on level 4
├─ rebuild_results_table.bat            # rebuilds results_repository.csv; also called by the above
├─ results_repository.csv               # consolidated table; merged with the local runs, published
│
├─ local/                               # machine-local, git-ignored (see .gitignore)
│  ├─ runs/                             # every run directory the harness writes
│  ├─ runs_archive/                     # earlier campaigns, kept out of the live table
│  └─ to_delete/                        # files moved instead of deleted
│
├─ lib/
│  ├─ oracle.py                         # the shared oracle implementation (chapter 11)
│  ├─ reviewer_prompt.md                # the review pass's own prompt (chapter 12, step 7b); it
│  │                                    #   is harness content, not a methodology, and lives here
│  │                                    #   rather than under methodology/ so the two `for /d`
│  │                                    #   loops over that directory stay a plain listing
│  ├─ reviewer_prompt_adversarial.md    # the same output contract, a reviewer told to break the
│  │                                    #   code; selected by REVIEW_PROMPT (chapter 9)
│  ├─ feedback_prompt.md                # the fix call's fixed instruction (chapter 12, step 7c)
│  └─ failure_taxonomy.md               # the fourteen MAST failure modes and the sign each leaves
│                                       #   in a run directory; a reading aid for chapter 17,
│                                       #   never deployed and read by no code
│
├─ methodology/
│  ├─ 00_empty/
│  │  ├─ copy_to_root/                  # intentionally empty: no entry file is deployed
│  │  └─ notes.md                       # documentation only, never deployed
│  ├─ 00_sabotage/
│  │  ├─ copy_to_root/agents_or_claude.md
│  │  └─ notes.md
│  ├─ 01_process/
│  │  ├─ copy_to_root/agents_or_claude.md   # active entry file, carries {{key=value}}
│  │  ├─ process.md                     # referenced from the entry file
│  │  ├─ tools.txt                      # optional, none shipped: one tool per line, replacing the
│  │  │                                 #   default --allowedTools list for this arm (chapter 15)
│  │  └─ notes.md
│  ├─ 08_process_doctypes_roles_guardrails/
│  │  ├─ copy_to_root/agents_or_claude.md
│  │  ├─ process.md
│  │  ├─ doc_types.md
│  │  ├─ roles.md
│  │  ├─ guardrails.md
│  │  └─ notes.md
│  ├─ 09_foureyes/
│  │  ├─ copy_to_root/agents_or_claude.md
│  │  ├─ four_eyes.md
│  │  └─ notes.md
│  ├─ 10_planner_executor/
│  │  ├─ copy_to_root/agents_or_claude.md
│  │  ├─ planner_executor.md
│  │  └─ notes.md
│  └─ …                                 # 02–07: the combinations listed in chapter 5; and
│                                       #   11_stop_criteria, 12_handoff_schema, 13_domain_roles,
│                                       #   14_negative_scope, 15_invariants, 16_product_goal,
│                                       #   17_finding_schema, 18_justify_file, 19_relative_stop,
│                                       #   20_clean_restraint, 21_clean_catalog, 23_self_review,
│                                       #   24_two_proposals, 25_context_discipline,
│                                       #   26_test_first, 27_escalation — same layout, one side
│                                       #   file each; 22_clean_both carries both of
│                                       #   20 and 21, byte-identical copies
│
├─ projects/
│  ├─ 00_fail/
│  │  ├─ prompt.md                      # harness: the task given to the agent; self-contradictory
│  │  ├─ run_verification.py            # harness: the same pytest oracle every project uses
│  │  ├─ reference/                     # fail.py + metrics.txt: the reference passes the two
│  │  │                                 #   satisfiable tests, 2/3 (chapter 11)
│  │  └─ project_reset_template/        # the project as the agent sees it
│  │     ├─ .environment
│  │     ├─ .requirements
│  │     ├─ <module>.py
│  │     └─ test_<module>.py            # contradicts prompt.md; cannot pass
│  ├─ 01_python_small/
│  │  ├─ prompt.md
│  │  ├─ run_verification.py            # thin wrapper over lib/oracle.py; SIZE_REF 9, MI_REF 63.3
│  │  ├─ reference/                     # textstats.py + metrics.txt
│  │  └─ project_reset_template/
│  │     ├─ .environment                # python=3.10  — the project defines its runtime
│  │     ├─ .requirements               # pytest — one package per line
│  │     ├─ textstats.py
│  │     └─ test_textstats.py           # 4 tests; fails at baseline, passes when done
│  ├─ 03_python_large/
│  │  ├─ prompt.md                      # spec plus a 10-step work order
│  │  ├─ run_verification.py            # SIZE_REF 82, MI_REF 31.7
│  │  ├─ reference/                     # ledger/ + metrics.txt, the measured known-good solution
│  │  ├─ holdout_tests/
│  │  │  └─ test_ledger_holdout.py      # 12 held-out tests; never enters the project_workspace
│  │  └─ project_reset_template/
│  │     ├─ .environment
│  │     ├─ .requirements
│  │     ├─ ledger/
│  │     │  ├─ __init__.py
│  │     │  ├─ parse.py                 # parse_amount, parse_lines
│  │     │  ├─ rules.py                 # categorise, DEFAULT_RULES
│  │     │  ├─ report.py                # round_half_away, aggregate, format_report
│  │     │  └─ cli.py                   # main(argv), imports the three above
│  │     └─ test_ledger.py              # 24 tests; the visible suite
│  ├─ 04_python_xlarge/
│  │  ├─ prompt.md                      # spec plus a 14-step work order, 882 words
│  │  ├─ run_verification.py            # SIZE_REF 177, MI_REF 16.0
│  │  ├─ reference/                     # harness-side only; never copied into a workspace
│  │  │  ├─ metrics.txt                 # the oracle's own output on the reference solution
│  │  │  └─ warehouse/                  # the known-good solution SIZE_REF and MI_REF are measured on
│  │  │     ├─ __init__.py
│  │  │     ├─ pipeline.py
│  │  │     ├─ cli.py
│  │  │     ├─ feeds/
│  │  │     │  ├─ __init__.py
│  │  │     │  ├─ money.py
│  │  │     │  ├─ pricelist.py
│  │  │     │  └─ orders.py
│  │  │     └─ rules/
│  │  │        ├─ __init__.py
│  │  │        ├─ pricing.py
│  │  │        ├─ stock.py
│  │  │        └─ validation.py
│  │  ├─ holdout_tests/
│  │  │  ├─ test_feeds_holdout.py       # 9
│  │  │  ├─ test_rules_holdout.py       # 7
│  │  │  ├─ test_pipeline_holdout.py    # 4
│  │  │  └─ test_scope_holdout.py       # 6; one composite per [later] backlog item
│  │  └─ project_reset_template/
│  │     ├─ .environment
│  │     ├─ .requirements
│  │     ├─ TASK_BACKLOG.md                  # 20 items; 8 [scope], 12 [later]
│  │     ├─ fixtures/
│  │     │  ├─ pricelist.csv            # defines the CSV format; 14 rows incl. 4 malformed
│  │     │  └─ orders.json              # defines the JSON feed; 6 orders, 17 lines
│  │     ├─ warehouse/
│  │     │  ├─ __init__.py
│  │     │  ├─ pipeline.py
│  │     │  ├─ cli.py
│  │     │  ├─ feeds/
│  │     │  │  ├─ __init__.py
│  │     │  │  ├─ money.py
│  │     │  │  ├─ pricelist.py
│  │     │  │  └─ orders.py
│  │     │  └─ rules/
│  │     │     ├─ __init__.py
│  │     │     ├─ pricing.py
│  │     │     ├─ stock.py
│  │     │     └─ validation.py
│  │     ├─ test_feeds.py               # 18
│  │     ├─ test_rules.py               # 18
│  │     └─ test_pipeline.py            # 14
│  └─ …                                 # 02_python_medium and 05_python_refactor_large, same
│                                       #   layout, `reference/` and `holdout_tests/` included;
│                                       #   00_fail and 01_python_small ship no held-out suite
│
└─ local/runs/                          # detail of the git-ignored run directory shown above
   ├─ _matrix_<campaign>_<YYYYMMDD_HHMMSS>.log   # one `--matrix` invocation's whole output, every
   │                                     #   line prefixed by the pair that produced it (chapter 12)
   └─ run_<methodology>_<project>_<YYYYMMDD_HHMMSS>_r<NN>/
      ├─ .venv/                         # built from the project's own .environment/.requirements
      ├─ methodology/                   # snapshot of methodology/<M>/ minus notes.md
      ├─ project_workspace/                     # copy of project_reset_template + rendered entry file
      ├─ holdout/                       # copy of projects/<P>/holdout_tests/, outside the
      │                                 #   project_workspace. Exists for the pre-flight score and
      │                                 #   again from step 8; deleted while the agent runs, since
      │                                 #   ../holdout/ would be readable from the workspace
      ├─ project_workspace_<n>/         # BEST_OF_N only: one workspace per candidate, kept as the
      │                                 #   record; the chosen one is copied to project_workspace/
      ├─ bestof_<n>/                    # BEST_OF_N only: each candidate's own verification.txt,
      │                                 #   metrics.txt and junit.xml, so they cannot overwrite
      │                                 #   each other's score, plus scored_workspace/ — the
      │                                 #   throwaway restored copy the score was taken on
      ├─ mcp_empty.json                 # {"mcpServers": {}} — the path passed to --mcp-config
      ├─ result.json                    # raw CLI output; under BEST_OF_N the chosen candidate's
      ├─ result_<n>.json, stderr_<n>.txt  # BEST_OF_N only: every candidate's own output
      ├─ review_cwd/                    # created empty; the review invocation's working directory,
      │                                 #   so nothing it writes can reach the scored workspace.
      │                                 #   REVIEW_WEIGHT>1: review_cwd_1..n, one per reviewer
      ├─ review_input.txt               # exactly what the reviewer was given on stdin — the record
      │                                 #   that the pass was blind; absent when REVIEW_PASS=none.
      │                                 #   One file whatever the weight: every reviewer gets it
      ├─ review.json                    # raw output of the review invocation (same_model only);
      │                                 #   review_1..n.json under REVIEW_WEIGHT>1
      ├─ review.md                      # the reviewer's findings, one Conventional Comment per
      │                                 #   line; under REVIEW_WEIGHT>1 one block per reviewer,
      │                                 #   each opened by a `# reviewer k` header
      ├─ fix_input.txt                  # exactly what the fix call was given on stdin; absent when
      │                                 #   REVIEW_FEEDBACK=0 or the review found no issue:
      ├─ fix.json, fix_stderr.txt       # the fix invocation's raw output and stderr (step 7c)
      ├─ fix_argv.txt                   # the fix invocation's own argv, kept apart from
      │                                 #   cli_argv.txt because FIX_MODEL can make the two
      │                                 #   launch lines genuinely differ (chapter 9)
      ├─ pytest_empty.ini               # the empty inifile pytest is pointed at with -c, so no
      │                                 #   pytest.ini the agent added is read (chapter 11)
      ├─ junit_baseline.xml             # pytest output of the pre-flight check
      ├─ junit.xml                      # pytest output of the post-run check, read by the oracle
      ├─ verification_baseline.txt      # pre-flight: passed / total / score
      ├─ verification.txt               # post-run: passed / total / score, plus the marker lines
      │                                 #   config_tampered=1 and timeout=1 where they apply
      ├─ metrics_baseline.txt           # pristine code metrics; the strict-reduction gate reads its sloc
      ├─ metrics.txt                    # post-run code metrics; lifted into the res_ columns
      ├─ run.log                        # everything the harness printed during this run (13.1)
      ├─ abort.txt                      # only on an aborted repeat: the exit code and the message
      │                                 #   (chapter 12); the next repeat still runs
      ├─ cli_help.txt, cli_argv.txt, stderr.txt, pip.log, venv.log, preflight_ancestors.txt
      ├─ review_argv.txt, review_stderr.txt   # the review invocation's own argv and stderr
      └─ results_run.csv                # this run's row
```

Example run id:
`run_08_process_doctypes_roles_guardrails_03_python_large_20260907_143012_r01`.

### Further details

**Requirement: one batch file runs one specific project under one specific methodology.** That file
is `run.bat <project> <methodology>`, e.g.
`run.bat 03_python_large 08_process_doctypes_roles_guardrails`; it does nothing but
`py -3 run_master.py %1 %2 %3 %4` and exits with that exit code, the third and fourth arguments
being the optional `--config <path>` pair. `run_selected_model_04.bat` is a plain list of
`run.bat` calls; `rebuild_results_table.bat` rebuilds `results_repository.csv`. Any Python
≥3.9 on the machine runs the master; the project venv is separate.

```
call run.bat 03_python_large 00_empty
call run.bat 03_python_large 00_sabotage
call run.bat 03_python_large 08_process_doctypes_roles_guardrails
```

## 9. Configuration

The campaign constants live in the `.llm_config.model_NN` files and nowhere else. There are four,
one per **capability level**, and a level is a model at an effort, packaged so that the batch files,
the documents and the campaign label can name it without naming a vendor:

| file | level | meaning | wired to |
|---|---|---|---|
| `.llm_config.model_01` | 1 | the cheapest model at the lowest effort; apparatus checks, rows never ranked | `run_turbo_model_01.bat` |
| `.llm_config.model_02` | 2 | the workhorse model at medium effort; single pairs and the smoke test | `run.bat` (default), `run_smoke_model_02.bat` |
| `.llm_config.model_03` | 3 | the frontier model at low effort; the full matrix | `run_all_model_03.bat` |
| `.llm_config.model_04` | 4 | the model above the frontier tier; the full campaign and the gate | `run_all_model_04.bat`, `run_selected_model_04.bat` |

A batch file that is bound to a level carries it in its name; `run.bat` and
`rebuild_results_table.bat` are the two that are not.

The vendor's model id appears in exactly one place, the `MODEL=` line of each file; a different
vendor or a new generation is four edited lines and no other change. Callers pass only
project and methodology, and optionally `--config <path>` to read the same keys from another file —
a relative path resolves against the repository root. `run_master.py` defaults to level 2.

```
ENGINE=claude
MODEL=claude-sonnet-5
EFFORT=medium
MAX_TURNS=60
MAX_BUDGET_USD=4.00
REPEATS=1
CLAUDE_CONFIG_DIR=
REVIEW_PASS=none
REVIEW_MAX_BUDGET_USD=1.00
REVIEW_MODEL=
REVIEW_CMD=
REVIEW_PROMPT=
REVIEW_WEIGHT=1
REVIEW_FEEDBACK=0
FIX_MODEL=
BEST_OF_N=1
```

The values shown are the smoke-run setting. Campaign 1 sets `REPEATS=3`; campaign 2 sets
`REPEATS=3` and `MAX_BUDGET_USD=4.00`. The raise is required rather than cosmetic: the dearest
campaign-1 run on `03_python_large` cost $0.882, and ×2 for the size of `04_python_xlarge` ×2.05
for the level-3 model is ≈$3.62, so a $2.00 cap would truncate the R and F arms on that level alone — a censoring
indistinguishable from a methodology effect.

### Further details

`MAX_TURNS` is not passed to the CLI — 2.1.251 has no such flag (chapter 14). It is the reporting
threshold behind `res_hit_turn_cap`; the run is bounded by `--max-budget-usd` alone.

`CLAUDE_CONFIG_DIR` is blank, meaning unset: the CLI stays on the user's own config directory. Set
to a path — relative paths resolve against the repository root, as for `--config` — it is exported
into the CLI's environment and isolates the campaign from the user profile, which is what a machine
whose user-level entry file is not suppressed needs. The directory needs a one-time `claude login`
inside it before the first run; an unauthenticated config dir fails every run identically.

`ENGINE=claude` is the only valid value. `MODEL` is pinned to the canonical id, never the `opus`
alias — an alias silently re-points to a different model between campaigns and invalidates
comparisons. The rule is enforced, not stated: pre-flight aborts with exit 4 on a `MODEL` without a
dash-separated version part (`opus`, `sonnet`, `haiku`, `sonnet-latest` — a canonical id carries a
digit in a part after the first, as `claude-sonnet-5` does), and on `CLAUDE_FALLBACK_MODEL` or
`--fallback-model` appearing in the environment or in the config file, since a fallback substitutes
another model on overload with no visible error (chapter 14).

The four `REVIEW_*` keys configure the independent review pass (chapter 12, step 7b).
`REVIEW_PASS` is `none` | `same_model` | `other_model`; unset or blank reads as `none`, so a config
file written before the pass existed keeps working, and any other value aborts with exit 4 rather
than becoming a silent no-op. `none` is the campaign-1 and campaign-2 setting: the pass is a second
invocation, a second cost and a treatment, so it is on for a whole campaign or off for it.
`REVIEW_MAX_BUDGET_USD` is the review invocation's own `--max-budget-usd`, a quarter of the
implementer's cap because the reviewer reads a diff and writes at most twenty lines; it never
touches the implementer's budget. `REVIEW_MODEL` blank on `same_model` means the implementer's
model and a named value takes the same alias rejection as `MODEL`; on `other_model` it is the
foreign vendor's id, which the digit-in-a-dashed-part rule cannot judge (`gpt-5`, `o3`), so it is
taken as given — recorded either way as `cfg_review_model`,
which on `other_model` is the only record there is, since a foreign CLI does not report back what
it served. `REVIEW_CMD` applies to `other_model` alone: a command, not a shell line, run with the
reviewer prompt on stdin and its stdout taken as `review.md`. Blank there aborts with exit 6 before
any tokens are spent, as does an executable `shutil.which` cannot find — the same class of failure,
and the same exit code, as a flag the CLI does not offer.

`REVIEW_PROMPT` selects the reviewer's prompt file: blank is `lib/reviewer_prompt.md`, and any
other value is a path relative to the repository root. `lib/reviewer_prompt_adversarial.md` is the
second one shipped — the same output contract, a reviewer instructed to break the code against the
task rather than to read it, and to raise `issue:` only where it can name a failing input. The
prompt is a treatment like the model, so the file name is recorded as `cfg_review_prompt` and a
path that does not exist aborts with exit 4.

`REVIEW_WEIGHT` is how many independent reviewers the pass runs, default `1`. Above 1 the harness
makes that many invocations of the same prompt on the same diff — the same input stream, kept once
as `review_input.txt` — each in a working directory created empty for it, and concatenates their
answers into one `review.md` under a `# reviewer k` header per block. `res_review_findings`,
`res_review_issues` and `res_review_actionable` are counted over all of them and the `tk_review_*`
counters are summed, so a weight is a cost as well as a sample; `prf_review_s` is the whole pass's
wall-clock. The number is recorded as `cfg_review_weight`, because two campaigns that differ only in
it are two treatments. Non-numeric or below 1 aborts with exit 4 naming the key. The reason for the
key is that one reviewer's silence is not evidence: a pass that files nothing measures the reviewer
as much as the code, and `n` of them on the same diff is the cheapest way to tell those apart.

`REVIEW_FEEDBACK` is `0` | `1`, default `0`. `1` turns the counted review into a methodology
element that acts: the harness runs one further implementer invocation on the reviewer's `issue:`
lines (chapter 12, step 7c) and the oracle then scores the fixed code. It is meaningless without a
review, so `1` with `REVIEW_PASS=none` aborts with exit 4 naming the key rather than running as a
silent no-op.

`FIX_MODEL` is the model that fix call runs on. Blank means `MODEL`, which is what the call used
before the key existed, and it is meaningful only with `REVIEW_FEEDBACK=1` — recorded as
`cfg_fix_model`, blank wherever the feedback loop is off. Set, it takes the same alias rejection as
`MODEL` and aborts with exit 4 on an id without a version part, for the same reason: it is a second
model id on the row and an alias there re-points as silently as the first one would. Nothing else
on the launch line moves with it — same tools, same budget key, same cwd — so the fix call differs
from the implementer's in exactly one recorded value. The key exists because the review loop has
two model-sized decisions in it and one setting cannot express both: whether a weaker reviewer
still finds what matters is `REVIEW_MODEL`, and whether applying named issues is a smaller job than
writing the code is this one.

`BEST_OF_N` is how many implementer invocations produce one row, default `1`. Above 1 the harness
runs that many sequentially and keeps the best (chapter 12, step 7a). Non-numeric or below 1 aborts
with exit 4 naming the key. All four keys, `FIX_MODEL`'s id and `REVIEW_PROMPT`'s path, are
validated at pre-flight before any tokens are spent, as are the run constants: `EFFORT` must be one
of `low | medium | high | xhigh | max`, `MAX_BUDGET_USD` a positive number, `MAX_TURNS` and
`REPEATS` integers of at least 1 — each missing or malformed is exit 4 naming the key.

## 10. Environment

The runtime is defined by the project, not by the harness and not by the campaign config. Each
project's `project_reset_template/` carries:

- `.environment` — one line, machine-readable: `python=3.10`
- `.requirements` — one package per line, pip-installable

The harness reads both from `project_reset_template/`, never from the project_workspace, and prepares the
environment before the agent starts, in the run directory and outside the project_workspace so it never
appears in the diff:

```
py -3.10 -m venv local\runs\<id>\.venv
local\runs\<id>\.venv\Scripts\python.exe -m pip install -q -r projects\<P>\project_reset_template\.requirements
```

### Further details

pip is invoked as a module of the venv's own interpreter rather than through the `pip` shim: the
shim carries a hard-coded shebang and breaks when the run directory is moved, and `-m` cannot
install into the wrong environment.

The interpreter is looked up as `py -<ver>` on Windows and as `python<ver>` (then `python3`) on
POSIX, and the venv's binaries are `Scripts/` or `bin/` accordingly. The POSIX branch exists so the
harness can be dry-run inside a container; the supported target is Windows, and a result produced
anywhere else is a smoke test of the harness, not a measurement.

**Pre-flight.** Before the agent is launched, the verification is run once against the pristine
project_workspace. If the interpreter is missing or the baseline does not import, the run aborts before a
single token is spent. Without this check an environment breakage appears in the results table as a
methodology failure, indistinguishable after the fact.

A project must pin a version that `py -0` lists on the machine; if it does not, the run is skipped
and recorded as such, never silently run under a different interpreter. This machine lists 3.10,
3.9, 3.6, 3.5 and 2.7 — 3.12 is not installed, which is why the projects pin 3.10.

## 11. Verification and scoring

Each project owns its oracle: `projects/<P>/run_verification.py`, stdlib only, executed with the
run's venv python. There is no shared root script — a project defines its own runtime (chapter 10)
and defines its own success the same way. The harness only calls it and reads what it writes.

**Contract.** Called with five arguments: the project_workspace path, the run directory,
`baseline` or the empty string — `baseline` writes `verification_baseline.txt` instead of
`verification.txt` — the run's held-out directory or the empty string, and the
`project_reset_template` or the empty string. It runs
`python -m pytest -q -c <run dir>\pytest_empty.ini -o addopts= -p no:cacheprovider
--rootdir=<project_workspace>
--junitxml=<run dir>\junit.xml <project_workspace>\<each template test file> [<holdout dir>]`,
reads passed and total per test file from the junit XML, and exits with one of three codes:

**The invocation is immune to workspace configuration.** `-c` names an empty ini the oracle writes
in the run directory, which makes that file the one and only inifile: a `pytest.ini`, `tox.ini`,
`setup.cfg` or `pyproject.toml` in the project_workspace is not read at all, and `-o addopts=`
clears any `addopts` that reached pytest another way. Without this an added
`addopts = -k test_origin` deselected every test that contradicted the code and `00_fail` scored
1.00 with `res_tests_tampered=false`.

**It runs the template's test files, never tests the agent added.** The fifth argument is what
makes that possible: the file names are the `test_*.py` glob of `project_reset_template` plus its
`conftest.py` if it ships one, and pytest is pointed at those paths under the project_workspace and
at nothing else — never at the directory. Without it an arm raises its own score by writing a file
of passing tests, and the more tests it writes the smaller the weight of the ones it failed. The
files themselves are restored from the template before scoring (step 8), so what runs is the
project's suite verbatim. Called without the fifth argument the oracle falls back to the
workspace's own root glob, which is the standalone shape and correct only on a pristine template.

| Code | Meaning |
|---|---|
| 0 | pass |
| 1 | fail |
| 2 | environment or setup error |

The third code is not optional. Without it a broken interpreter is recorded as a methodology
failure and the two are indistinguishable afterwards. The rule: whenever pytest wrote a `junit.xml`
that parses, the run is scored from it whatever pytest's exit code — a collection error raised by the
agent's own code (a syntax or import error; pytest exit `2`) is a fail, exit 1 with `score=0.00`, and
a junit with no test case at all scores 0.00 over the template's own test-function count. Only
pytest exit `3` (internal error), `4` (usage error), pytest not being importable, or no parseable
`junit.xml` map to 2 — those alone are not statements about the code under test. An **emptied or
deleted implementation** is not one either: pytest ran and reported the import failures, so a
workspace measuring 0 SLOC is a fail with `score=0.00` and the metrics at zero, never exit 2 with a
blank score. `res_verification_error` is exit code 2 on the post-run check, and
`res_verification_exit` is that exit code recorded raw.

**A verification that does not finish is a fail.** The pytest invocation is bounded by
`VERIFY_TIMEOUT_S = 300` seconds in `lib/oracle.py`; on the bound the process tree is killed —
`taskkill /T /F` on Windows, `killpg` elsewhere, since killing the direct child alone leaves its
own children holding the pipes — and `verification.txt` is written with `passed=0`,
`total=<the template's test count>`, `score=0.00` and a `timeout=1` marker line, exit 1. It needs
no column of its own: `res_verification_error` stays `false` and `res_verification_exit` stays 1,
and `run.log` says `TIMEOUT`. The harness bounds its own call of `run_verification.py` at 420
seconds as a second layer, for the case where the oracle hangs where pytest's bound cannot see it.
An infinite loop in generated code otherwise stalled a matrix worker forever.

**Score, not verdict.** The script writes `verification.txt` into the run directory:

```
passed=7
total=10
score=0.70
passed_holdout=5
total_holdout=12
score_holdout=0.42
```

`passed` and `total` are the visible suite alone; the held-out lines are blank when the project
ships no held-out suite. A **skipped test is neither passed nor failed** and leaves the fraction
entirely: `passed = tests − failures − errors − skipped` as before, but `total = tests − skipped`,
so a `skipif` on the machine's interpreter or on a missing package no longer lowers a score for a
reason that has nothing to do with methodology. The master reads it into `res_score`; `res_verification_passed` is the oracle's own verdict, exit
code 0 on the post-run check, and blank when the project ships no tests. It is deliberately not
`score == 1.0`: on `05_python_refactor_large` a run can hold every golden test green, fail the
strict-reduction gate and still carry a score of 1.00, and a threshold on the score would record
that as a pass. A binary outcome needs
roughly an order of magnitude more runs than a continuous one to reach the same confidence,
which is the difference between a campaign you can afford and one you cannot.

**Parsimony is part of the score.** Solving a task by writing more code, or more convoluted code,
is not the same as solving it well, so the test result is scaled by a parsimony factor built on the
**Maintainability Index** — the SEI-normalised form, in the one shape `lib/oracle.py` computes.
The definition is written out here because a metric quoted loosely is not reproducible:

```
per file, over the AST:
  operators   every node of type BinOp, UnaryOp, BoolOp, Compare, Assign, AugAssign, Call,
              Subscript, Attribute, Return, If, For, While, With, Raise, Try, Import,
              ImportFrom or Lambda; n1 = distinct node types, N1 = occurrences
  operands    every Name by its id and every Constant by repr(value);
              n2 = distinct values, N2 = occurrences
  V           = (N1 + N2) * log2(n1 + n2)  — Halstead volume, and 0 when n1 + n2 <= 1

over the non-test sources of the project_workspace, packages included:
  V           = the sum of the per-file volumes
  G           = per callable, 1 + its decision points, summed; a decision point is If, For,
                AsyncFor, While, ExceptHandler, IfExp, a comprehension clause or Assert, and a
                BoolOp counts len(values) - 1
  L           = SLOC

MI          = round(max(0, min(100, (171 - 5.2 ln V - 0.23 G - 16.2 ln L) * 100 / 171)), 1)
              and 0.0 when V = 0 or L = 0
factor      = round(clamp(MI_run / MI_REF, 0.8, 1.0), 3)
score       = (passed / total) * factor
```

`ln` is the natural logarithm, `log2` the binary one. Three details are part of the definition
rather than of the implementation: the per-file volumes are **summed**, which is not the volume of
the concatenated sources; complexity is counted **inside callables only**, so module-level code
adds nothing and a nested callable's decision points are counted in both it and its enclosing
callable; and a test file — `test_*.py` or `*_test.py` — is not a source, nor is anything under
`.venv`, `__pycache__`, `.git`, `.pytest_cache`, `build` or `dist`. `MI_REF` is the
Maintainability Index of a known-good solution, declared in the project's oracle. Matching or beating
the reference scores 1.0; bulkier or more convoluted code scores proportionally less, floored at 0.8
so parsimony can never outweigh correctness. The factor is 1.0 only where `MI_REF` is unset — there
is nothing to divide by; **an MI of 0 takes the 0.8 floor**, since it is the worst measurable code
rather than the absence of a measurement, and returning 1.0 there handed an emptied or unparsable
source tree the best factor there is. The factor is applied to the post-run score only — `res_score_baseline` is the unscaled test
fraction, so the two are comparable in the same direction.

### Further details

MI supersedes the earlier raw-SLOC factor because it already combines volume, complexity and size —
using both would count size twice. The SLOC factor `clamp(1 - 0.1 log2(SLOC / SIZE_REF), 0.8, 1.0)`
is gone: it was computed and written and read by nothing, which is worse than absent, because a
number in a file invites a reader to believe it means something. `metrics.txt` now holds only what
is lifted into the results table plus `mi_ref` — the value the factor was divided by, kept so a row
can be recomputed from the run directory, and not a column because it is a project constant
identical on every row of that project. Halstead volume is an intermediate of MI and is not written
at all.

**Metrics recorded every run.** The oracle writes `metrics.txt`, and the harness lifts it into the
results table: `res_sloc`, `res_chars`, `res_complexity`, `res_mi`, `res_parsimony_factor`,
`res_max_func_sloc`, `res_max_nesting`, `res_lint_errors`, `res_docstring_cov`,
`res_comment_density`. All are computed from the AST with the standard library only:

| Metric | Definition |
|---|---|
| `sloc` | non-blank, non-comment lines of the non-test sources, docstring lines included, walked recursively so packages count; `.venv`, `__pycache__` and `.pytest_cache` are skipped |
| `chars` | total characters of the same files |
| `complexity` | cyclomatic, decision points + 1 per callable (McCabe) |
| `mi` | Maintainability Index as above |
| `max_func_sloc` | longest callable — catches one monster function a line count would average away |
| `max_nesting` | deepest block nesting |
| `lint_errors` | unused imports, bare `except`, shadowed builtins |
| `docstring_cov` | share of the module and its public callables carrying a docstring |
| `comment_density` | comment lines per 100 SLOC |

The same metrics are written at pre-flight as `metrics_baseline.txt`, so every run stores its own
starting point rather than a project constant: `res_sloc_baseline` is that file's `sloc` and
`res_sloc_delta = res_sloc − res_sloc_baseline` is the code the run actually wrote, which is what
`res_sloc` alone cannot say on projects whose templates differ by a factor of three.

Diff statistics use the same recursive listing. The harness adds `res_lines_added` and `res_lines_removed` separately rather than one churn figure —
on a simplification task, removal is the work — plus `res_artifacts`, the list of declared artifacts
(`PLAN.md`, `DECISIONS.md`, `SUMMARY.md`, `REVIEW.md`, `AGENT_BACKLOG.md`, `RUN_NOTES.md`, and every file
matching `docs/adr/*.md`) the agent actually produced. The glob is there because one declared
artifact is a directory of files rather than a name: `doc_types=adr` writes one numbered record per
decision (chapter 19.3), and each is listed by its path.
That list is adherence evidence: a methodology that demands a plan either left one behind or did not.

**A project without tests cannot be scored.** If the reset template ships no test file, the oracle
records a blank score and stops. Any test file found in the project_workspace was written by the
agent, and running it would let a methodology grade its own homework.

**Per-project constants.** Each oracle declares four values; these are what make a campaign
reproducible, so they are recorded here as well as in the code:

| Project | `SIZE_REF` | `MI_REF` | `EXPECTS_TESTS` | `REQUIRE_SMALLER_THAN_BASELINE` |
|---|---|---|---|---|
| `00_fail` | 4 | 77.3 | true | false |
| `01_python_small` | 9 | 63.3 | true | false |
| `02_python_medium` | 42 | 41.7 | true | false |
| `03_python_large` | 82 | 31.7 | true | false |
| `04_python_xlarge` | 177 | 16.0 | true | false |
| `05_python_refactor_large` | 30 | 45.6 | true | true |

Every pair is measured, and the solution it was measured on is on disk: `projects/<P>/reference/`
holds the module or package plus `reference/metrics.txt`, the oracle's own output on it. No value
in this table is a literal any more — a constant that cannot be re-measured from an artefact is a
number the reader has to trust. Each reference passes its project's visible **and** held-out suite,
except `00_fail`, whose task is unsatisfiable by construction: its reference satisfies the two
tests that can be satisfied and the oracle exits 1 on it, as it must on every run of that project.
`05_python_refactor_large`'s reference passes the strict-reduction gate as well, at 30 SLOC against
the template's 75.

`04_python_xlarge`'s two values are the oracle's own output on its `reference/`, kept there as
`reference/metrics.txt` beside the solution they were measured on: 177 SLOC, complexity 67, MI
16.0. The magnitude is what the size predicts — MI falls with `ln(SLOC)`, so 82 → 177 costs about
15 MI points — and it is the reason MI is the tiebreaker and not the discriminator here: the
pristine template measures 67 SLOC / MI 40.6, and from `MI_REF=16.0` the parsimony factor spans
roughly 177–200 SLOC before it reaches the 0.80 floor.

Both constants come from measuring a verified reference solution with the same oracle: the SLOC and
the MI of an implementation that passes the project's whole suite. `SIZE_REF` is declared by each
oracle and recorded in this table; nothing scores it and the oracle no longer writes it out. A
project whose `MI_REF` is unset scores on correctness alone and is not comparable with the rest,
which is why every project carries one.

**The strict-reduction gate.** `REQUIRE_SMALLER_THAN_BASELINE` is the extra condition
`05_python_refactor_large` needs and no other project has. Its template already passes its own tests, so the
oracle inverts at baseline: green returns exit 1, because a module that has not been touched is by
definition not yet simplified, and anything else returns 2. After the run it returns 0 only if the
suite is still green *and* the workspace SLOC is strictly below the baseline SLOC read back from
`metrics_baseline.txt`; a missing baseline is exit 2.

**The baseline must fail.** A project with an oracle ships a test suite that fails on the pristine
template and passes once the task is done correctly. Pre-flight therefore *expects* exit 1; exit 0
means the project cannot measure anything and exit 2 means the environment is broken, and both abort
the run before any tokens are spent. A template that cannot even be collected is exit 1 like any
other failing baseline, so pre-flight does not catch it; the template author's own test run does. Pre-flight writes `verification_baseline.txt`, whose score is
recorded as `res_score_baseline` — it is already computed, and the post-run gain is meaningless
without it. Pre-flight passes the held-out directory too, so `verification_baseline.txt` carries
the baseline held-out fraction as well; it is not a column, because on a pristine template it only
restates that nothing is implemented yet.

**Pre-flight for oracle-less projects.** A project whose template holds no `test_*.py` is
oracle-less: `run_verification.py` returns 0 and writes `passed=`, `total=` and `score=` all blank,
so pre-flight only checks that the exit code is not 2.

**Tests are restored before scoring.** The cheapest way to pass a suite is to weaken or delete it,
and some methodologies will find that route. The tamper set is every file in `project_reset_template/` whose
name matches `test_*.py`, `conftest.py`, `pytest.ini`, `pyproject.toml`, `.requirements` or
`.environment`, plus every file under `fixtures/`. `res_tests_tampered=true` if any of them is
missing from the project_workspace or differs
byte-for-byte from the template, blank when the project ships none of them. All are restored from
the template before scoring. Fixtures are in the set because on a project whose input formats are
defined by a fixture and nowhere else (`04_python_xlarge`) rewriting the file the code failed to
parse is the same move as weakening a test, and would score 1.00 against the agent's own input. The
`test_*.py` glob is root-level only, which is why a project's visible suite stays at the template
root: a suite in a subdirectory would not be restored.

**Restoring is not enough: an added file has nothing to restore.** The restore puts template files
back, so a file the agent *added* survived it untouched — an added `pytest.ini` carrying
`addopts = -k test_origin`, or an added `conftest.py` monkeypatching the module under test. The
oracle therefore **deletes every pytest configuration or hook file the template does not ship**
before it scores anything: `conftest.py` at any depth, `pytest.ini`, `.pytest.ini`, `tox.ini`,
`setup.cfg`, `pyproject.toml`. The deletion is tampering — it is written to `verification.txt` as
`config_tampered=1` and the harness lifts it into `res_tests_tampered=true` — and the row is then
scored on the cleaned tree, exactly as a restored one is.

**And the suite must still be there.** After scoring, the visible test cases the junit carries
(skipped ones included, since a skip is collected and merely leaves the fraction) are compared with
the number of `test_*` functions the template's own suite defines. A shortfall means tests were
deselected or made uncollectable, so **the missing tests are counted as failures** — the
denominator is raised back to the template's count — rather than quietly shrinking the fraction the
run is scored on.

**The held-out suite.** The tests in the project_workspace are the spec the agent works against, so
code can be written that satisfies exactly those inputs and nothing more. Each ranking project
therefore ships a second suite in `projects/<P>/holdout_tests/`, roughly half the size of the
visible one, exercising the same public contract on inputs the visible suite does not use — an
unsorted or duplicated interval, both thousands conventions in one file, a discount that rounds
onto the free-shipping threshold. It tests **only the contract stated in `prompt.md`**: testing
unstated requirements would penalise a methodology for not reading the author's mind and turn the
column into noise.

A held-out test that checks scope — that an out-of-scope feature was *not* built — must assert a
positive behaviour in the same test, and the absence beside it. A bare absence assertion passes on
the pristine template, which breaks the chapter-16 requirement that the held-out suite fails at
baseline and makes the test evidence of nothing.

The harness copies it into `local/runs/<id>/holdout/` and never into the project_workspace — which
is why it is not in the tamper set. **It is not on disk while the agent runs.** `local/runs/<id>/`
is one directory above the workspace the agent works in, so a suite copied before step 7 is
readable as `../holdout/` by any python the agent starts. Pre-flight copies it, scores the baseline
with it and deletes it again before the CLI is launched; step 8 re-creates it after the agent has
exited. Under `BEST_OF_N` it is not copied at all until step 8: candidates are launched and scored
in turn, so a directory copied to score candidate 1 would sit beside candidate 2's workspace while
its agent runs, and candidate selection is on the visible `res_score` alone.

**A known limitation, recorded rather than solved.** The tool list allows `Bash(python:*)`, and a
python process can read any path on this disk: `projects/<P>/holdout_tests/` and
`projects/<P>/reference/` are reachable by a relative path from the workspace, whatever the harness
does with `local/runs/<id>/`. Removing the run's own copy closes the accidental route — reading
`../holdout/` needs no intent — but not the deliberate one. Nothing in the harness can detect it:
the CLI reports tool calls, not the paths a subprocess opened, and only a sandbox or a filesystem
ACL around the repository would prevent it. It is recorded here, in chapter 14 and in chapter 15 as
a property of the apparatus, and a run suspected of it is a run to discard by hand. Both suites run
in one pytest invocation with the project_workspace as cwd and as `--rootdir`, so the held-out
file's `import <module>` resolves exactly as the visible suite's does, and the junit XML is counted
per file. The held-out fraction is written as `passed_holdout` / `total_holdout` /
`score_holdout` and lifted into `res_score_holdout`, unscaled by parsimony. It changes neither
`score` nor the exit code: `res_score` stays the visible result, and the gap
`res_score − res_score_holdout` is the direct measure of fitting-to-the-test.

**Projects without an oracle.** All five projects now ship a test suite, so none writes the blank
triple. The path stays: a project that ships none records blank, never `false` — a blank is honest,
`false` looks like a measurement.

## 12. Run sequence

`run.bat <project> <methodology> [--config <path>]` is the single-run entry point and calls
`run_master.py`; `run_selected_model_04.bat` is the multi-run list. There is no per-combination file.

`run_smoke_model_02.bat` takes no arguments and exists to be double-clicked: it runs one fixed pair on
level 1 (`.llm_config.model_01`), rebuilds the table and pauses so the window survives. It is `run_turbo_model_01.bat`
with one pair in place of the matrix; the two files differ in nothing else. The default pair is
`02_python_medium 00_empty` — the smallest project with a real oracle that still has surface,
combined with the cheapest methodology, and it exercises the full path including venv, pre-flight,
pytest and scoring. Changing the default is a one-line edit in that file.

**Entry points.** Six batch files and one matrix, and the cost tells them apart:

| File | Does | Order of magnitude |
|---|---|---|
| `run.bat <P> <M> [--config <path>]` | one pair, `REPEATS` times; exits 2 on fewer than two arguments | 1 pair × `REPEATS` |
| `run_smoke_model_02.bat` | `02_python_medium 00_empty --config .llm_config.model_02`, then rebuilds | 1 run on level 2 |
| `run_master.py --matrix` | every pair of the two listings once, then consolidation and `--gate` | up to 174 × `REPEATS` |
| `run_turbo_model_01.bat` | `--matrix --workers 1 --config .llm_config.model_01`, then rebuilds | 174 runs on level 1 |
| `run_selected_model_04.bat` | the chapter 16 validity gate on `00_fail`, level 4, then rebuilds | 3 pairs × `REPEATS` |
| `run_screen_model_03.bat` | `--matrix --config .llm_config.model_03 --projects 04_python_xlarge --workers 3 --skip-existing` | 29 runs on level 3 |
| `run_all_model_03.bat` | `--matrix --config .llm_config.model_03 --workers 1` | 174 × `REPEATS` on level 3 |
| `run_all_model_04.bat` | `--matrix --config .llm_config.model_04 --workers 1` | 174 × `REPEATS` on level 4 |
| `rebuild_results_table.bat` | consolidation, then `--gate`: the chapter 16 conditions per campaign as PASS or FAIL; no runs. Pauses at the end, so double-clicking it shows the result | free |

### Further details

`--matrix` is the matrix, and the two sweep files are one line each calling it — a batch loop cannot
skip what has already run, cannot run two pairs at once and cannot say at the end how many rows it
produced. Its flags, each optional:

- `--config <path>` — the campaign constants file, as everywhere else; its base name is the
  `cfg_campaign` the matrix filters and reports on. It is read once in the parent for the keys that
  are wrong for every pair alike, so a broken config aborts once instead of 174 times.
- `--workers N` — how many pairs run at once, each an independent `run_master.py P M` subprocess.
  Default 1, which is the sequential order the `for /d` loops had. Workers start two seconds apart
  and the queue gives the next pair to whichever worker is free.
- `--skip-existing` — drop every pair that already has a row with this `prj_name`, `mth_name` and
  `cfg_campaign`, read from `local\runs\*\results_run.csv`. This is how an interrupted sweep resumes.
- `--projects a,b` and `--methodologies x,y` — restrict either listing to the names given; an
  unknown name is a usage error rather than a silently empty matrix.

Each pair runs **once**; `REPEATS` applies inside it, exactly as under `run.bat`. The two directory
listings are the matrix rather than a hard-coded list, so a new project or methodology joins by
existing — 44 × 6 = 264 pairs today, and nothing changed when ten arms were added; a directory whose
name starts with `_` is not an arm and is skipped. Stdout and stderr of every run go to one
`local\runs\_matrix_<campaign>_<timestamp>.log`, each line prefixed by its pair, and the summary at the
end is pairs run, rows produced and aborts. The turbo rows are real rows in the repository and are
excluded from the campaign pivot by `cfg_effort` (chapter 17): the sweep answers "does every pair
still run", not "which methodology is better".

`--matrix` exits 0 when every pair produced at least one row and 1 when one did not; the gate's own
verdict is printed but does not decide it, because a matrix answers "did every pair run" and chapter
16 answers "is the apparatus sound". `--gate` exits 0 when every campaign holds all three conditions
and 1 when one does not. Either takes exit 2 on a malformed flag.

1. Read the constants from `.llm_config.model_02`, or from the file `--config` names; the entry filename is
   `CLAUDE.md`. A second engine is a separate branch (chapter 18). Then, once for the whole
   invocation and before repeat 1, the checks that cannot come right on a later repeat: the config
   keys including `MODEL` and the fallback model (exit 4), every flag of the launch line against
   `claude --help` and `REVIEW_CMD` where it applies (exit 6), and the ancestor entry files
   (exit 5). Their records are `local/runs/_cli_help.txt` and `local/runs/_preflight_ancestors.txt`; each run
   keeps its own copy as well.
2. For each repeat `1..REPEATS`: build run id `run_<methodology>_<project>_<timestamp>_r<NN>` and
   create the run directory. **An abort after the run directory exists ends that repeat, not the
   invocation**: the exit code and the message are written to `abort.txt` in the run directory and
   to `_master.log`, and the next repeat starts. `REPEATS=3` with one broken venv therefore yields
   two rows and one recorded abort rather than one row and silence; the process exits with the
   highest abort code seen, or 0 when every repeat produced a row. The directory is created with
   `exist_ok=False`: the timestamp has one-second resolution, so two `--matrix` workers starting
   the same pair in the same second would otherwise share one directory and overwrite each other's
   `result.json` and row. On a collision the id is rebuilt from a fresh timestamp a second later,
   bounded at ten tries, and `id_timestamp` is the rebuilt one, so it still names the directory the
   run is in.
3. Copy `methodology/<M>/` minus `notes.md` into `local/runs/<id>/methodology/` — the snapshot that makes
   the run reproducible, and the only directory the agent is given beyond the project_workspace.
4. Copy `projects/<P>/project_reset_template/` into `local/runs/<id>/project_workspace/` — this copy *is* the
   reset; the source project is never modified.
5. Render `{{key=value}}` placeholders, deploy the entry file into the project_workspace as `CLAUDE.md` and
   record its byte count as `mth_chars`. **The source is the run's own snapshot from step 3**,
   `local/runs/<id>/methodology/copy_to_root/agents_or_claude.md`, never `methodology/<M>/`:
   deploying from the source directory meant an edit landing between the two steps gave the agent a
   file the snapshot does not contain, and the run directory then recorded something other than
   what ran. `00_empty` deploys nothing, `mth_chars=0`; the master
   tolerates an empty `copy_to_root`. A key occurring twice in one entry file aborts here, with
   exit 4 — before pre-flight, because the deployed file is already wrong and no environment work
   can make it right.
6. Pre-flight, in order: validate the config keys carrying a type, a range or a path —
   `REVIEW_FEEDBACK` is `0|1` and requires `REVIEW_PASS≠none`, `BEST_OF_N` and `REVIEW_WEIGHT` are
   integers ≥ 1, `FIX_MODEL` where set is a canonical id, `REVIEW_PROMPT` names a file that exists —
   aborting with exit 4 and the key's name;
   resolve `claude` on `PATH` and validate every flag of the launch line
   against `claude --help`, saving the help text as `cli_help.txt` and aborting with exit 6 if the
   CLI is absent or a flag is missing — `--disallowedTools` joins that list only when
   `REVIEW_PASS=same_model`, since a CLI that cannot run the review is no reason to fail a run that
   does not review; on `REVIEW_PASS=other_model`, abort with exit 6 if `REVIEW_CMD` is blank or its
   executable is not on `PATH`; walk from the run directory up to the drive root and abort
   with exit 5 if any `CLAUDE.md` or `AGENTS.md` is
   found, naming the paths in `preflight_ancestors.txt`; build the environment from the project's
   `.environment` and `.requirements` (chapter 10); copy `projects\<P>\holdout_tests\*.py` into
   `local\runs\<id>\holdout\` if that directory exists; run the verification against the pristine
   project_workspace, with the holdout directory as its fourth argument and the template as its
   fifth (chapter 11); **then delete `local\runs\<id>\holdout\` again**, so it does not exist while
   the agent runs — it sits one directory above the workspace and `../holdout/` is readable by any
   python the agent starts (chapter 11). Step 8 re-creates it. A pre-flight verification that hits
   the timeout aborts the repeat with exit 4 rather than reading as the expected failing baseline.
   Pre-flight
   also tests `%USERPROFILE%\.claude\CLAUDE.md` and records
   `cfg_user_claude_md=present|absent` as a label.
7. Launch the CLI with cwd = `project_workspace/`. The subprocess environment prepends
   `local\runs\<id>\.venv\Scripts` to `PATH`, sets `VIRTUAL_ENV` and removes `PYTHONHOME`, so `python`
   and `pytest` resolve to the project environment and an inherited `PYTHONHOME` cannot point the
   venv interpreter at another installation's standard library. `PYTHONUTF8=1` and
   `PYTHONIOENCODING=utf-8` are set on every subprocess the harness starts, not only the CLI —
   venv build, pip, both oracle runs — because a Windows cp1252 pipe corrupts any of them. The
   prompt is piped on stdin and the exact argv is written to `cli_argv.txt`:
   `type projects\<P>\prompt.md | claude -p --model %MODEL% --effort %EFFORT%
   --max-budget-usd %MAX_BUDGET_USD% --output-format json --permission-mode acceptEdits
   --allowedTools "<the arm's tool list>"
   --strict-mcp-config --mcp-config local\runs\<id>\mcp_empty.json
   --no-session-persistence --setting-sources project --add-dir local\runs\<id>\methodology`
   Print mode with `--permission-mode acceptEdits` denies any tool that would prompt, Bash included,
   so the tool list is explicit; `PowerShell` is the shell tool on Windows and `Bash(...)` rules do
   not cover it (chapter 14). The list is
   `Read,Edit,Write,Glob,Grep,Agent,Bash(python:*),Bash(pytest:*),PowerShell(python:*),PowerShell(pytest:*)`
   unless the arm ships `methodology/<M>/tools.txt`, one tool per line in the same syntax, which
   replaces it whole and is recorded as `cfg_tools` (chapter 15). `Agent` is the reviewer subagent the R methodologies hand off to and is listed
   for every methodology, including those that never use it: a tool set that varied by methodology without being recorded would be a second
   treatment. `pip` is deliberately not allowed: dependencies come from `.requirements`
   (chapter 10). `--strict-mcp-config` with an empty `mcpServers` file keeps the
   user's globally configured MCP servers out of every run's system prompt, where they would change
   the token floor and the tool set as an invisible constant; the value must be a path, since a
   literal `"{}"` is rejected against the schema. `--setting-sources project` drops user and local
   settings. `--add-dir` is narrowed to the methodology snapshot, which is what the entry file's
   imports reach. There is no `--max-turns`: the flag does not exist in this CLI and unknown
   options are accepted silently, which is what the flag validation in step 6 exists to catch.
   Stdout goes to `result.json`, stderr to `stderr.txt`; a run past one hour of wall-clock is killed
   and recorded as `res_subtype=harness_timeout`.

   7a. **Best of N**, when `BEST_OF_N` is above 1. Step 7 runs `N` times instead of once, into
   `project_workspace_1..N`, each a fresh copy of the reset template with the entry file deployed
   and each launched on the same line. They run sequentially: parallel invocations would share a
   machine, a rate limit and one wall-clock, and `prf_duration_s` would stop meaning anything.
   Each candidate is then scored on a throwaway copy of itself, `bestof_<n>/scored_workspace/`,
   where the tamper set is restored and the project's own oracle runs, writing into
   `local/runs/<id>/bestof_<n>/` — without the held-out suite, which would otherwise be on disk
   beside the next candidate's workspace while its agent runs (chapter 11); selection is on the
   visible `res_score` alone and the winner's held-out fraction is measured in step 8. The candidate workspace itself is never restored: the winner must reach
   step 7b and step 8 exactly as its agent left it, or a weakened test would be missing from the
   reviewer's diff and `res_tests_tampered` would read false on a row that tampered.
   The highest `res_score` wins, a tie going to the cheaper run;
   the winner is copied to `project_workspace/` and its output becomes `result.json`, so everything
   downstream — review, feedback, tamper, oracle, row — sees one run. `res_bestof_n`,
   `res_bestof_min` and `res_bestof_max` record the shape of the sample, the row's `tk_*` are the
   chosen run's, and the losers' spend is summed into `tk_bestof_cost_usd`: it was really spent,
   and it is not what the chosen run cost.

   7b. **The review pass**, when `REVIEW_PASS` is not `none`. It runs here — after the agent exits,
   before the tamper set is restored and before the oracle runs — for two reasons: the diff it reads
   must be the one the agent left, not the one the restore produces, and it must not be able to see
   the oracle's verdict on the code it is judging. Its whole input is one stdin stream of three
   parts separated by a rule: the file `REVIEW_PROMPT` names, the project's `prompt.md`, and the unified
   diff of the project_workspace against `project_reset_template` over `.py` files only. **The pass
   is blind by construction.** The implementer's `result.json`, `run.log` and reasoning never reach
   it, and neither do the Markdown artifacts a methodology tells the agent to write — `PLAN.md`,
   `DECISIONS.md` and `SUMMARY.md` are the implementer's plan and reasoning in another file, so they
   fall outside the glob by the same rule; the deployed `CLAUDE.md` and the held-out suite are out
   for the same reason and because the suite never enters the project_workspace at all. The stream
   is kept as `review_input.txt`, which is the record that the pass was blind.

   **The reviewer has no tools and an empty working directory; stdin is its only input.** Blindness
   is a property of the launch line, not an instruction the reviewer is trusted to follow: a
   reviewer sitting in the project_workspace with a file-reading tool need only open `CLAUDE.md` or
   `PLAN.md` to read the methodology and the plan the diff was meant to hide, and an `other_model`
   reviewer there is an external process with write access to the workspace about to be scored.
   Both invocations therefore run with cwd = `local/runs/<id>/review_cwd/`, a directory created empty for
   the call, so whatever the reviewer writes lands where it is evidence rather than where it would
   be scored. `same_model` launches the CLI there under the step-7 environment with
   `-p --model <REVIEW_MODEL or MODEL> --effort %EFFORT% --max-budget-usd %REVIEW_MAX_BUDGET_USD%
   --output-format json --permission-mode acceptEdits
   --disallowedTools "Read,Edit,Write,Glob,Grep,Bash,PowerShell,Agent,WebFetch,WebSearch"
   --strict-mcp-config --mcp-config local\runs\<id>\mcp_empty.json --no-session-persistence
   --setting-sources project`, writing `review.json` raw and the `result` text as `review.md`. There
   is no `--allowedTools` and no `--add-dir`: an empty allow-list is not how this CLI is told "no
   tools", so the denial is written out by name, in full — an option this CLI does not offer is
   accepted silently, and a shorter list would look identical. `other_model` runs `REVIEW_CMD` in
   the same directory on the same stdin, takes its stdout as `review.md` and records the exit code
   in `run.log`. `res_review_findings` counts the lines
   opening with a Conventional Comments label, `res_review_issues` the `issue:` lines alone, and
   `res_review_actionable` the `issue:` lines that also carry a `changes=` field naming an edit
   (chapter 13). **An invocation that exits non-zero having printed nothing did not review**: it is
   recorded as `res_review_error=1`, the three counts stay blank rather than reading as a clean
   review that found nothing, step 7c is skipped so `res_review_fixed` stays blank too, and
   `run.log` says why. With
   `REVIEW_FEEDBACK=0` the review gates nothing and blocks nothing — it is measured, not obeyed. Tokens and cost land in
   `tk_review_*` and are blank on `other_model`, whose usage fields are not comparable with this
   CLI's.

   **Weight.** `REVIEW_WEIGHT=n` above 1 makes step 7b `n` invocations instead of one, of the same
   prompt on the same diff, each with cwd = `local/runs/<id>/review_cwd_<k>/` and its raw output in
   `review_<k>.json`. They are independent by construction — same input, separate contexts, no
   reviewer sees another's answer — and their texts are concatenated into one `review.md` with a
   `# reviewer k` header per block, which carries no label and is therefore counted by nothing. The
   three `res_review_*` counts are taken over the whole file and the `tk_review_*` counters are
   summed; `prf_review_s` is the pass's total wall-clock. At `n=1` nothing is suffixed and
   `review.md` is the reviewer's answer verbatim, as before the key existed.

   7c. **Feedback**, when `REVIEW_FEEDBACK=1` and `review.md` carries at least one `issue:` line.
   The harness runs one further implementer invocation: the same launch line as step 7 — same
   tools, same budget key, cwd = `project_workspace/` — except for `--model`, which carries
   `FIX_MODEL` when that key is set and `MODEL` when it is not (chapter 9), recorded as
   `cfg_fix_model`. Its stdin is three parts separated
   by the same rule: the project's `prompt.md`, the `issue:` lines of `review.md` verbatim, and the
   fixed instruction in `lib/feedback_prompt.md` ("Fix the listed issues in the existing code. Do
   not add features, files or tests. Stop when they are fixed."). The stream is kept as
   `fix_input.txt`, the argv as `fix_argv.txt` — its own file, because under `FIX_MODEL` the two
   launch lines differ and one overwriting the other would leave the run directory unable to say
   which model wrote what — and the result as `fix.json`. The oracle then runs as usual, so the row
   scores
   the fixed code. `res_review_fixed` is 1 when the call ran, 0 when the review found no `issue:`,
   and blank when the feature is off. The fix call's counters are `tk_fix_*` and `prf_fix_s`;
   `tk_cost_usd` stays the first implementer call's (chapter 17) and the fix call's permission
   denials are not added to `res_permission_denials`, which is read from `result.json` alone.
8. After the agent exits: compare the tamper set against the template and record
   `res_tests_tampered`, restore it, re-create `local/runs/<id>/holdout/` from
   `projects/<P>/holdout_tests/` — which pre-flight deleted before the launch (step 6) — then run
   `projects/<P>/run_verification.py` against the
   project_workspace with that directory as its fourth argument and `project_reset_template` as
   its fifth (chapter 11). The held-out suite is
   copied into the run directory, never into the project_workspace. The oracle deletes any pytest
   configuration or hook file the template does not ship and reports it as `config_tampered=1`,
   which is `res_tests_tampered=true` here as well: the restore above only puts template files
   back, so an *added* `pytest.ini` or `conftest.py` is invisible to it (chapter 11). A budget or
   turn stop is a normal row; verification still runs.
9. Parse `result.json`, `verification_baseline.txt` and `verification.txt`; print the row and write
   `results_run.csv` into the run directory.

`--setting-sources project` suppresses the user-level `CLAUDE.md`, verified by probe (chapter 14).
It does not suppress an entry file in an ancestor directory of the run root — the CLI walks up from
cwd and loads it — which is why that case aborts rather than being recorded. The repository lives at
`D:\OpenAgentsGym` for that reason: `D:\a_ClaudeCowork\CLAUDE.md` would otherwise enter every run.

| Exit | Meaning | When |
|---|---|---|
| 0 | every repeat produced a row | — |
| 2 | usage error: fewer than two arguments, in `run.bat` or in `run_master.py` | before repeat 1 |
| 3 | the interpreter named in `.environment` is not available; the repeat is skipped | in a repeat |
| 4 | abort: config (a malformed line, an empty key), a `MODEL` alias, a `REVIEW_MODEL` alias on `same_model`, or a fallback model, `REVIEW_PASS` not one of the three values, or a config key failing its type, range or path check (`EFFORT`, `MAX_BUDGET_USD`, `MAX_TURNS`, `REPEATS`, `REVIEW_FEEDBACK`, `BEST_OF_N`, `REVIEW_WEIGHT`, `REVIEW_PROMPT`) — the message names the key | before repeat 1 |
| 4 | abort: venv build, pip, baseline passes, oracle exit 2, duplicate parameter key | in a repeat |
| 5 | `CLAUDE.md` or `AGENTS.md` in an ancestor directory | before repeat 1 |
| 6 | CLI not on `PATH`, or on Windows only as a `.cmd`/`.bat` shim with no `.exe` beside it, a flag the harness passes is not offered by `claude --help`, or `REVIEW_PASS=other_model` with `REVIEW_CMD` blank or not on `PATH` | before repeat 1 |

The third column is the difference the repeat loop makes. A fault that is certain to recur is
settled before the first repeat and ends the invocation; a fault that belongs to one repeat leaves
`abort.txt` there and the loop goes on, and the process exit code is the highest abort code seen.

3 and 4 are deliberately separated. A missing interpreter is a property of the machine and the run
is skipped; a venv or pip that fails afterwards is a broken machine and the message names the step
and points at `venv.log` or `pip.log`. Recording the second as a skip would hide it.

`rebuild_results_table.bat` (a wrapper over `run_master.py --consolidate`, followed by
`run_master.py --gate`) merges `local\runs\*\results_run.csv` into
`results_repository.csv` on demand and then prints the chapter 16 conditions over it.
**The published table is an input as well as the output.** `local\runs\` is git-ignored, so a fresh
checkout holds none of the runs behind the published rows, and rebuilding from the run directories
alone emptied the table on the first consolidation after a clone. Every row already in
`results_repository.csv` whose `id_run` has no local `results_run.csv` is therefore kept exactly as
it stands, a local run overwrites the row of its own id, and the counts are printed as *kept from
the published table* and *from local/runs*. `local\runs_archive\` is still not read, and a mixed
campaign is named here as `--gate` names it (chapter 17).
Consolidation also names the repeats that aborted and produced no row (`abort.txt`, chapter 12),
so a campaign short of rows says so instead of looking complete. `results_repository.csv` is never
written while runs execute. What
parallel workers do share is three files, and each is written in the one way that cannot tear:
`local\runs\_master.log` is appended to a line at a time and never opened for writing, and the two
invocation-level records `local\runs\_cli_help.txt` and `local\runs\_preflight_ancestors.txt` are written to a
private temporary and renamed into place. Everything else a run writes is inside its own run
directory. Rows are merged by column name rather than by position, and a column a run predates is left blank, so adding a metric never orphans the runs already on disk. The header written is the full column list of chapter 13 whatever the rows hold — a column no run has produced yet is a blank cell in every row, not an absent column, so the published file always matches the schema — followed by any column a row carries that the list does not.

## 13. Results

Every column carries a two- or three-letter semantic prefix, so the clusters read as blocks:
`id_` identity, `prj_` project, `mth_` methodology, `cfg_` configuration, `res_` outcome, `tk_`
cost, `prf_` performance. This is the literal CSV header, 85 columns, in this order:

```
id_run, id_timestamp, id_repeat
prj_name
mth_name, mth_version, mth_chars, mth_param_definition_of_done, mth_param_constraint_order,
mth_param_doc_types, mth_param_review_rounds, mth_param_gate_style, mth_param_phase_budget,
mth_param_retry_policy
cfg_campaign, cfg_engine, cfg_cli_version, cfg_model, cfg_effort, cfg_user_claude_md,
cfg_review_pass, cfg_review_model, cfg_fix_model, cfg_review_prompt, cfg_review_weight, cfg_tools
res_score_baseline, res_score, res_score_holdout, res_bestof_n, res_bestof_min, res_bestof_max,
res_verification_passed,
res_verification_error, res_verification_exit, res_review_findings, res_review_issues,
res_review_actionable, res_review_fixed, res_review_error,
res_tests_tampered, res_files_added, res_files_added_src, res_diff_lines, res_lines_added,
res_lines_removed, res_artifacts, res_subtype, res_hit_turn_cap, res_subagents_spawned,
res_permission_denials,
res_model_served, res_sloc, res_sloc_baseline, res_sloc_delta, res_chars, res_complexity, res_mi,
res_parsimony_factor,
res_max_func_sloc, res_max_nesting, res_lint_errors, res_docstring_cov, res_comment_density
tk_input, tk_output, tk_thinking, tk_cache_write, tk_cache_read, tk_cost_usd, tk_bestof_cost_usd,
tk_review_input, tk_review_output, tk_review_cache_write, tk_review_cache_read, tk_review_cost_usd,
tk_fix_input, tk_fix_output, tk_fix_cache_write, tk_fix_cache_read, tk_fix_cost_usd
prf_turns, prf_duration_s, prf_review_s, prf_fix_s
```

### 13.1 Logs

Three levels, all plain text:

- `local/runs/<id>/run.log` — everything the harness printed during that run, mirrored from the console.
  The console is the live view; this file is the record that survives a closed window and is what
  makes a crashed or aborted run diagnosable afterwards.
- `local/runs/_master.log` — one line per run at campaign level: `START` with model and effort, then
  `DONE` with score, pass, cost, turns and duration, or `ERROR`/`ABORT` with the reason. This is the
  history of what was attempted, including the runs that produced no row at all.
- `local/runs/<id>/stderr.txt`, `venv.log`, `pip.log` — raw output from the CLI, the virtual environment
  build and the dependency install, kept separate so a failure can be attributed to the right step.

A run that aborts before `results_run.csv` exists still leaves `run.log`, an `abort.txt` carrying
the exit code and the message, and an `ABORT` line in `_master.log`; a missing row is therefore
always explainable, and the repeats after it still run (chapter 12).

### Further details

The seven parameter columns are always present and blank when the key is not in the entry file —
`mth_param_review_rounds` therefore carries a value on `09_foureyes` alone, and the three candidate
keys on `01_process` alone. Consolidation merges by column name and writes this header in full, so
a run that predates a column gets a blank cell for it and a column no run has produced yet is blank
in every row rather than absent from the file.

Source in `result.json`: `usage.input_tokens`, `usage.output_tokens`,
`usage.output_tokens_details.thinking_tokens`, `usage.cache_creation_input_tokens`,
`usage.cache_read_input_tokens`, `total_cost_usd`, `num_turns`, `duration_ms`, `subtype`,
`subagent_stats.spawned`, `permission_denials` and `modelUsage.<id>.canonicalModel`. `prf_duration_s` is
`duration_ms / 1000`, and the harness's own wall-clock when the JSON carries none.

Outcome columns come from the two `verification*.txt` files and the verification exit codes
(chapter 11). `res_verification_passed` is that post-run exit code being 0 — the oracle's verdict,
gate included — and `res_verification_exit` carries the code itself, so a 1 (task not done) and a 2
(environment broken) stay distinguishable in the table without opening the run directory.
Run-level constants (`MAX_TURNS`, `MAX_BUDGET_USD`) stay in the config file rather than on every row.

`res_files_added`, `res_files_added_src`, `res_lines_added`, `res_lines_removed` and
`res_diff_lines` are taken over the project_workspace against `project_reset_template` **less the
deployed entry file (`CLAUDE.md`/`AGENTS.md`) and the D documents `PLAN.md`, `DECISIONS.md` and
`SUMMARY.md`**, which the review diff excludes for its own reason (chapter 12, step 7b). Neither is
code the agent chose to add: the entry file is the harness's own deployment, and the three
documents are what the methodology demanded and what `res_artifacts` already records — counting
them made the restraint columns grow with `mth_chars`, reading 4 on every `02_doctypes` row of
campaign 1 for compliance rather than for sprawl.

`res_files_added_src` is the count of added files whose suffix is `.py`, a subset of
`res_files_added`. It stays because a Markdown file outside those three — a `NOTES.md`, a second
plan — is a real addition and still counts, so the total and the source count answer different
questions.

`res_artifacts` lists only artifacts the agent added: a name the project's own template ships is
filtered out, since crediting every arm with a file it was handed measures nothing. The ADR records
are filtered the same way and listed by path, so `docs/adr/0001-storage.md` appears as itself rather
than as one `adr` flag — the count of records is the adherence evidence, and a single flag would
hide it.

`res_score_holdout` is the held-out suite's own pass fraction, unscaled by parsimony and blank on a
project that ships none; `res_score` stays the visible result, so the gap between the two is read
directly off the row (chapter 11).

`res_sloc_baseline` is the pre-flight SLOC lifted out of `metrics_baseline.txt` and
`res_sloc_delta` is `res_sloc − res_sloc_baseline` — the code the run actually wrote, blank if
either side is missing.

The review columns are the review pass's whole output (chapter 12, step 7b). `cfg_review_pass` and
`cfg_review_model` carry the configuration, so a campaign that ran with the pass on is a filter
rather than a memory; `cfg_review_pass` therefore reads `none` on a run without one, where the
`res_`, `tk_review_*` and `prf_review_s` columns are blank and `cfg_review_model` with them.
`res_review_findings` counts the reviewer's Conventional Comments lines and `res_review_issues` the
`issue:` lines alone — the split matters because a reviewer that files twenty `nitpick:` lines and
no `issue:` has found nothing. A line counts with a leading markdown bullet (`- `, `* `, `1. `) and
in any case (`Issue:`), since a finding lost to formatting is a miscount rather than a stricter
measurement; a line carrying no label at all is not a finding. `tk_review_*` are the review invocation's own counters, never folded
into the implementer's, and blank on `other_model`; `prf_review_s` is its wall-clock, which is
already excluded from `prf_duration_s` because that is the implementer's `duration_ms`. Under
`REVIEW_WEIGHT>1` all three counts are taken over the concatenated `review.md` and the `tk_review_*`
counters are summed across the reviewers, so the columns describe the pass and not one member of it.

`res_review_actionable` is the subset of `res_review_issues` whose line also carries a `changes=`
field naming an edit. The field is the optional suffix `lib/reviewer_prompt.md` allows and the
schema `17_finding_schema` deploys asks for; it runs to the next `key=` field or to the end of the
line, so it reads the same whether a `confidence=` follows it or nothing does. An `issue:` with no
such field named no edit, and one with `changes=none` said in the schema's own words that there is
none — neither is actionable. The split is the point: a reviewer that files twenty issues nobody can
act on has produced a number, not a review, and `res_review_issues − res_review_actionable` is the
size of that gap. The column is read off the harness review pass's own output, so it is blank
wherever `cfg_review_pass` is `none`, exactly as the other two review counts are.

`cfg_review_prompt` is the file name of the reviewer prompt that ran, blank where there was no
review pass: two campaigns with the same `cfg_review_pass` and different prompt files are two
treatments, and the name is what separates them without opening a run directory.
`cfg_review_weight` is how many reviewers that pass ran, blank on the same rows and for the same
reason. It is a treatment like the prompt — three reviewers find more than one does — so rows whose
weight differs are not pooled (chapter 17).

`cfg_campaign` is the base name of the config file the run read — `.llm_config.model_02`,
`.llm_config.model_01` — set from the file that was actually used, never from a key inside it. Seven
`cfg_` columns now decide what may be pooled, and reconstructing that set row by row is how two
campaigns get mixed; one label is the first filter (chapter 17) and the unit `--gate` groups by.

`cfg_tools` is `default` on every arm that does not ship `tools.txt` and the comma-joined list on
one that does (chapter 15). Rows whose `cfg_tools` differ are not pooled (chapter 17).

`res_review_error` is 1 when an invocation of the review pass exited non-zero having printed
nothing, 0 when the pass ran, and blank where `cfg_review_pass` is `none`. A failed reviewer used to
be recorded as zero findings at zero cost — indistinguishable from a reviewer that read the diff and
had nothing to say — and the feedback step then read it as nothing to fix. On a 1 the three
`res_review_*` counts stay blank, since there is no measurement to report, and the fix call is
skipped so `res_review_fixed` stays blank as well. Rows with `res_review_error=1` are excluded from
any statement about the review pass; they are not excluded from the run's own score, which the
implementer earned before the reviewer failed.

`res_review_fixed` is 1 when the feedback call ran, 0 when the review pass ran and found no
`issue:` to act on, and blank when `REVIEW_FEEDBACK=0` or when the review pass errored. The states
are distinct: a blank says the treatment was off or produced nothing usable, a 0 says it was on and
the code gave it nothing to do. `tk_fix_*` and
`prf_fix_s` are that invocation's own counters, never folded into the implementer's.

`cfg_fix_model` is the model that invocation ran on (chapter 9, `FIX_MODEL`) and is blank wherever
`REVIEW_FEEDBACK=0`, since there is no fix call there to carry one. It sits beside
`cfg_review_model` because the two are the same kind of value and the loop has room for two tiers:
who reviews and who applies what the review found. On a run with the feedback loop on it names a
model whether the key was set or not — blank `FIX_MODEL` reads back as `MODEL`, so the column says
what ran rather than leaving the reader to look the default up.

`res_bestof_n`, `res_bestof_min` and `res_bestof_max` are the shape of the best-of-N sample: how
many candidates ran, and the lowest and the highest `res_score` among them. All three are blank at
`BEST_OF_N=1`. The row carries the chosen candidate's score and counters; `tk_bestof_cost_usd` is
what the candidates that lost cost, which is real spend no other column would show.

Token counters stay separate. A verbose methodology pays `tk_cache_write` once and `tk_cache_read`
on every turn at a fraction of the price; a summed figure mis-ranks the verbose methodologies.

`res_subagents_spawned` is objective adherence data: a methodology containing R either spawned a reviewer
or did not, independently of what the agent's answer claims.

`res_permission_denials` is the length of `permission_denials`: a compound shell command such as
`cd ...; python -m pytest` is not matched by a `PowerShell(python:*)` rule and is denied whole, so
the count separates a methodology that skipped its tests from a harness that blocked them.

`res_subtype` is the CLI's `subtype` recorded raw. `res_hit_turn_cap` is `num_turns >= MAX_TURNS`,
a threshold read from the config file and never passed to the CLI (chapter 9).

`cfg_cli_version` is `claude --version`, `cfg_model` the id requested in the config file, and
`res_model_served` the `modelUsage` entry with the highest `costUSD`, ties broken by `outputTokens`
— `modelUsage` always carries a
second `claude-haiku-4-5` housekeeping entry of about $0.001, so the first key is not the model that
did the work, and on a run cheap enough for two entries to report the same cost the one that wrote
more is the one that did it. A `res_model_served` ≠ `cfg_model` mismatch is a row to discard, not a
measurement.

`mth_version` is the first line of the entry file, an HTML comment
`<!-- mth_version: 08_process_doctypes_roles_guardrails.v1 -->`; blank for `00_empty`. The full
snapshot in the run directory
is the authoritative record of what ran.

## 14. Verified CLI

Established by direct query of the installed CLI and by the first runs, not assumed.

| Fact | Value |
|---|---|
| CLI | Claude Code 2.1.251 at `C:\Users\<you>\.local\bin\claude.exe` |
| git | 2.55 |
| Model alias `opus` resolves to | `claude-opus-5` (`modelUsage.canonicalModel`) |
| Effort | `--effort low\|medium\|high\|xhigh\|max`, settable per invocation |
| Cost cap | `--max-budget-usd <amount>`, print mode only |
| Tool restriction | `--tools`, `--allowedTools`, `--disallowedTools` |
| Role enforcement | `--agents <json>` |
| Hygiene | `--strict-mcp-config`, `--setting-sources`, `--safe-mode`, `--no-session-persistence` |
| Turn cap | no `--max-turns` in this CLI; it is an SDK option only |
| Unknown options | accepted silently — a bogus flag exits 0, so a dropped flag is an invisible no-op |
| `--mcp-config` | takes a path; a literal `"{}"` is rejected with `mcpServers: expected record` |
| Shell tool on Windows | `PowerShell`; `Bash(...)` rules do not cover it — observed as `permission_denials=[{tool_name: "PowerShell", command: "python -m pytest -q"}]` |
| `modelUsage` | carries a second `claude-haiku-4-5` housekeeping entry, ≈ $0.001 |
| Floor cost per run | 1-turn probe: 7,186 cache write / 15,440 cache read, $0.087. A real 7-turn run: 10,065 / 88,561, $0.171, 17 s |
| Python versions available | 3.10, 3.9, 3.6, 3.5, 2.7 (`py -0`); no 3.12 |
| User-level `CLAUDE.md` | present at `%USERPROFILE%\.claude\CLAUDE.md`; suppressed by `--setting-sources project` — verified by run: yes |
| Ancestor `CLAUDE.md` | loaded into every run; `--setting-sources project` does not stop it |
| Filesystem reach | `Bash(python:*)` is a python process: it reads any path on the disk, the tool list notwithstanding — an unsandboxed limitation, recorded below |

### Further details

**What the tool list does not bound.** `--allowedTools` decides which tools the CLI offers, not what
a process those tools start may open. `Bash(python:*)` and `PowerShell(python:*)` are on the list
because the agent must be able to run its own tests, and a python process can read
`projects/<P>/holdout_tests/` and `projects/<P>/reference/` by a relative path from the
project_workspace. The harness does not copy the held-out suite anywhere the agent could stumble
over it (chapter 11, chapter 12 step 6), which closes the accidental route; the deliberate one
stays open. It cannot be detected from here — the CLI reports tool calls, not the files a
subprocess opened — and closing it needs a sandbox or a filesystem ACL around the repository, which
this apparatus does not have. It is a known limitation, recorded and not solved: a run suspected of
it is discarded by hand, and a `res_score_holdout` that matches `res_score` exactly where the field
shows a gap is the sign to look for.

The evidence for these rows is in the run directories — `cli_help.txt`, `cli_argv.txt`,
`result.json`, `stderr.txt` — which are not versioned, so the table above is the record that
survives. A row is re-verified when `cfg_cli_version` changes: an upgraded CLI can rename a flag,
drop one, or start offering `--max-turns`, and unknown options are accepted silently.

`--fallback-model` must never be set. It silently substitutes a different model on overload, which
would corrupt a campaign without any visible error.

## 15. Invariants

- No `CLAUDE.md` or `AGENTS.md` in any ancestor directory of the repository — enforced by pre-flight
  (exit 5); the user-level file is suppressed by `--setting-sources project` (verified) and
  labelled `cfg_user_claude_md`.
- The held-out suite and the reference solution are not enforced as unreachable. They are kept out
  of the project_workspace and off the disk beside it while the agent runs, which is as far as an
  unsandboxed harness reaches; `Bash(python:*)` can still open them by path (chapter 14).
- The hygiene flags (`--strict-mcp-config --mcp-config <empty mcpServers file>
  --no-session-persistence --setting-sources project`) and the `--allowedTools` list
  (`Read,Edit,Write,Glob,Grep,Agent,Bash(python:*),Bash(pytest:*),PowerShell(python:*),PowerShell(pytest:*)`)
  are part of the launch line, not optional. The list is identical for every methodology **unless the arm
  ships `methodology/<M>/tools.txt`** — one entry per line, `Name` or `Name(pattern)`, a line of
  any other shape aborting with exit 4 — which replaces it whole; `cfg_tools` then records the
  deviation and chapter 17 treats the tool set as a separate axis, so rows with differing
  `cfg_tools` are never pooled. No arm ships one. `Agent` is on the default list
  unconditionally, so the R methodologies can spawn a reviewer without the tool set becoming a treatment.
  A tool tier is a treatment that is declared and recorded, never one that varies silently.
- Every flag on the launch line is validated against `claude --help` before the run; unknown options
  are accepted silently, so an unvalidated launch line cannot be trusted.
- The methodology snapshot is frozen per run. The source methodology directory may be edited
  freely; earlier runs stay reproducible.
- Harness files (`prompt.md`, `run_verification.py`) never enter the project_workspace, and `notes.md` is
  excluded from the methodology snapshot the agent can reach. The agent must not see its own check.
- Verification is executed by the master after the agent exits, never described in the prompt.
- Effort is set through `--effort`, never through prompt keywords — a keyword inside the
  methodology text would become part of the treatment being measured.
- Anchors (`00_*`) are never tuned.
- `MODEL` is a canonical id, never an alias; `--fallback-model` is never set.

## 16. Validity gate

Before any campaign result is interpreted, both anchors must behave. The gate is the 3 `00_fail`
runs and the `00_sabotage` rows of the campaign's ranking runs, judged against the incumbent:

- `00_sabotage` scores worse than the incumbent, `29_invariants_test_first_relative_stop`, on the
  same project with an oracle. The condition is evaluated **per project the campaign holds rows for**, and a project
  carrying one of the two anchors but not the other makes the campaign **INCOMPLETE**, printed as
  such and exit 1 — never PASS. Skipping such a project silently let a campaign missing half its
  gate report that the gate held. A project carrying neither anchor — the smoke run on
  `01_python_small` — is not a ranking project of that campaign and is not a gap.
- `00_fail` never reaches `res_verification_passed` under any methodology.
- The pristine baseline of an oracle project fails pre-flight. If it passes, the project cannot
  measure anything.
- The held-out suite passes on the project's reference solution and fails on the pristine template.
  A suite that fails the reference is testing something the prompt does not state;
  one that passes the template tests nothing. `05_python_refactor_large` inverts the second half as
  it inverts everything else: its template already holds the pinned behaviour, so both its suites
  are green at baseline and the strict-reduction gate is what fails.
- The ranking project's visible suite discriminates. A project is accepted for ranking only if its
  first three-repeat run shows a visible-fraction range of at least 0.15 across the twenty-nine arms.
  Where correctness is flat, the ranking is produced by the parsimony factor alone — a clamped
  one-decimal ratio — and the campaign ranks maintainability while reporting it as methodology.
  `03_python_large` fails this in campaign 1: 24/24 visible on all 23 runs, with the whole 0.80–0.91
  spread coming from the factor.

### Further details

**One label, one set of constants.** `cfg_campaign` is only the config file's base name, so two
different files of that name, or one file edited between two runs, share it. Before any condition
is read, `--gate` checks that the campaign's rows agree on `cfg_model`, `cfg_effort`,
`cfg_review_pass`, `cfg_review_model`, `cfg_fix_model`, `cfg_review_weight` and `cfg_tools` — the
columns chapter 17 forbids pooling across. A campaign whose rows do not is printed as **MIXED**
with the differing values and exits 1: a condition computed over two treatments wearing one name is
arithmetic, not a gate. `--consolidate` names the same campaigns as it writes the table.

`py -3 run_master.py --gate` prints the first three of these over `results_repository.csv`, one
block per `cfg_campaign`, each condition PASS, FAIL, INCOMPLETE or MIXED with the numbers behind
it. The closing line is the most severe word any campaign reached — MIXED before INCOMPLETE before
FAIL before PASS — and only PASS exits 0, so a campaign that is merely two campaigns under one
label is not reported as an unfinished one.
`rebuild_results_table.bat` runs it after every consolidation — the gate is worth nothing if it is
only checked when someone remembers to. The incumbent is `GATE_INCUMBENT_MTH` in `run_master.py`;
where a campaign has no rows of it the gate falls back to the previous incumbent,
`08_process_doctypes_roles_guardrails`, so campaigns that predate the change still have a
comparison, and a gate that silently found no incumbent rows would otherwise report the absence as
PASS.

`--gate --campaign <name> --apparatus-only` is the go/no-go for launching an expensive campaign
after a cheap one: it prints the same block for that campaign alone, drops the first condition —
which needs ranking rows the cheap sweep was never meant to buy — and adds the one the sweep exists
to answer, that no repeat aborted and no row carries a `res_subtype` other than `success`. An
aborted repeat writes no row and therefore carries no campaign, so that half of the count is over
`local\runs\` whole, which is the conservative reading and the right one here. Exit 0 or 1, as always.

If any of these does not hold, the finding is about the apparatus, not about methodology.

## 17. Campaign protocol

- `REPEATS=1` is a smoke-test setting only. Comparing methodologies requires `REPEATS≥3`; agent runs vary
  enough that a single observation per methodology cannot separate an effect from noise.
- Report the median across repeats, never the single best run.
- Report the spread beside the median on `prf_turns` and `tk_cost_usd` — min–max, or the
  interquartile range at `REPEATS ≥ 4`. Agent runs of the same cell differ by more than the gap
  between two arms, so a median without its spread is not a result
  ([SWE-Gym, Pan et al., ICML 2025](https://arxiv.org/abs/2412.21139)).
- An **empty patch** is a run with `res_files_added = 0` and `res_diff_lines = 0`: the agent
  finished without touching the code. It is derived from two existing columns and never a column of
  its own. Read it apart from a wrong edit — both leave `res_score` at its baseline value, and only
  the first says the methodology talked the agent out of starting.
- Score continuously where possible — fraction of tests passing, diff size, cost — rather than
  pass/fail. Binary outcomes need an order of magnitude more runs to reach the same confidence.
- Rank on `res_score` and report `res_score_holdout` beside it, never in its place: the held-out
  suite is the check on the ranking, not the ranking. A methodology that wins on `res_score` while
  its holdout column trails the field won by fitting to the visible tests, and that is a finding to
  state, not a number to fold in.
- Draw conclusions from the campaign's ranking project — `03_python_large` in campaign 1,
  `04_python_xlarge` in campaign 2; `02_python_medium`, `03_python_large` and
  `05_python_refactor_large` are secondary. `00_fail` is the gate and `01_python_small` is used for exactly one
  harness smoke run.
- **Campaign 2** holds `MODEL=claude-sonnet-5`, `EFFORT=medium`, `REPEATS=3`,
  `MAX_BUDGET_USD=4.00` and is **91 runs**: `04_python_xlarge` × 29 methodologies × 3 repeats = 87,
  the chapter-16 gate `00_fail` × {`00_empty`, `00_sabotage`,
  `08_process_doctypes_roles_guardrails`} × 1 = 3, and 1 smoke run on
  `01_python_small`. Optionally 87 continuity runs of `03_python_large` × 29 × 3 under the corrected
  held-out suite, which are a separate 87 and not part of the ranking. Estimated ≈$60.6 at
  level 2, ≈$124.2 at level 3, from a campaign-1 per-run mean of $0.348 on
  `03_python_large` doubled for project size.
- The cost axis is `tk_cost_usd`, the first implementer call's spend. `tk_review_cost_usd`,
  `tk_fix_cost_usd` and `tk_bestof_cost_usd` are reported beside it, never summed into it by default: the review pass is a treatment, so a campaign that runs it
  compares arms that all carry it, and adding a per-arm-constant second invoice to the axis only
  moves every row up by roughly the same amount. The same holds for the feedback call and the
  best-of-N losers: both are per-arm-constant second invoices. Sum them when the question is what a
  run costs end to end, and say which figure is being quoted.
- Pool only rows that share a `cfg_campaign`: it is the name of the constants file they were run
  on, so one label stands for the whole `cfg_` set and a pivot cannot silently mix two campaigns.
  Beyond it, rows whose `cfg_model`, `cfg_effort`, `cfg_cli_version`, `cfg_review_pass`,
  `cfg_review_prompt`, `cfg_review_weight` or `cfg_tools` differs from the
  campaign's constants, and rows whose `res_model_served` ≠ `cfg_model`, are excluded before the
  pivot — a config file edited between two runs keeps its name, so the label narrows the set and
  the seven columns confirm it. `--gate` and `--consolidate` check that much of it automatically and
  print a campaign whose rows disagree as MIXED (chapter 16); the remaining columns are the
  reader's. The tool set is an axis like the model: rows with differing `cfg_tools` are not pooled. The repository
  holds every run ever made, including the `run_turbo_model_01.bat` sweep at `cfg_effort=low` and any row
  from an earlier CLI; a campaign is the subset that shares its constants, and the constants are on
  every row so that subset is a filter rather than a memory.
- Reading a losing cell is a separate act from ranking, and `lib/failure_taxonomy.md` is the
  vocabulary for it: the fourteen MAST failure modes, each with the sign it leaves in a run
  directory, so a cell that lost is described by a named mode and the file the sign was read from
  rather than by a guess.
- Analysis is a manual pivot on `results_repository.csv`; no analysis script exists. `--gate` is
  not one: it re-states the chapter 16 conditions as PASS or FAIL and ranks nothing.

## 18. Open

- **GPT branch.** A second engine needs its own launch command, flags and usage field names, and
  its token counters will not be comparable across vendors — cost and wall-clock are the only
  cross-vendor axes. Every coupling to this engine sits in `run_master.py`, and nowhere else in the
  repository — the methodologies, the projects, `lib/oracle.py` and the batch files carry none:
  the `ENGINE` check; `shutil.which("claude")`; the entry-file target `CLAUDE.md`; the launch line
  and its flags; the `{"mcpServers": {}}` config the CLI's schema requires; flag validation against
  `claude --help` and the version from `claude --version`; `CLAUDE_CONFIG_DIR` and
  `CLAUDE_FALLBACK_MODEL`; the `claude-` prefix the model-id check enforces; the `DEFAULT_TOOLS`
  names and the `Tool(pattern)` grammar `tools.txt` inherits; and the `result.json` field names read
  in step 9. `cfg_user_claude_md` is named after this engine too and would be renamed with it.
- **`other_model` review pricing and cap.** The `other_model` branch runs and records
  `review.md`, but two things about it stay open. Its cost is not recorded: a foreign CLI reports
  usage in its own field names and its own units, so `tk_review_*` are blank there and the only
  cross-vendor figure would be wall-clock — the same limit the GPT branch has, in a smaller place.
  And `REVIEW_MAX_BUDGET_USD` does not bind it: the cap is a flag on this CLI's launch line and has
  no portable equivalent, so an `other_model` reviewer is bounded by the harness timeout alone.
  Both are settled once, together with a second engine, or not at all.
- **Enforced variants.** The CLI can *enforce* through `--tools` and `--agents` what a methodology
  can only request; running a parameter both ways measures the compliance gap. Two halves of this
  are now built — `REVIEW_FEEDBACK` against `09_foureyes` (chapter 19.2) and `tools.txt` against a
  methodology's tool policy (chapter 15) — and `--agents` role enforcement stays deferred until an
  effect exists to explain.

## 19. Methodology content requirements

What a methodology must contain to be worth deploying, and how each requirement is observed.

### 19.1 Complexity is recorded, not asserted

A methodology may claim restraint; the numbers decide. Every run records `res_files_added` and
`res_diff_lines` against `project_reset_template`, and, where the project measures it,
`res_sloc` and `res_complexity` (cyclomatic, standard decision-point count). The corresponding
instruction is one line: *prefer the smallest change that satisfies the stated requirement; adding
a file, an abstraction or a dependency requires one line of justification first*.

### 19.2 Four eyes

Self-review inside one session shares the context and the blind spots that produced the code, so it
is close to worthless. `09_foureyes` is the built answer and it is the **in-session subagent
variant**: the implementer hands the task text and the diff — nothing else — to a subagent with a
fresh context, and every `issue:` it reports blocks. Its adherence evidence is
`res_subagents_spawned` and the presence of `REVIEW.md`.

The stronger form, a **separate invocation** over the diff with a review-only prompt and no memory
of the implementation, is built and lives in the harness, not in a methodology: `REVIEW_PASS`
(chapter 9) and step 7b (chapter 12), recorded as `res_review_findings`, `res_review_issues`,
`res_review_actionable` and `tk_review_*`. `REVIEW_WEIGHT` is how many such reviewers one pass
runs: one reviewer's silence is not evidence, and `n` of them on the same diff separate a sound
diff from a quiet reviewer at a cost the row records.

`17_finding_schema` is the methodology-side counterpart of the actionable count. It asks the
in-session reviewer for the same five fields the harness pass's optional `changes=` suffix carries,
and its claim is that a review output shaped as a schema produces fewer findings that name nothing
to do. The harness measures that claim on its own reviewer, where every arm gets the same one; the
arm measures whether a methodology can get an agent to produce it.

`REVIEW_FEEDBACK=1` is the **enforced variant** of `09_foureyes`: the same blind review, but the
harness makes the fix happen instead of asking the methodology to. The findings block by
construction — the implementer is invoked again on them and the oracle scores what comes back —
where `09_foureyes` can only instruct an agent to block on its own subagent's findings, and
`res_subagents_spawned` measures whether it complied. Running both is the compliance gap of
chapter 18 with a number on it. `REVIEW_PASS=other_model` with `REVIEW_FEEDBACK=1` is the
cross-provider four-eyes arm: one vendor writes, another finds, the first fixes.

The reviewer's own prompt is a treatment too. `REVIEW_PROMPT` (chapter 9) selects it, and
`lib/reviewer_prompt_adversarial.md` is the harder setting — the same output contract with a
reviewer told to break the code and to raise `issue:` only where it can name a failing input. A
review pass that files no `issue:` measures the reviewer as much as the code, which is why the
prompt is recorded as `cfg_review_prompt` rather than assumed. The two are deliberately not the same thing. `09_foureyes` measures whether a
methodology can *get* an agent to review its own work — the review is inside the treatment, and
`res_subagents_spawned` is the adherence evidence. The harness pass takes the review out of the
treatment entirely: every arm gets the same reviewer on the same input, so the findings count is a
property of the code, not of the methodology's persuasiveness. That is also why it is not a `10_*`
methodology, why it blocks nothing, and why it is off by default — turning it on is a campaign-wide
decision, not a per-arm one.

### 19.3 Decisions

What the D feature actually ships is `doc_types.md`: three files in the project_workspace root, each
about fifteen lines at most, and no others.

- `PLAN.md` — written before the first code edit: what the task asks for, which files are to change,
  in what order.
- `DECISIONS.md` — written as decisions are made, one line each: the choice and what it rules out.
- `SUMMARY.md` — written last: what changed, what the tests said, what was left undone.

The file states the cap as a rule with a reason — a document past about fifteen lines costs more
than it carries, and is to be cut rather than continued in a second file.

`doc_types.md` also describes the two multi-session shapes, so a campaign can reach them without a
new file. **`doc_types=adr`** replaces `DECISIONS.md` with one record per decision under
`docs/adr/NNNN-title.md`, numbered from 0001, each carrying Context / Decision / Consequences —
Nygard's format, per 19.4, and `PLAN.md` and `SUMMARY.md` unchanged beside it. **`AGENT_BACKLOG.md`** is
the one further document the D feature may ship: one line per item the task named and the run
deliberately did not do, so the next session gets the list rather than the reasoning.

Both are described and neither is deployed: no arm renders `doc_types=adr` today, and a value the
catalogue offers is not a value an arm is on. What is built for them is the detection —
`res_artifacts` matches `docs/adr/*.md` as well as the six names, so the day an arm switches, the
adherence evidence is already being recorded (chapter 11).

Whether documents pay for themselves is what `doc_types` measures; they are not assumed to.

### 19.4 Change log and review, on accepted standards

No invented conventions:

- Commit messages: **Conventional Commits 1.0.0**. `git log` is then the change log; a separate
  `CHANGES.md` is redundant and is not required.
- Release notes, where a project wants them: **Keep a Changelog 1.1.0**, versions per **SemVer**.
- Decision records: **ADR**, Nygard format (see 19.3).
- Review remarks: **Conventional Comments** (`praise:`, `issue:`, `nitpick:`, `question:`), which
  makes `res_review_findings` countable by label rather than by guesswork.

### 19.5 Portability rules

Checked by the author when a methodology is edited, not at run time:

1. No vendor tool names. Capability words are allowed — `subagent` is used by the R and F arms
   — but they bind the arm to engines that have the capability, which is a portability limit of
   the arm, not of the text.
2. No CLI flags or harness paths.
3. No absolute paths; everything relative to the project_workspace root.
4. No framework vocabulary and no thinking keywords.

A methodology that passes these is portable text: the same file deploys unchanged under either
name. Today the harness always writes `CLAUDE.md`; nothing in the methodology changes when the
GPT branch adds the second name.

The same rule holds for the harness side, one step weaker: file names, batch files and these
documents name capability levels (chapter 9), never a vendor's model; the model id lives on the
`MODEL=` line of the config file and in the `cfg_model` column, nowhere else.

### 19.6 Execution tiers, steered by the project

Three levels, defined by the project because the project owns its runtime (chapter 10):

| Tier | Content | When |
|---|---|---|
| smoke | imports plus one trivial call; seconds | after each change |
| unit | the project's test suite | before claiming the task is done |
| full | unit plus held-out suite plus metrics | harness only, after the agent exits |

`prompt.md` states which tier the agent runs and when; the methodology does not. Keeping the tiers
in the project rather than in the methodology means the same methodology can be run against projects with very
different runtimes without editing the methodology — and it keeps that instruction out of the character
budget.

The harness always runs `full` itself, independently of anything the agent reports.
