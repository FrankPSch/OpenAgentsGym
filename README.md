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
| **oracle** | a project's `run_verification.py`: the code that scores one run. Every oracle calls the same shared metric library, `lib/oracle.py`. |

If you come from the general literature on agent evaluation: a run is a *trial*, an oracle is a
*grader*, what it reads is the *outcome*, the run directory is the *transcript*, and the CLI is the
*agent harness* — `run_master.py` being the evaluation harness around it. The specification
(chapter 2.1) lists the translation; everything here uses the four words above.

A run deploys the methodology's entry file into a fresh copy of the project, invokes the agent with
the project's prompt, then scores what it left behind with the project's own oracle:

```
score = (visible tests passed / total) × parsimony_factor
parsimony_factor = clamp(MI_run / MI_REF, 0.8, 1.0)
```

`MI` is the SEI-normalised Maintainability Index; `MI_REF` is measured from a stored reference
solution. The parsimony factor exists so a methodology cannot win by writing more code.

That score says whether a run worked. Beside it the table carries `sc_effort` (duration, turns,
output tokens), `sc_quality` (maintainability, nesting depth, longest function) and their mean
`sc_overall`, each placing a run by how far it is behind the leader of its own project — so the best
run of every project is 1.0 and the worst run of the whole table is 0.0. They are what separates
arms on a project where every score ties, and they are blank on a run that did not pass, because an
effort number without a correctness gate rewards giving up early.

Two anchors bound every campaign: `m00_empty` (no methodology at all) and `m47_sabotage` (a
deliberately bad one). **No ranking is believed until sabotage scores below every real methodology.**
That validity gate, not the leaderboard, is the first thing to read.

---

## Quick start

Requirements: Windows, Python via the `py` launcher, `claude` on the `PATH` and logged in, git, and **no
`CLAUDE.md` or `AGENTS.md` in any parent folder** of the repository (the CLI walks upwards and would
load it into every run — pre-flight aborts instead of measuring it).

Every entry point is a batch file in the repository root, and the listing is the documentation —
`dir *.bat` is current, anything written here would not be. The names say what they do:

```
run.bat <project> <methodology>   one specific pair; --config <file> picks another engine
run_smoke_*.bat                   double-click; proves the whole chain works, cheaply
run_turbo_*.bat                   every pair once, on the cheapest engine
run_screen_*.bat                  every methodology once on the ranking project
run_all_*.bat                     every pair, on the engine the name carries
run_selected_*.bat                a hand-picked list; edit it in the file
rebuild_results_table.bat         re-merge the results table and print the validity gate

check_engine_matrix.bat           verify a machine can run a second engine; spends nothing
run_engine_matrix.bat [/billed]   one project x one methodology across engines and local models
run_engine_matrix.p<nn>.bat       the same for one project, by double-click; one file per project

NN_*.bat                          numbered setup and campaign steps, run in that order: build the
                                  local models, start the gateway, then a sweep
```

A batch file bound to one engine carries that engine's name, so the file you double-click and the
campaign label on the row it produces are the same word.

Setting a fresh Windows machine up — Python, Node, Ollama, LiteLLM, opencode and the three engine
families in the order they need to be installed — is [`oam_install_windows.md`](oam_install_windows.md).

All campaign constants live in the `.llm_config.<engine>` files, one per engine, and nowhere else;
[`NAMING.md`](NAMING.md) holds the register of which engine is which and which are retired. The
low-numbered ones are the capability levels of the reference engine — cheapest, workhorse, frontier
at low effort, and above the frontier tier — and the rest are the other vendors' CLIs and the local
models behind the gateway. The vendor's model id is on
the `MODEL=` line and nowhere else. For a one-off, copy a file, edit the copy and pass it with
`--config`; its base name becomes the campaign label on every row, so two
campaigns cannot be pooled by accident.

---

## Layout

