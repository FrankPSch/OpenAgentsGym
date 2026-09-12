"""Fill the columns added on 2026-09-12 into rows written before they existed.

    py -3 backfill_columns.py --dry-run
    py -3 backfill_columns.py --apply

Kept in the repository as the evidence for a commit that rewrites recorded
rows, on the same footing as migrate_naming.py.

WHAT IT DOES AND DOES NOT DO. Only the new columns are written. Every existing
cell is copied through untouched, so a backfilled row differs from its old self
in exactly the added fields and in nothing else -- the point is to make the new
columns usable on the runs already taken, not to re-derive anything that was
already published.

The values are not invented: each one is re-read from that run's own
result.json, the payload the CLI wrote at the time, through the same parser a
new run goes through. A run whose result.json is gone or unparsable keeps blank
cells, which is the honest answer for it.

Rows in results_repository.csv whose run directory no longer exists cannot be
backfilled at all and stay blank. That is visible rather than hidden: the
published table keeps rows whose directory is gone (see consolidate), so the
column will be blank for older campaigns and filled for recent ones, and a
reader must not assume a blank cell means "no tool calls".
"""
import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import run_master as R

NEW = ["res_stop_reason", "res_error_name", "res_error_status", "res_tool_calls",
       "res_subagents_failed", "res_subagents_refused", "res_web_searches",
       "res_context_window", "res_service_tier", "prf_api_s", "prf_ttft_s",
       "res_syntax_ok", "res_syntax_error", "res_collection_errors"]


def derive(run_dir, engine):
    """The new columns for one run, from the artefacts that run left behind.

    Two independent sources, and either can answer alone: result.json for what the engine
    reported, and the workspace plus junit.xml for what the code turned out to be. A run whose
    result.json is unparsable can still say whether its Python parses.
    """
    out = {}

    # Workspace-derived first, because it does not depend on the engine's stdout at all.
    ws = os.path.join(run_dir, "project_workspace")
    if os.path.isdir(ws):
        ok, err = R.workspace_syntax(ws)
        if ok:
            out["res_syntax_ok"] = ok
        if err:
            out["res_syntax_error"] = err
    ce = R.collection_errors(run_dir)
    if ce != "":
        out["res_collection_errors"] = ce

    rj = os.path.join(run_dir, "result.json")
    if not os.path.isfile(rj):
        return out
    raw = open(rj, encoding="utf-8", errors="replace").read()
    code = R.read_exit_code(R.Path(rj))
    rec = R.stream_result_record(raw, code) if engine == "opencode" else R.result_record(raw)
    if not isinstance(rec, dict):
        return out
    stop = rec.get("stop_reason") or rec.get("terminal_reason")
    if isinstance(stop, str) and stop.strip():
        out["res_stop_reason"] = stop.strip()[:40]

    err = rec.get("error_name")
    if not err and rec.get("is_error"):
        err = rec.get("api_error_status") or "error"
    if err:
        out["res_error_name"] = str(err).strip()[:60]
    status = rec.get("error_status")
    if status is None:
        status = rec.get("api_error_status")
    if isinstance(status, (int, float)):
        out["res_error_status"] = status

    if rec.get("tool_calls"):
        out["res_tool_calls"] = rec["tool_calls"]

    stats = rec.get("subagent_stats")
    if isinstance(stats, dict) and stats:
        if stats.get("failed") != "":
            out["res_subagents_failed"] = stats.get("failed", "")
        refused = stats.get("refused")
        if isinstance(refused, dict):
            out["res_subagents_refused"] = sum(
                v for v in refused.values() if isinstance(v, (int, float)))
        elif isinstance(refused, (int, float)):
            out["res_subagents_refused"] = refused

    usage = rec.get("usage") or {}
    server = usage.get("server_tool_use")
    if isinstance(server, dict) and server.get("web_search_requests") is not None:
        out["res_web_searches"] = server["web_search_requests"]
    if usage.get("service_tier"):
        out["res_service_tier"] = usage["service_tier"]

    mu = rec.get("modelUsage") or {}
    if isinstance(mu, dict) and mu:
        def spend(item):
            e = item[1]
            if not isinstance(e, dict):
                return (0.0, 0)
            return (float(e.get("costUSD") or 0), int(e.get("outputTokens") or 0))
        _key, entry = max(mu.items(), key=spend)
        if isinstance(entry, dict) and entry.get("contextWindow") is not None:
            out["res_context_window"] = entry["contextWindow"]

    api_ms = rec.get("duration_api_ms")
    if isinstance(api_ms, (int, float)):
        out["prf_api_s"] = round(api_ms / 1000.0, 1)
    ttft = rec.get("ttft_ms")
    if isinstance(ttft, (int, float)):
        out["prf_ttft_s"] = round(ttft / 1000.0, 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.apply == args.dry_run:
        sys.exit("choose exactly one of --apply / --dry-run")

    runs = os.path.join(ROOT, "local", "runs")
    if not os.path.isdir(runs):
        sys.exit("no local/runs")

    touched, already, cannot = 0, 0, 0
    for name in sorted(os.listdir(runs)):
        path = os.path.join(runs, name, "results_run.csv")
        if not os.path.isfile(path):
            continue
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            continue
        row = rows[0]
        new = derive(os.path.join(runs, name), (row.get("cfg_engine") or "").strip())
        if not new:
            cannot += 1
            continue
        if all((row.get(k) or "") == str(v) for k, v in new.items()):
            already += 1
            continue
        touched += 1
        print("  %-46s %s" % (name[:46], ", ".join("%s=%s" % kv for kv in sorted(new.items()))))
        if args.apply:
            # Every existing cell copied through; only the new keys are set. Written in COLUMNS
            # order so the file gains the header the current schema expects.
            out = {c: row.get(c, "") for c in R.COLUMNS}
            out.update({k: v for k, v in new.items()})
            with open(path, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh, lineterminator="\n")
                w.writerow([R.csv_name(c) for c in R.COLUMNS])
                w.writerow([out[c] for c in R.COLUMNS])

    print("\nbackfilled %d, already current %d, cannot say %d" % (touched, already, cannot))
    if not args.apply:
        print("DRY RUN - nothing was changed. Re-run with --apply, then --consolidate.")


if __name__ == "__main__":
    main()
