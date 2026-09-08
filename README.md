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

## Quick start

Requirements: Windows, Python via the `py` launcher, `claude` on the `PATH`, git, and **no
`CLAUDE.md` or `AGENTS.md` in any parent folder** of the repository (the CLI walks upwards and would
load it into every run — pre-flight aborts instead of measuring it).

```
run_smoke_model_02.bat                 double-click; proves the whole chain works (level 2)
run.bat <project> <methodology>        one specific pair (level 2 unless --config says otherwise)
run_turbo_model_01.bat                 every pair once on level 1, the cheapest model
run_all_model_04.bat                   every pair on level 4
run_selected_model_04.bat              the validity gate on level 4 (edit the list in the file)
rebuild_results_table.bat              re-merge the results table and print the validity gate
```

All campaign constants live in the four `.llm_config.model_01` … `model_04` files — one per
capability level: 1 the cheapest model (`run_turbo_model_01.bat`), 2 the workhorse (`run.bat`,
`run_smoke_model_02.bat`), 3 the frontier model at low effort (by hand only), 4 the model above the
frontier tier (`run_all_model_04.bat`, `run_selected_model_04.bat`). The vendor's model id is on
the `MODEL=` line and nowhere else. For a one-off, copy a file, edit the copy and pass it with
`--config`; its base name becomes the campaign label on every row, so two
campaigns cannot be pooled by accident.

---

## Layout

```
methodology/     29 candidates: 00_empty, 00_sabotage, a four-feature ladder, then one idea each
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
- **The validity gate has not yet passed on a full campaign.** In the first campaign the sabotage
  anchor outscored most real methodologies, because every arm passed every test and only parsimony
  separated them — a statement about the task being too easy, not about methodology.
- **Costs are real.** A campaign is methodologies × projects × repeats invocations of a paid CLI.
  Start with `run_smoke_model_02.bat` and read `tk_cost_usd` before scaling anything up.

---

## Contributing

New methodologies and new projects are the useful contributions, and both are additive — a
directory. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for what a submission must ship.

## License

MIT — see [`LICENSE`](LICENSE).