```
methodology/     the candidates: m00_empty, m47_sabotage, a four-feature ladder, one idea each, compositions of the winners, a transcribed kernel and its untranscribed source. A directory suffixed _outdated is retired but keeps its rows
projects/        p00_fail (impossible by construction), Python tasks of growing size, QuantConnect tiers driven through MCP, SWE-bench-style instances against real upstream repositories
lib/oracle.py    the shared metric library every project's oracle calls: tests, SLOC, complexity, Halstead, maintainability index
run_master.py    the harness — pre-flight, invoke, score, one CSV row
*.bat            the entry points
results_repository.csv   every run ever made, one row each; rebuilt by consolidation, never hand-edited
results_pareto.svg       code quality against effort spent, one panel per campaign and project; written by the same consolidation
local/           run directories and logs (git-ignored, never published)
```

Everything is a directory listing: a new methodology or project joins the matrix by existing.

---

## Documents

| File | Contains |
|---|---|
| [`oam_targetpicture.md`](oam_targetpicture.md) | the specification — defines behaviour; the source of truth |
| [`oam_manual.md`](oam_manual.md) | how to use it, extend a project, extend a methodology, read the columns |
| [`oam_install_windows.md`](oam_install_windows.md) | bringing a fresh Windows machine up — requirements, then the Claude, GPT and local chapters in install order |
| [`NAMING.md`](NAMING.md) | how projects, methodologies and engines are named and numbered, and the engine register |

---

## Status and limitations

Working apparatus, early results. Read before quoting a number:

- **Windows only.** The harness runs elsewhere, but the interpreter pin behaves differently and a
  non-Windows run is a smoke test of the plumbing, not a measurement.
- **Three engines, two of them measured.** `ENGINE` accepts `claude`, `opencode` and `gpt`.
  `claude` is the reference engine and most published rows come from it. `opencode` (a
  model-agnostic CLI, pointed at any OpenAI-compatible endpoint) has been run end to end and
  produces scored rows against local models; its one unobserved part is cost arithmetic on a paid
  model, since every opencode run so far used a model priced at zero. `gpt` (the `codex` CLI) is
  **structural only** — its
  subcommand, flags, stdout shape and model rule are documentation-derived and have never been
  executed; a run aborts with exit 6 until the CLI is installed and the registry row corrected
  against observed behaviour. The coupling stays confined to `run_master.py`: the methodologies,
  the projects, the oracle and the batch files still name no vendor.
- **Engine is a treatment, not a constant.** A different engine means a different system prompt,
  different tool schemas and a different edit mechanism, so rows from two engines are not poolable
  — `cfg_engine` is in the campaign-constant tuple for that reason. Cross-engine claims are
  directional ("29 beats 08 under both"), never absolute. Token counters are not comparable across
  vendors either; cost and wall-clock are the only cross-engine axes.
- **Non-claude engines lose columns.** `opencode` has no effort flag and no per-run budget flag, so
  `cfg_effort_enforced=false` and `cfg_bound=walltime`; no event in its stream carries a model id,
  so `res_model_served` is blank — the guard against silent model substitution does not exist
  there. Its `cfg_endpoint` reads `native` even when a gateway served the run, because the endpoint
  is addressed through the model id rather than an environment variable. `cfg_tools` is recorded
  with an `unenforced:` prefix, since that engine has no tool-allowlist flag.
- **Python projects only.** A project type that filters which methodologies apply is not built.
- **One repeat so far.** Every published row is a single run, so the table orders arms at pass@1 and
  arms within 0.05 of each other are ties; the repeats that would make an ordering a result have not
  been run. With more than one run per pair, report pass^k as
  well — every run of a pair succeeding — because that asks for consistency rather than one lucky
  draw.
- **Some projects saturate on a strong engine.** The refactor project and both QuantConnect tiers
  have every arm at the top of the range, sabotage included. A project every arm passes orders by
  cost alone; those are smoke tests for the plumbing — the QuantConnect pair for the MCP path — and
  are not read as a ranking. The consolidation prints one line per project saying how many distinct
  scores its arms produced, so saturation is visible without anyone having to invent a threshold.
  Difficulty belongs where the empty anchor still fails: calibrate a new project on the cheapest
  engine before spending a real campaign on it.
- **Costs are real.** A campaign is methodologies × projects × repeats invocations of a paid CLI.
  Start with the smoke batch and read `tk_cost_usd` before scaling anything up.

---

## Contributing

New methodologies and new projects are the useful contributions, and both are additive — a
directory. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for what a submission must ship.

## License

MIT — see [`LICENSE`](LICENSE).
