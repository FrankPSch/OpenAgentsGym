# OpenAgentsGym — user manual

How to use the apparatus. **The specification (`oam_targetpicture.md`) defines behaviour; this
manual only explains use.** Where a rule matters it is named and its chapter is cited, never
restated.

Version of 8 September 2026, 11:09 UTC.

---

## 0. Contents

| # | Chapter | Answers |
|---|---|---|
| 1 | [Goal and overview](#1-goal-and-overview) | what is being measured, and what the four words mean |
| 2 | [Installation](#2-installation) | what must be on the machine before the first run |
| 3 | [Running](#3-running) | which entry point, which settings, what a reset is, how to clean up |
| 4 | [Extending a project](#4-extending-a-project) | how to add a task, and how to keep its scores comparable with the others |
| 5 | [Extending a methodology](#5-extending-a-methodology) | how to add a candidate without touching anything outside it |
| 6 | [Interpreting results](#6-interpreting-results) | which column says what, what may be pooled, what to look for |
| 7 | [Abbreviations](#7-abbreviations) | the short forms used here and in the table |

---

## 1. Goal and overview

The methodology under which an agent works — its process, roles, document types and guardrails — is
the largest uncontrolled variable in agentic software development, and it is normally argued about
rather than measured. OpenAgentsGym holds the model, the effort and the task constant and varies only
that text, so the difference between two ways of working shows up as numbers in one table
(chapters 1–3).

Four words carry the whole system:

| Term | Is |
|---|---|
| **methodology** | one candidate under test: a directory of plain Markdown under `methodology/`. Nothing but prose — no code, no framework. |
| **project** | one task an agent is asked to do: a directory under `projects/` with a prompt, a pristine template and its own oracle. |
| **run** | one methodology executed once against one project, in its own directory under `runs/`, ending in one CSV row. |
| **campaign** | a set of runs compared with each other, with model, effort and every other constant fixed across it. |

Coming from the general literature on agent evaluation, a *run* is a **trial**, the oracle is a
**grader**, and the CLI is the **agent harness**; chapter 2.1 of the specification lists the whole
translation. This manual uses the four words above and nothing else. One point from that section is
worth carrying here, because mistaking it is expensive: `REVIEW_PASS` (chapter 3) is part of the
**treatment**, a reviewer the arm works with — it grades nothing and never touches the score.

The methodologies form a **ladder** plus a set of **single-feature arms**:

```
00_*            the anchors                  no methodology at all, and a deliberately bad one:
                                             does methodology matter, and can the apparatus
                                             detect worse
the ladder      four features, singly        the low numbers are single features, the high ones
                and combined                 combinations; the last is the incumbent — the
                                             practical baseline every candidate is read against
above it        specific methodologies       one idea each, never combined into a grid: read
                or elements                  against the empty anchor for the effect, and
                                             against the incumbent for whether it beats it
```

Anchors (`00_*`) bound the measurement and are never tuned. The projects form the same kind of
ladder — `p00_fail` is impossible by construction, the rest grow in size (chapters 4, 5, 7).

Everything is a directory listing: a new methodology or project joins the matrix by existing.

## 2. Installation

Windows is the supported target; anything else is a smoke test of the harness, not a measurement
(chapter 10).

1. **Python** through the `py` launcher. `py -0` must list the version each project pins in its
   `.environment`. The harness itself runs on any Python ≥ 3.9 and uses the standard library only;
   each run builds its own virtual environment.
2. **Claude Code** on the `PATH` and logged in (`claude login` once, or an API key in the
   environment) — the harness never prompts. Every flag the harness passes is validated against
   `claude --help` before a run starts, because unknown flags are accepted silently (chapter 14).
3. **git**, and the repository under version control — that is the reset point for the repository
   itself.
4. **No `CLAUDE.md` or `AGENTS.md` in any parent folder** of the repository. The CLI walks upwards
   and would load it into every run; pre-flight aborts instead of measuring it (chapter 15). This is
   why the repository does not live under a folder that has one.
5. Optional, for the other-provider reviewer (`REVIEW_PASS=other_model`): a second command-line tool
   installed and logged in, its config directory pointed inside the repository, and `REVIEW_CMD` set
   to the command that reads a prompt on standard input. Still open.

Nothing else is installed globally. Project dependencies come from the project's `.requirements`.

## 3. Running

All entry points are batch files in the repository root; the exit code says what happened
(chapter 12).

| You want | Run |
|---|---|
| the quickest proof the whole chain works | `run_smoke_e02.bat` — double-click, no arguments; one pair on capability level 2 |
| one specific pair | `run.bat <project> <methodology>` |
| the same pair under different constants | `run.bat <project> <methodology> --config <path>` |
| every pair once, cheaply | `run_turbo_e01.bat` — every pair on level 1, the cheapest model |
| every methodology once on the xlarge project, level 3 | `run_screen_e03.bat` (the screen; edit `PROJECT` in the file) |
| every pair on level 3 or 4 | `run_all_e03.bat`, `run_all_e04.bat` |
| a hand-picked list, e.g. the validity gate | `run_selected_e04.bat` (edit the list in the file) |
| the results table and the gate, without running anything | `rebuild_results_table.bat` |

**Settings.** All campaign constants live in the four `.llm_config.e01_claude_haiku_4_5` … `e04_claude_fable_5_1` files and
nowhere else — model, effort, budget cap, repeats, and the review and best-of-N keys (chapter 9).
Each file is one capability level: 1 the cheapest model for the apparatus sweep
(`run_turbo_e01.bat`), 2 the workhorse for single pairs and the smoke test (`run.bat`,
`run_smoke_e02.bat`), 3 the frontier model at low effort for the full matrix (`run_all_e03.bat`), 4 the
model above the frontier tier for the full matrix and the gate (`run_all_e04.bat`,
`run_selected_e04.bat`). A batch file bound to a level carries it in its name. For a one-off, copy a file,
edit the copy, and pass it with `--config`; the file's base name becomes the campaign label on every row, so
two campaigns can never be pooled by accident.

**Resetting.** There is nothing to reset by hand. Every run copies the project's
`project_reset_template` into its own run directory and works there; the source project is never
touched (chapter 12).

**Clearing old runs.** Run directories accumulate — each carries a virtual environment. Move
`runs\run_*` you no longer need into `_to_delete\` and delete that folder; the rows they already
produced stay in `results_repository.csv`, which is what keeps the published table intact on a
fresh checkout (chapter 12). A row you want gone is deleted from that file.

**Consolidation.** `rebuild_results_table.bat` merges every `runs\*\results_run.csv` into
`results_repository.csv` and then prints the validity gate. Merging is by column name, so a run made
before a column existed simply gets a blank cell and nothing is orphaned. The published rows are
kept and a local run overwrites the row of its own id; the counts are printed (chapter 12). The
table is never written while runs execute. The same call writes `results_pareto.svg` beside the
table at the repository root — score against cost, one panel per campaign and project; open it in
a browser (chapter 13.2).

**Interrupted sweeps** resume with `--skip-existing`; `--workers N` runs pairs side by side.

## 4. Extending a project

A project is a directory under `projects/` holding a task, a pristine copy of the code, its own
oracle, a measured reference solution and — for a ranking project — a held-out suite (chapters 7,
8, 10, 11).

Working order:

1. **Write the task** (`prompt.md`) in the shared structure the existing projects use, and pin the
   runtime in the template's `.environment` and `.requirements`.
2. **Ship a visible test suite in the template that fails on the pristine code.** Pre-flight expects
   that failure; a template that already passes cannot measure anything and aborts the run
   (chapter 11). `p05_python_refactor_large` shows the inverted case, where the metric fails instead.
3. **Solve it yourself and keep the solution** under `reference/`. Run the oracle on it and store
   its output. The oracle constants — the size reference and the maintainability reference the
   parsimony factor divides by — are read off that measurement, never chosen. A constant that cannot
   be re-measured from an artefact on disk is a number the reader has to trust.
4. **Write the held-out suite** — roughly half the size of the visible one, same public contract,
   different inputs. It may test **only what `prompt.md` states**: testing unstated requirements
   penalises a methodology for not reading the author's mind. It must pass on the reference and fail
   on the pristine template, and a scope test must assert a positive behaviour beside the absence
   (chapters 11, 16).
5. **Calibrate the difficulty before spending a campaign on it.** Run the project once against
   `m00_empty` on capability level 1 — `run_turbo_e01.bat`, the cheapest model, cents. If the
   empty anchor already passes there, the task sits below the level you were aiming at and a
   level-3 campaign will hand back one score for every arm. Raise the difficulty, or file the
   project at the level where the anchor still fails. `p06_qc_ema_cross` was built without this step
   and cost four level-3 runs to learn the same thing.
6. **Check the gate conditions hold** for the new project before any result from it is read.

Two questions decide whether a task is worth a campaign, and both are cheaper to ask than to skip.
*Would two domain experts, reading `prompt.md` and the oracle alone, independently reach the same
pass/fail verdict?* If not, the task is under-specified and its scores are noise — fix the prompt,
not the oracle. *Is there something here an arm can plausibly get wrong?* A task whose specification
leaves no room to fail measures nothing, however strict the oracle is.

A project on which every methodology scores at the top ranks by cost alone. That is a statement
about the project, not about methodology — such a project is kept for smoke runs, not for ranking
(chapter 7).

### Keeping projects comparable

A score is not an absolute number. It is the visible pass fraction multiplied by the parsimony
factor, and that factor is the run's maintainability index divided by **this project's own**
reference. Two projects are therefore comparable only if both halves are produced the same way — so
a new project **copies** the machinery instead of writing its own.

| Copy from an existing project | Change only |
|---|---|
| `run_verification.py` — the oracle the harness calls, a thin wrapper over `lib/oracle.py` | the four constants at the top: the size and maintainability references, whether the project demands a strict size reduction, whether it ships tests (exception: an oracle-less project, below, may write a fully custom `run_verification.py` instead) |
| the section structure of `prompt.md` (task, specification, files, verification, work order), including which execution tier the agent runs and when (chapter 19.6) | the content |
| `.environment` and `.requirements` in the template | the pinned version and the packages |
| the layout `reference/` + `reference/metrics.txt`, and `holdout_tests/` | the solution and the tests |

**Never re-implement the metrics in a project.** Every project measuring itself with the same
`lib/oracle.py` is what makes the columns mean the same thing; an oracle that computes its own size
or complexity produces a column that silently is not the others'.

### Projects without a pytest oracle

Some tasks cannot be judged by running pytest against a local module at all — the correctness
check is a live external system (an API, a service, an account) rather than code sitting in the
workspace. `run_master.py` supports this directly: a project whose `project_reset_template/` ships
no `test_*.py` file is detected as **oracle-less** (`oracle_less = not list(template.glob("test_*.py"))`),
and pre-flight then only requires the baseline call to `run_verification.py` not to error out
(exit code 2) — it drops the "baseline must fail on the pristine template" requirement of chapter
11, since there is nothing to fail (`run_master.py`, step 6).

For such a project, `run_verification.py` need not be a thin `lib/oracle.py` wrapper — it may be a
fully custom script, provided it keeps the same contract every project's oracle keeps:

- called the same way: `<workspace> <run dir> [baseline|""] [holdout dir] [template dir]`
- writes `verification.txt` (and `metrics.txt`, if it scores quality) in the same `key=value` shape
- exit 0 = pass, 1 = fail, 2 = environment/setup error, with the same meaning as elsewhere

If the task still has code worth grading (a solution the agent produces or leaves behind
somewhere — locally or, as for `p06_qc_ema_cross`, in a live project the agent builds), score it
with `lib/oracle.py`'s own `code_metrics` / `parsimony_factor` against a measured `reference/`
solution exactly as any other project — never re-implement the metric just because the rest of the
oracle is custom. `p06_qc_ema_cross` is the example: it grades a QuantConnect backtest the agent
runs through the QuantConnect MCP tools rather than a local Python module, gates on the backtest
having actually run (compile succeeded, results exist), and scores the parsimony factor on the
algorithm's source fetched back live from the QuantConnect API.

**The two references are measured, not chosen.** Run the oracle on `reference/` and keep its output
as `reference/metrics.txt`; the size and maintainability constants are the `sloc` and `mi` lines of
that file. Keeping the file beside the solution is what lets any row be recomputed later.

The maintainability index falls with the logarithm of size, so a large project's reference is a much
smaller number than a small project's — and that is fine, because what enters the score is the
**ratio** to that project's own reference, not the index itself. This is also why every project must
carry one: a project without a reference scores on correctness alone and cannot be compared with the
rest. The factor's floor is the same everywhere, so parsimony can never outweigh correctness on any
project (chapter 11).

Two more things keep the scale the same: size the held-out suite at roughly half the visible one, so
the held-out column carries comparable weight everywhere; and check the project actually
discriminates before ranking on it — if the visible fraction barely moves across the arms, the
ranking is being produced by maintainability alone and must be reported as that (chapters 11, 16).

## 5. Extending a methodology

A methodology is a directory under `methodology/` containing one entry file and one side file per
feature. Copy the nearest existing arm and edit it.

- **Entry file** — `copy_to_root/agents_or_claude.md`, deployed into the workspace as `CLAUDE.md`
  (the `AGENTS.md` name waits on the GPT branch, chapter 18 of the specification). It opens with its version comment, then the constraints block carrying the
  rendered parameters, then the pointers to its side files, then the task hand-off. Keep it to about
  a kilobyte: the entry file is deployed on every run and its byte count is a recorded covariate.
- **Parameters** — `{{key=value}}` placeholders rendered on deploy and extracted as columns, so the
  configuration cannot drift out of sync with the prose the agent reads. The catalogue of keys is
  chapter 6; only one is varied at a time, the rest are held at a fixed value.
- **One side file per feature**, named after the feature, and **byte-identical** in every
  methodology that includes it. A diff between two arms' copies of the same file is a bug, not a
  variant.
- **`notes.md`** documents the arm for a human and is never deployed.
- **Portability rules** (chapter 19.5): no vendor tool names, no CLI flags or harness paths, no
  absolute paths, no framework vocabulary or thinking keywords. An arm that passes these deploys
  unchanged to any engine.
- **`tools.txt`** is the one declared deviation: an arm that ships it replaces the shared tool list
  whole, the deviation is recorded on the row, and its rows are then never pooled with the rest
  (chapter 15).

New arms outside the ladder are single features, read against `m00_empty` for the main effect and
against the incumbent for whether they beat it — never combined into a grid (chapter 4). Add nothing
outside the arm's own directory: the harness reads the listing.

## 6. Interpreting results

One row per run in `results_repository.csv`. The prefix says what a column is (chapter 13):

| Prefix | Holds |
|---|---|
| `id_`, `prj_`, `mth_` | which run, which project, which methodology and its parameters |
| `cfg_` | the campaign constants the row was produced under — the filter that decides what may be pooled |
| `res_` | what came out: scores, restraint, adherence, code metrics, review findings |
| `tk_` | tokens and cost, per invocation, never summed for you |
| `prf_` | turns and wall-clock |

**The three numbers that matter, and how they relate.** `res_score` is the visible suite's pass
fraction scaled by the parsimony factor; it is what arms are ranked on. `res_score_holdout` is a
second suite the agent never saw, unscaled — reported *beside* the ranking, never in place of it. An
arm that wins on the first while trailing on the second won by fitting to the visible tests, and
that is a finding to state. The maintainability index behind the parsimony factor is the tiebreaker,
not the discriminator: where correctness is flat it silently becomes the whole ranking, which is a
result about the project (chapters 11, 17).

**Before reading anything, read the gate.** `rebuild_results_table.bat` prints it: the sabotage arm
must lose, the impossible project must never pass, every pristine template must fail before the
agent starts. If a condition fails, the finding is about the apparatus and nothing else in the table
means anything yet (chapter 16).

**Pool only what belongs together.** Rows sharing a campaign label, and within it the same model,
effort, CLI version, review settings and tool set; rows whose served model differs from the
requested one are discarded. The repository deliberately holds every run ever made — the cheap sweep
included — so a campaign is a filter, not a memory (chapter 17).

**Repeats.** One run per cell is a smoke test. Comparison needs at least three, ranked on the
**median** with the **spread** reported beside it for turns and cost: two runs of the same cell
differ by more than the gap between two arms (chapter 17).

With more than one run per cell, report **pass^k** — the share of cells whose every run passed —
beside the median score. pass@1, the single-run number, says an arm *can* do the task; pass^k says
it does so every time, and that is what a methodology is supposed to buy. The two diverge exactly
where a methodology matters most.

**The rule for reading a ranking**, fixed before the rows are read so the rows cannot bend it:

1. Per arm, the median `res_score` over its repeats and the range (min–max).
2. Two arms are **different** only when their medians are more than 0.05 apart *and* their ranges
   do not overlap. 0.05 is the measured noise floor of one cell; anything inside it is a tie
   whatever the ordering says.
3. Ties are broken by cost (`tk_cost_usd` median), then by turns — never by the third decimal of
   the score.
4. A one-repeat screen — pass@1 — ranks by the same rule with the range collapsed to a point: it
   can separate an arm from `m00_empty` when the gap exceeds 0.05, it cannot separate two arms that
   close. A screen orders; repeats decide.
5. The rows read are one campaign label (chapter 17); a comparison across levels or configs is
   a comparison of models, not of methodologies, and is not made.

**Effort and quality, side by side.** `res_score` says whether a run worked. The score columns say
what it cost and what the code is worth, and they are read together:

| | `sc_effort` | `sc_quality` |
|---|---|---|
| built from | duration, turns, output tokens | maintainability, nesting depth, longest function |
| larger means | less spent | better code |
| money | not included — `sc_cost_usd` stands alone, and is blank wherever the engine reports no price | — |

There are two ways to combine them, and they answer different questions:

| | `sc_overall_mean` | `sc_overall_ratio` |
|---|---|---|
| formula | mean of `sc_effort` and `sc_quality` | `sc_quality / (1.25 − 0.5 × sc_effort)` |
| answers | how good was this run overall | did the effort pay for itself |
| range | 0.0–1.0 | 0.0–1.333 |
| neutral point | none | **1.0** — and at median effort it equals `sc_quality` |

Read `sc_overall_ratio` against `sc_quality`: above it, the effort was repaid; below it, it was not.
Effort can move a run by at most a third either way, so quality stays the dominant term. It is the
only `sc_` column that is not on 0.0–1.0 — do not read it as a normalised score.

Every score column places a run by how far it is behind **the leader of its own project**, measured
in logarithms and divided by the largest such distance anywhere in the table. So the best run of
each project scores 1.0, the worst run of the whole table scores 0.0, and nothing is clipped
(chapter 13.1b of the specification). They are blank on a run that did not pass: an effort number
without a correctness gate rewards giving up early.

Two things follow. A distance means the same in every project, so **all engines and all arms of one
project are directly comparable** — that is what these columns are for. But the *level* between
projects is gone: every project's best is 1.0, so they cannot say whether the best `p03` run beats
the best `p06` run. The measured columns answer that.

What the pair is for is the case the score cannot decide. On `p05_python_refactor_large` every arm
scores 1.0000, and the score columns still separate them, from
`m38_pipeline_source_with_reviewer_relative_stop` at 0.97587 down to `m46_gsd_surface_lean` at
0.37662 — the latter leading nothing and taking 1259 seconds to get there. One number would have
averaged that into silence.

**What to look for.**
- *Saturation* — every arm at the top of the score range. The project has stopped discriminating; it
  now ranks by cost, and it is reported as a cost comparison rather than as a quality ranking. The
  consolidation prints one descriptive line per project (arms, lowest and highest `res_score`,
  distinct values) so this is visible without a threshold anyone had to invent: `1 distinct value`
  across every arm is the whole finding. At level 3 this is the state of
  `p05_python_refactor_large`, `p06_qc_ema_cross` and `p07_qc_bugfix_refactor` — on 07 the sabotage arm
  even carries the highest maintainability index of the four. A saturated project is not broken; it
  is a smoke test, and a task belongs at the capability level where `m00_empty` still fails
  (`CONTRIBUTING.md`).
- *An empty patch* — no files added and no diff. The agent finished without touching the code, which
  is a different failure from a wrong edit even though both leave the score at baseline.
- *Restraint* — files and lines added, source lines written, complexity. A methodology may claim
  restraint; these columns decide (chapter 19.1).
- *Adherence* — the artifacts actually produced, subagents spawned, review findings. Objective
  evidence, independent of what the agent's answer claims.
- *A losing cell* — describe it with `lib/failure_taxonomy.md`, naming the mode and the file the sign
  was read from, rather than guessing.

**Cost.** Order of magnitude per run: cheapest arms around a tenth of a dollar, the review-heavy and
multi-invocation arms several times that. The cost axis is the implementer's own spend; a review
pass, a fix round and the best-of-N losers are separate invoices reported beside it and summed only
when the question is what a run costs end to end — and then said so (chapter 17).

Analysis is a manual pivot on the CSV. There is no analysis script, and the gate is not one.

## 7. Abbreviations

**Feature letters** (chapter 5) — P process, D document types, R roles, G guardrails; then one per
off-ladder arm: F four eyes, Pl planner/executor, S stop criteria, H hand-off schema, and onwards
through the later sets. A methodology's directory name is its feature list.

| Term | Means |
|---|---|
| **MI** | maintainability index — volume, complexity and size in one number; the basis of the parsimony factor |
| **SLOC** | source lines of code: non-blank, non-comment lines of the non-test sources |
| **DoD** | definition of done — the parameter deciding when the agent stops |
| **held-out** | the second test suite the agent never sees, scored separately |
| **parsimony factor** | the clamped ratio of the run's MI to the reference's, multiplying the test fraction |
| **oracle** | the project's own verification script — it decides done and produces the score |
| **anchor** | a deliberately degenerate methodology or project (`00_*`), there to bound the measurement, never to be improved |
| **gate** | the conditions that must hold before any result is interpreted |
| **pre-flight** | the baseline check before a single token is spent |
| **arm** | one methodology in a comparison |
| `cfg_` / `res_` / `tk_` / `prf_` | column prefixes: configuration / result / tokens / performance |
