# p07_qc_bugfix_refactor

## Task

`main.py` in this workspace is an existing QuantConnect algorithm that does not do what it is
supposed to do. Using the QuantConnect MCP tools, upload it to a **new** QuantConnect project as
it is, compile it, then fix and refactor it until it meets the specification below, and prove it
with a backtest. Record the outcome as `qc_results_01.json` and `qc_results_02.json` in this
workspace.

This task is not scored by pytest — the verifier reads those two files and, separately, pulls the
project's files straight back from QuantConnect through the QuantConnect Cloud API (not the local
copy you hand it), so the graded code is whatever is actually live in the project.

## What the algorithm is supposed to do

- Symbol: `SPY` only, Resolution Daily.
- Indicators: `ExponentialMovingAverage`, period 5 (fast) and 160 (slow), **both fed daily bars**.
- Entry: go long 100% of the portfolio while the fast EMA is above the slow EMA.
- Exit: liquidate when the fast EMA is no longer above the slow EMA. Never go short.
- Backtest window: `2025-01-01` to `2025-12-31` inclusive.
- Warm the indicators with enough daily history that the 160-period EMA is valid on the first
  trading day of 2025, so the first signal in the window isn't an artifact of a cold indicator.
- Everything lives in `main.py`. The project must contain exactly one Python file.

The code in this workspace deviates from that specification in more than one place. Finding the
deviations is part of the task — they are not listed here.

## Required steps

1. Create a new QuantConnect project (Python) via the MCP tools.
2. Upload `main.py` from this workspace **unchanged** and compile it. Record whether that compile
   succeeded.
3. Write `qc_results_01.json` (schema below).
4. Fix the defects and refactor the algorithm so it meets the specification, keeping it in one
   file. Dead code, misleading names and leftover scaffolding are part of what a refactor removes.
5. Compile the fixed project. Fix any errors and recompile until it is clean — the compiled state
   you leave the project in is what gets checked.
6. Run a backtest over the exact window above.
7. Read back the backtest's statistics and order history via the MCP tools.
8. Write `qc_results_02.json` (schema below).

## `qc_results_01.json` schema (written after the as-is upload and compile)

```json
{
  "project_id": 12345,
  "project_name": "string",
  "baseline_compile_success": true,
  "defects_found": ["short description", "..."]
}
```

- `baseline_compile_success` must be the actual result of compiling the **unchanged** file
  (`true` only if it came back clean).
- `defects_found` is your own list of what was wrong, one short string each, at least one entry.
  It is recorded, not scored — the code and the backtest decide the score.

## `qc_results_02.json` schema (written after the backtest completes)

```json
{
  "project_id": 12345,
  "backtest_id": "string",
  "symbol": "SPY",
  "resolution": "Daily",
  "fast_period": 5,
  "slow_period": 160,
  "compile_success": true,
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "statistics": { "...": "the statistics dict/object returned by the QC backtest read, verbatim" },
  "orders_count": 0
}
```

- `project_id` must match the one in `qc_results_01.json` — fix the project you created, do not
  start a second one.
- `statistics` must be the actual object QuantConnect returned for this backtest (its own key
  names, e.g. `"Total Trades"`, `"Net Profit"`, `"Sharpe Ratio"` — do not rename or invent keys).
- `orders_count` is the number of orders QuantConnect recorded for this backtest, and must be
  greater than 0. The algorithm as given never trades; one that still never trades has not been
  fixed.

## Verification

`run_verification.py` checks both files for internal consistency (parameters, window, matching
`project_id`), then scores the task in two stages:

1. **Gate** — `compile_success` is true, `statistics` is non-empty, `orders_count >= 1`, the
   QuantConnect project contains exactly one Python file (`main.py`, nothing else), and the live
   source no longer carries the defects: it trades `SPY`, feeds both EMAs daily bars, and its
   entry is a comparison rather than an equality test. Any of these failing scores 0.00 outright.
2. **Code quality** — the verifier fetches `main.py` live from your QuantConnect project via
   `project_id` (the QuantConnect Cloud API, not anything you leave in this workspace) and scores
   it with the same Maintainability Index / parsimony approach every other tier in this repo uses
   (`lib/oracle.py`): a bulkier or more convoluted `main.py` than the reference solution scores
   lower. This runs whether or not the gate passed, so the quality metrics are always recorded.

Because the verifier re-reads the code from QuantConnect itself, editing the local copy in this
workspace after the fact has no effect on the score.
