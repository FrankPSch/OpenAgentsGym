"""Judge the newest run of one campaign, and unload models between legs.

Two jobs, both learned from the 2026-09-11 matrix:

1) `unload <model>` — Ollama keeps a model resident for ~5 minutes after use, so
   a second leg starts while the first leg's weights are still held. Three legs
   back to back exhausted memory: gpt-oss-20b took 2.6x its solo time and made
   zero edits (CPU fallback), and the 30B then died with APIError. Unloading
   costs a reload per leg and removes the interference.

2) `verdict <campaign>` — run_master exits 0 for a run that reached a row, even
   when that row says APIError and scores 0.0000. That is correct for the
   harness (the run completed and was recorded) but useless as a batch signal.
   This reads the row and judges it:
       PASS   scored above zero, subtype success
       FAIL   subtype not success, or score 0, or nothing was edited

Usage:  py -3 _leg_verdict.py unload  litellm/qwen3-4b
        py -3 _leg_verdict.py verdict opencode_01
Exit 0 = PASS, 1 = FAIL, 2 = could not tell.
"""
import csv
import glob
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))


def _resident():
    try:
        return [m.get("name", "?") for m in json.load(urllib.request.urlopen(
            "http://127.0.0.1:11434/api/ps", timeout=20)).get("models", [])]
    except Exception:
        return []


def unload(_model=None):
    """Evict EVERY resident model, not just the one this leg will use.

    The first version guessed the leg's own tag and unloaded that - which is the
    model about to be loaded, while the PREVIOUS leg's weights stayed resident.
    The log said it plainly: "resident after unload: gpt-oss:20b" immediately
    before the qwen3-4b leg. Asking /api/ps what is actually loaded and evicting
    all of it removes the guesswork and the name-mangling between gateway names
    (gpt-oss-20b) and Ollama tags (gpt-oss:20b).

    keep_alive=0 on a zero-token generate request evicts on completion.
    """
    before = _resident()
    for tag in before:
        body = json.dumps({"model": tag, "keep_alive": 0}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate", data=body,
            headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=120).read()
        except Exception as exc:
            print("   (evicting %s failed: %s)" % (tag, exc))

    # Eviction is not instant; give the server a moment and re-ask.
    for _ in range(10):
        after = _resident()
        if not after:
            break
        time.sleep(2)
    after = _resident()
    print("   resident before=%s after=%s"
          % (", ".join(before) or "none", ", ".join(after) or "none"))
    if after:
        print("   WARNING: models still resident - the next leg starts with"
              " less memory than it needs")
    return 0


def newest_row(campaign):
    """The most recent results_run.csv written under this campaign label."""
    best = None
    for path in glob.glob(os.path.join(ROOT, "local", "runs", "*", "results_run.csv")):
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                row = next(iter(csv.DictReader(fh)), None)
        except Exception:
            continue
        if not row:
            continue
        if row.get("cfg_campaign", "").replace(".llm_config.", "") != campaign:
            continue
        stamp = row.get("id_timestamp", "")
        if best is None or stamp > best[0]:
            best = (stamp, row)
    return best[1] if best else None


def verdict(campaign):
    row = newest_row(campaign)
    if row is None:
        print("   VERDICT: UNKNOWN - no row found for %s" % campaign)
        return 2

    subtype = (row.get("res_subtype") or "").strip()
    try:
        score = float(row.get("res_score") or 0)
    except ValueError:
        score = 0.0
    try:
        diff = int(row.get("res_diff_lines") or 0)
    except ValueError:
        diff = 0
    passed = (row.get("res_verification_passed") or "").strip().lower() == "true"
    secs = row.get("prf_duration_s") or "?"
    turns = row.get("prf_turns") or "?"

    problems = []
    if subtype != "success":
        problems.append("subtype=%s" % (subtype or "empty"))
    if score <= 0:
        problems.append("score=%.4f" % score)
    if diff == 0:
        problems.append("no edit (diff_lines=0)")
    if not passed:
        problems.append("tests did not pass")

    print("   score=%.4f turns=%s sec=%s subtype=%s diff=%s"
          % (score, turns, secs, subtype or "-", diff))
    if problems:
        print("   VERDICT: FAIL - %s" % "; ".join(problems))
        return 1
    print("   VERDICT: PASS")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "unload":
        sys.exit(unload(arg))
    if cmd == "verdict":
        sys.exit(verdict(arg))
    print("unknown command %r" % cmd)
    sys.exit(2)
