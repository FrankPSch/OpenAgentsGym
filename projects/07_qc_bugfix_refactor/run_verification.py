#!/usr/bin/env python3
"""Project verifier for 07_qc_bugfix_refactor.

Like 06, this tier is not scored by pytest: the agent drives the real QuantConnect MCP tools --
create a project, upload the workspace's broken main.py unchanged, compile it, then fix and
refactor it, compile again and backtest -- and records the outcome as two files:

  qc_results_01.json -- after the as-is upload and compile (project identity, baseline compile,
                        the agent's own list of defects; recorded, not scored).
  qc_results_02.json -- after the backtest (parameters, window, statistics, orders_count),
                        sharing project_id with qc_results_01.json.

This script:
  1. Reads both files and checks them against the spec (symbol, resolution, EMA periods, window,
     matching project_id).
  2. Gate ("passed"): compile_success is true AND the backtest produced results (non-empty
     statistics, at least one order) AND the project holds exactly one Python file, main.py, AND
     the live source no longer carries the three defects the task is about (wrong symbol, mixed
     resolution, equality instead of comparison).
  3. Quality: fetches main.py straight from the QuantConnect Cloud API (using project_id, not a
     local copy) and scores it with lib/oracle.py's code_metrics, exactly as every other tier.

score = (1.0 if gate_passed else 0.0) * parsimony_factor(mi, MI_REF)

Requires QUANTCONNECT_USER_ID and QUANTCONNECT_API_TOKEN in the environment. Their absence is an
environment error (exit 2), not a failed run.

Contract kept identical to the other tiers: <workspace> <run dir> [baseline|""] [holdout dir]
[template dir]. Exit 0 = pass, 1 = fail, 2 = environment/setup error.
"""
import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from oracle import code_metrics, parsimony_factor  # noqa: E402

MI_REF = 0.0      # replaced below from reference/metrics.txt
SIZE_REF = 0      # recorded, not scored
QC_API_BASE = "https://www.quantconnect.com/api/v2"

REQUIRED_01 = ("project_id", "project_name", "baseline_compile_success", "defects_found")
REQUIRED_02 = ("project_id", "backtest_id", "symbol", "resolution", "fast_period", "slow_period",
               "compile_success", "start_date", "end_date", "statistics", "orders_count")


def read_reference_metrics():
    """MI_REF and SIZE_REF come from reference/metrics.txt -- measured, never chosen."""
    global MI_REF, SIZE_REF
    path = Path(__file__).resolve().parent / "reference" / "metrics.txt"
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        k, v = (p.strip() for p in line.split("=", 1))
        if k == "mi":
            MI_REF = float(v)
        elif k == "sloc":
            SIZE_REF = int(v)
    return MI_REF > 0


def qc_auth_headers():
    """Basic-auth headers for the QuantConnect Cloud API (timestamped SHA-256 hash scheme)."""
    user_id = os.environ.get("QUANTCONNECT_USER_ID")
    token = os.environ.get("QUANTCONNECT_API_TOKEN")
    if not user_id or not token:
        return None
    timestamp = str(int(time.time()))
    digest = hashlib.sha256(("%s:%s" % (token, timestamp)).encode("utf-8")).hexdigest()
    auth = base64.b64encode(("%s:%s" % (user_id, digest)).encode("utf-8")).decode("ascii")
    return {"Authorization": "Basic %s" % auth, "Timestamp": timestamp}


def fetch_project_files(project_id):
    """List+read every file QuantConnect Cloud has for project_id; None on any failure."""
    headers = qc_auth_headers()
    if headers is None:
        return None
    url = "%s/files/read?projectId=%s" % (QC_API_BASE, project_id)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, OSError):
        return None
    if not payload.get("success"):
        return None
    return payload.get("files") or []


def load_json(path):
    if not path.is_file():
        return None, "%s not found in workspace" % path.name
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (json.JSONDecodeError, OSError) as exc:
        return None, "%s is not valid JSON: %s" % (path.name, exc)


def validate_fields(data01, data02):
    reasons = []
    for key in REQUIRED_01:
        if key not in data01:
            reasons.append("qc_results_01.json missing field: %s" % key)
    for key in REQUIRED_02:
        if key not in data02:
            reasons.append("qc_results_02.json missing field: %s" % key)
    if reasons:
        return reasons

    if data02.get("symbol") != "SPY":
        reasons.append("symbol must be SPY, got %r" % data02.get("symbol"))
    if data02.get("resolution") not in ("Daily", "Day"):
        reasons.append("resolution must be Daily, got %r" % data02.get("resolution"))
    if data02.get("fast_period") != 5:
        reasons.append("fast_period must be 5, got %r" % data02.get("fast_period"))
    if data02.get("slow_period") != 160:
        reasons.append("slow_period must be 160, got %r" % data02.get("slow_period"))
    if data02.get("start_date") != "2025-01-01":
        reasons.append("start_date must be 2025-01-01, got %r" % data02.get("start_date"))
    if data02.get("end_date") != "2025-12-31":
        reasons.append("end_date must be 2025-12-31, got %r" % data02.get("end_date"))
    if not isinstance(data02.get("backtest_id"), str) or not data02["backtest_id"]:
        reasons.append("backtest_id must be a non-empty string")
    if not isinstance(data01.get("project_id"), int):
        reasons.append("qc_results_01.json project_id must be an integer")
    if not isinstance(data02.get("project_id"), int):
        reasons.append("qc_results_02.json project_id must be an integer")
    if not isinstance(data01.get("defects_found"), list) or not data01["defects_found"]:
        reasons.append("defects_found must be a non-empty list")

    if isinstance(data01.get("project_id"), int) and isinstance(data02.get("project_id"), int) \
            and data01["project_id"] != data02["project_id"]:
        reasons.append("project_id differs between qc_results_01.json and qc_results_02.json")
    return reasons


