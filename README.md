# OpenAgentsGym

**Benchmark the methods, not the models.** Run one task under many sets of agent instructions and
compare quality, cost and adherence.

The instructions an agent works under — its process, roles, document types and guardrails — are the
largest uncontrolled variable in agentic work, and they are normally argued about rather than
measured. OpenAgentsGym holds the model, the effort level and the task constant and varies only that
text, so the difference between two ways of working comes out as numbers in one table.

---

## What it does

| Term | Is |
|---|---|
| **methodology** | one candidate under test: a directory of plain Markdown under `methodology/`. Prose only — no code, no framework. |
| **project** | one task: a directory under `projects/` with a prompt, a pristine template, its own oracle and a held-out test suite. |
| **run** | one methodology executed once against one project, in its own directory, ending in one CSV row. |
| **campaign** | a set of runs compared with each other, with model, effort and every other constant fixed across it. |

A run deploys the methodology's entry file into a fresh copy of the project, invokes the agent with
the project's prompt, then scores the result with the project's own oracle:

```
score = (visible tests passed / total) × parsimony_factor
parsimony_factor = clamp(MI_run / MI_REF, 0.8, 1.0)
```

`MI` is the SEI-normalised Maintainability Index; `MI_REF` is measured from a stored reference
solution. The parsimony factor exists so a methodology cannot win by writing more code.

Two anchors bound every campaign: `00_empty` (no methodology at all) and `00_sabotage` (a
deliberately bad one). **No ranking is believed until sabotage scores below every real methodology.**
That validity gate, not the leaderboard, is the first thing to read.

---

## First result

Level-3 screen, 8–9 September 2026: all 33 methodologies once on `04_python_xlarge`
(`claude-opus-5`, low effort, one repeat, `$4.00` cap, review off). Every arm passed all 50 visible
tests; 31 of 33 passed all 26 held-out tests. The spread is the parsimony factor — how compact the
passing code is. One repeat orders, it does not decide (manual, chapter 6): arms within 0.05 are
ties.

| # | methodology | score | held-out | MI | SLOC | turns | $ |
|---|---|---|---|---|---|---|---|
| 1 | `29_invariants_test_first_relative_stop` | 0.99 | 1.00 | 15.8 | 186 | 32 | 1.15 |
| 2 | `26_test_first` | 0.99 | 0.96 | 15.9 | 187 | 50 | 1.64 |
| 3 | `15_invariants` | 0.98 | 1.00 | 15.7 | 187 | 36 | 0.93 |
| 4 | `28_invariants_test_first` | 0.97 | 1.00 | 15.6 | 186 | 37 | 1.10 |
| 5 | `19_relative_stop` | 0.96 | 1.00 | 15.3 | 187 | 37 | 0.82 |
| 6 | `24_two_proposals` | 0.96 | 1.00 | 15.4 | 193 | 33 | 1.04 |
| 7 | `07_process_doctypes_roles` | 0.96 | 1.00 | 15.3 | 193 | 59 | 2.14 |
| 8 | `06_process_roles` | 0.95 | 1.00 | 15.2 | 193 | 38 | 1.54 |
| … | | | | | | | |
| 15 | `31_pipeline_source` | 0.93 | 1.00 | 14.9 | 191 | 34 | 0.79 |
| 25 | `00_empty` | 0.91 | 1.00 | 14.6 | 199 | 22 | 1.16 |
| 27 | `00_sabotage` | 0.90 | 1.00 | 14.4 | 193 | 34 | 0.85 |
| 29 | `30_delivery_kernel` | 0.90 | 1.00 | 14.4 | 198 | 45 | 1.74 |
| 32 | `03_roles` | 0.86 | 1.00 | 13.7 | 199 | 42 | 1.83 |
| 33 | `08_process_doctypes_roles_guardrails` | 0.86 | 1.00 | 13.8 | 194 | 47 | 1.94 |

