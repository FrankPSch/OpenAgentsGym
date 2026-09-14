"""Print the sabotage and incumbent rows of p04 under e13, and say whether their ranges overlap.

Called at the end of 04_run_noise_floor_p04_e13.bat. Reads the published table and nothing else,
and states the verdict the batch was run to get rather than leaving it to be eyeballed.
"""
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRJ = "p04_python_xlarge"
CAMP = "e13_claude_sonnet_5_medium"
ARMS = ("m47_sabotage", "m29_invariants_test_first_relative_stop")


def main():
    with open(os.path.join(ROOT, "results_repository.csv"), encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    got = {}
    for r in rows:
        if r.get("prj_name") != PRJ or CAMP not in (r.get("cfg_campaign") or ""):
            continue
        if r.get("mth_name") not in ARMS:
            continue
        try:
            score = float(r["res_score"])
        except (KeyError, TypeError, ValueError):
            continue
        got.setdefault(r["mth_name"], []).append((score, r.get("prf_duration_s", ""),
                                                  r.get("tk_cost_usd", "")))
    for arm in ARMS:
        runs = sorted(got.get(arm, []))
        if not runs:
            print("  %-45s no rows" % arm)
            continue
        scores = [s for s, _, _ in runs]
        print("  %-45s n=%d  %.4f - %.4f  median %.4f" % (
            arm, len(scores), scores[0], scores[-1], scores[len(scores) // 2]))
        for s, dur, usd in runs:
            print("      %.4f  %ss  $%s" % (s, dur, usd))
    a, b = [sorted(s for s, _, _ in got.get(arm, [])) for arm in ARMS]
    if len(a) < 2 or len(b) < 2:
        print("\n  fewer than two runs of an arm: no range to compare yet")
        return 0
    # Ranges, not means: with three runs a range is the honest statement of what was seen, and
    # the question is whether the two arms are separable at all, not by how much.
    overlap = not (a[-1] < b[0] or b[-1] < a[0])
    print("\n  sabotage %.4f-%.4f vs incumbent %.4f-%.4f" % (a[0], a[-1], b[0], b[-1]))
    if overlap:
        print("  RANGES OVERLAP -- this engine does not separate these two arms on this project.")
        print("  The e13 ordering of p04 is not a ranking; read those rows for cost and timing.")
    else:
        print("  ranges are disjoint -- the arms are separable here, and the gap between them")
        print("  is the smallest difference this engine can resolve on this project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