def defect_reasons(source):
    """The three defects the task is about, checked on the live source.

    Deliberately narrow: each one names a deviation the specification states outright, so a
    passing algorithm cannot carry it. Style is left to the maintainability index.
    """
    reasons = []
    if "QQQ" in source or "SPY" not in source:
        reasons.append("live main.py does not trade SPY")
    if re.search(r"Resolution\s*\.\s*HOUR", source, re.I) or \
            re.search(r"Resolution\s*\.\s*MINUTE", source, re.I):
        reasons.append("live main.py still feeds an indicator a non-daily resolution")
    if re.search(r"\.current\.value\s*==", source) or re.search(r"==\s*self\._?slow", source):
        reasons.append("entry still tests equality instead of comparing the two EMAs")
    if not re.search(r"[<>]", source):
        reasons.append("live main.py contains no comparison at all")
    return reasons


def gate_reasons(data02, py_files, main_source):
    """(a) compile clean, (b) the backtest produced results, (c) main.py only, (d) defects gone."""
    reasons = []
    if data02.get("compile_success") is not True:
        reasons.append("compile_success is not true -- project did not compile cleanly")
    if not isinstance(data02.get("statistics"), dict) or not data02["statistics"]:
        reasons.append("statistics must be a non-empty object -- no backtest results recorded")
    if not isinstance(data02.get("orders_count"), int) or data02.get("orders_count", 0) < 1:
        reasons.append("orders_count must be an integer >= 1 -- backtest produced no trades")
    if py_files is not None:
        names = sorted(f.get("name", "") for f in py_files if f.get("name", "").endswith(".py"))
        if names != ["main.py"]:
            reasons.append("project must contain exactly one Python file, main.py; found %s" %
                           (names or "none"))
    if main_source:
        reasons.extend(defect_reasons(main_source))
    return reasons


def write_fail(target, reasons):
    target.write_text("passed=0\ntotal=1\nscore=0.0000\n"
                      "passed_holdout=\ntotal_holdout=\nscore_holdout=\n"
                      "reasons=%s\n" % "; ".join(reasons), encoding="utf-8")


def write_zero_metrics(path):
    """Always leave metrics behind, even on an early exit: the results table reads this file."""
    path.write_text("mi=0.0\nmi_ref=%s\nparsimony_factor=%s\nsloc=0\n"
                    % (MI_REF, parsimony_factor(0.0, MI_REF)), encoding="utf-8")


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) < 3:
        sys.stderr.write("usage: run_verification.py <workspace> <run dir> "
                         "[baseline|\"\"] [holdout dir] [template dir]\n")
        return 2
    workspace = Path(argv[1]).resolve()
    run_dir = Path(argv[2]).resolve()
    baseline = len(argv) > 3 and argv[3] == "baseline"
    if not read_reference_metrics():
        sys.stderr.write("environment error: reference/metrics.txt missing or has no mi=\n")
        return 2
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write("could not create run dir: %s\n" % exc)
        return 2

    target = run_dir / ("verification_baseline.txt" if baseline else "verification.txt")
    metrics_path = run_dir / ("metrics_baseline.txt" if baseline else "metrics.txt")

    data01, err01 = load_json(workspace / "qc_results_01.json")
    data02, err02 = load_json(workspace / "qc_results_02.json")
    if err01 or err02:
        write_fail(target, [e for e in (err01, err02) if e])
        write_zero_metrics(metrics_path)
        return 1

    reasons = validate_fields(data01, data02)
    if reasons:
        write_fail(target, reasons)
        write_zero_metrics(metrics_path)
        return 1

    if qc_auth_headers() is None:
        sys.stderr.write("environment error: QUANTCONNECT_USER_ID/QUANTCONNECT_API_TOKEN not "
                         "set\n")
        return 2

    project_id = data01["project_id"]
    py_files = fetch_project_files(project_id)

    main_source = None
    extra = []
    if py_files is None:
        extra.append("could not read files back from QuantConnect for project_id %s "
                     "(project does not exist or credentials are invalid)" % project_id)
    else:
        for f in py_files:
            if f.get("name") == "main.py":
                main_source = f.get("content")
                break
        if main_source is None:
            extra.append("no main.py in QuantConnect project %s" % project_id)

    reasons = gate_reasons(data02, py_files, main_source) + extra
    gate_passed = not reasons

    if main_source is None:
        mi = 0.0
        write_zero_metrics(metrics_path)
    else:
        scratch = run_dir / ("qc_source_baseline" if baseline else "qc_source")
        scratch.mkdir(parents=True, exist_ok=True)
        (scratch / "main.py").write_text(main_source, encoding="utf-8")
        m = code_metrics(scratch)
        mi = m["mi"]
        m["mi_ref"] = MI_REF
        m["parsimony_factor"] = round(parsimony_factor(mi, MI_REF), 3)
        metrics_path.write_text("".join("%s=%s\n" % (k, m[k]) for k in sorted(m)),
                                encoding="utf-8")

    factor = parsimony_factor(mi, MI_REF) if gate_passed else 0.0
    score = (1.0 if gate_passed else 0.0) * factor
    lines = ["passed=%s\n" % (1 if gate_passed else 0), "total=1\n", "score=%.4f\n" % score,
             "passed_holdout=\ntotal_holdout=\nscore_holdout=\n"]
    if reasons:
        lines.append("reasons=%s\n" % "; ".join(reasons))
    target.write_text("".join(lines), encoding="utf-8")
    return 0 if gate_passed else 1


if __name__ == "__main__":
    sys.exit(main())
