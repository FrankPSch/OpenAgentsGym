# p06_qc_ema_cross

## Task

Using the QuantConnect MCP tools, build, compile, and backtest an EMA(5)/EMA(160) crossover
strategy on SPY purely in one `main.py` — no further Python files in the project — then record the
result as `qc_results_01.json` and `qc_results_02.json` in this workspace.

This task is not scored by pytest — the verifier reads those two files and, separately, pulls the
project's files straight back from QuantConnect through the QuantConnect Cloud API (not a local
copy you hand it), so the graded code is whatever is actually live in the project.

## Strategy specification

- Symbol: `SPY` only.
- Resolution: Daily.
- Indicators: `ExponentialMovingAverage` with periods 5 (fast) and 160 (slow), fed daily
  consolidated bars.
- Entry: go long (100% of the portfolio, or a fixed position) when the fast EMA crosses above the
  slow EMA.
- Exit: liquidate (flat) when the fast EMA crosses below the slow EMA. Do not go short.
- Backtest window: `2025-01-01` to `2025-12-31` inclusive.
- Warm up the indicators with enough history before 2025-01-01 that the 160-period EMA is valid on
  the first trading day of 2025 (`SetWarmUp` or an explicit lookback), so the first signal in the
  window isn't an artifact of a cold indicator.
- Everything lives in `main.py`. Don't split the algorithm across helper modules — the project must
  contain exactly one Python file.

## Required steps

1. Create a new QuantConnect project (Python) for this strategy via the MCP tools.
2. Write the algorithm to `main.py` in that project implementing the specification above.
3. Compile the project. Fix any errors and recompile until it is clean — the compiled state you
   leave the project in is what gets checked.
4. Write `qc_results_01.json` (schema below) into this workspace.
5. Run a backtest over the exact window above.
6. Read back the backtest's statistics and order history via the MCP tools.
7. Write `qc_results_02.json` (schema below) into this workspace.

## `qc_results_01.json` schema (written right after compiling, before any backtest)

```json
{
  "project_id": 12345,
  "project_name": "string",
  "symbol": "SPY",
  "resolution": "Daily",
  "fast_period": 5,
  "slow_period": 160,
  "compile_success": true
}
```

- `compile_success` must be the actual result of the compile step (`true` only if it came back
  clean).

## `qc_results_02.json` schema (written after the backtest completes)

```json
{
  "project_id": 12345,
  "backtest_id": "string",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "statistics": { "...": "the statistics dict/object returned by the QC backtest read, verbatim" },
  "orders_count": 0
}
```

- `project_id` must match the one in `qc_results_01.json`.
- `statistics` must be the actual object QuantConnect returned for this backtest (its own key
  names, e.g. `"Total Trades"`, `"Net Profit"`, `"Sharpe Ratio"` — do not rename or invent keys).
- `orders_count` is the number of orders QuantConnect recorded for this backtest (from reading the
  backtest's order history), and must be greater than 0 — a strategy that never crosses in 2025
  and never trades fails verification.

## Verification

`run_verification.py` checks both files for internal consistency (parameters, window, matching
`project_id`), then scores the task in two stages:

1. **Gate** — `compile_success` is true, `statistics` is non-empty, `orders_count >= 1`, and the
   QuantConnect project contains exactly one Python file (`main.py`, nothing else). Any of these
   failing scores 0.00 outright.
2. **Code quality** — the verifier fetches `main.py` live from your QuantConnect project via
   `project_id` (the QuantConnect Cloud API, not anything you leave in this workspace) and scores
   it with the same Maintainability Index / parsimony approach every other tier in this repo uses
   (`lib/oracle.py`): a bulkier or more convoluted `main.py` than the reference solution scores
   lower. This runs whether or not the gate passed, so the quality metrics are always recorded.

Because the verifier re-reads the code from QuantConnect itself, editing a local copy in this
workspace after the fact has no effect on the score.