What it says, at this model and effort: short, checkable constraints on the *output* (`26`, `15`,
`19`, `24`) beat process instructions; the four-layer stack `08` — the incumbent until this screen —
is last, slowest and dearest; roles are the weak ingredient. `29` is the composition of the three
winners and matches the best score at two thirds of the turns; it is the provisional incumbent
until three repeats confirm it. `30` is a working methodology's kernel transcribed into this frame and `31`
the same kernel untranscribed; both land beside `00_empty`, and the transcription cost a reviewer
round the source text did not trigger. Full rows, both projects: [`results_repository.csv`](results_repository.csv).
Score against cost, one panel per campaign and project: [`results_pareto.svg`](results_pareto.svg) — written by every consolidation, never edited by hand.

---

## Quick start

Requirements: Windows, Python via the `py` launcher, `claude` on the `PATH` and logged in, git, and **no
`CLAUDE.md` or `AGENTS.md` in any parent folder** of the repository (the CLI walks upwards and would
load it into every run — pre-flight aborts instead of measuring it).

```
run_smoke_model_02.bat                 double-click; proves the whole chain works (level 2)
run.bat <project> <methodology>        one specific pair (level 2 unless --config says otherwise)
run_turbo_model_01.bat                 every pair once on level 1, the cheapest model
run_screen_model_03.bat                every methodology once on 04_python_xlarge, level 3 (the screen)
run_all_model_03.bat                   every pair on level 3 (frontier model, low effort)
run_all_model_04.bat                   every pair on level 4
run_selected_model_04.bat              the validity gate on level 4 (edit the list in the file)
rebuild_results_table.bat              re-merge the results table and print the validity gate
```

All campaign constants live in the four `.llm_config.model_01` … `model_04` files — one per
capability level: 1 the cheapest model (`run_turbo_model_01.bat`), 2 the workhorse (`run.bat`,
`run_smoke_model_02.bat`), 3 the frontier model at low effort (`run_all_model_03.bat`), 4 the model above the
frontier tier (`run_all_model_04.bat`, `run_selected_model_04.bat`). The vendor's model id is on
the `MODEL=` line and nowhere else. For a one-off, copy a file, edit the copy and pass it with
`--config`; its base name becomes the campaign label on every row, so two
campaigns cannot be pooled by accident.

---

## Layout

```
methodology/     43 live candidates (+5 outdated, kept with their rows): 00_empty, 00_sabotage, a four-feature ladder, one idea each, two compositions, one transcribed kernel and its untranscribed source
projects/        00_fail (impossible by construction) and five Python tasks of growing size
lib/oracle.py    the shared scorer: tests, SLOC, complexity, Halstead, maintainability index
run_master.py    the harness — pre-flight, invoke, score, one CSV row
*.bat            the entry points
local/           run directories, logs and the results table (git-ignored, never published)
```

Everything is a directory listing: a new methodology or project joins the matrix by existing.

---

## Documents

| File | Contains |
|---|---|
| [`oam_targetpicture.md`](oam_targetpicture.md) | the specification — defines behaviour; the source of truth |
| [`oam_manual.md`](oam_manual.md) | how to use it, extend a project, extend a methodology, read the columns |

---

## Status and limitations

Working apparatus, early results. Read before quoting a number:

- **Windows only.** The harness runs elsewhere, but the interpreter pin behaves differently and a
  non-Windows run is a smoke test of the plumbing, not a measurement.
- **Claude only.** `ENGINE` accepts one value today; cross-vendor token counts would not be
  comparable in any case. The coupling is confined to `run_master.py` — the methodologies, the
  projects, the oracle and the batch files name no vendor — and chapter 18 of the specification
  lists every point a second engine would have to touch.
- **Python projects only.** A project type that filters which methodologies apply is not built.
- **One repeat so far.** The level-3 screen above orders the arms; the repeats that make the
  ordering a result are the next campaign. `05_python_refactor_large` saturates at this level (20
  arms tie at 1.00) and serves as a cost check only.
- **Costs are real.** A campaign is methodologies × projects × repeats invocations of a paid CLI.
  Start with `run_smoke_model_02.bat` and read `tk_cost_usd` before scaling anything up.

---

## Contributing

New methodologies and new projects are the useful contributions, and both are additive — a
directory. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for what a submission must ship.

## License

MIT — see [`LICENSE`](LICENSE).
