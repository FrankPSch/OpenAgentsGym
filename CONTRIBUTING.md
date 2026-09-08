# Contributing

Two contributions carry the project: a **new methodology** and a **new project**. Both are additive
— a directory that joins the matrix by existing. Everything else is a change to the specification
first, so open an issue before writing code.

`oam_targetpicture.md` defines behaviour. If a change makes the code and that document disagree, the
document is what gets fixed, in the same pull request.

---

## A new methodology

One directory under `methodology/`, Markdown only. No code, no scripts, no framework.

- One idea per methodology. The numbered ladder combines features deliberately; above it, arms test
  one element each so a result can be attributed.
- It must be readable as a normal agent entry file — nothing that depends on this harness.
- Do not tune against the anchors. `00_empty` and `00_sabotage` bound the measurement and are never
  adjusted to make a result look better.
- Say in the pull request what you expect it to change, and against which arm you read it: the empty
  anchor for the effect, the incumbent for whether it beats current practice.

## A new project

One directory under `projects/`, and it must ship all five of these:

1. **`prompt.md`** — the task, in the structure the existing projects use, plus `.environment` and
   `.requirements` pinning the runtime in the template.
2. **A pristine template whose visible test suite fails on it.** Pre-flight expects that failure; a
   template that already passes cannot measure anything and the run aborts.
3. **A reference solution under `reference/`**, solved by you, with the oracle's output on it stored
   beside it. The oracle constants (`SIZE_REF`, `MI_REF`) are read off that measurement, never
   chosen. A constant that cannot be re-measured from an artefact on disk is a number the reader has
   to trust.
4. **A held-out suite**, roughly half the size of the visible one, same public contract, different
   inputs. It may test **only what `prompt.md` states** — testing unstated requirements penalises a
   methodology for not reading the author's mind. It must pass on the reference and fail on the
   template.
5. **`run_verification.py`** — the thin wrapper over `lib/oracle.py`, with the constants from step 3.

A project on which every methodology scores at the top ranks by cost alone. That is a statement
about the project, not about methodology: it is kept for smoke runs, not for ranking.

---

## Pull requests

- Run `run_smoke_model_02.bat` and paste the exit code.
- If the change can move scores, say so explicitly and name which columns.
- Do not commit anything under `local/` — run directories, logs and the results table stay local.
  Paste the rows you want to discuss into the pull request instead.
- Results in an issue or pull request must state model, effort, repeats and campaign label. A score
  without its constants is not comparable to anything.

## Reporting a result that surprises you

That is the most valuable issue type. Include the run's constants, both anchor scores from the same
campaign, and the validity gate's verdict. A ranking whose gate did not pass is a finding about the
apparatus, and worth reporting as one.
