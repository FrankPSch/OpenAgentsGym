"""Print the arms that lead the combined panel of one or more projects, as a comma list.

The chart's combined panel ranks a project's rows by `sc_overall_ratio`; this prints the arm names
behind that ranking so a batch can run the same arms somewhere else. Reading them off the table
rather than pasting them into a batch file is the whole point: the leaders move as rows arrive, and
a hard-coded list would quietly go on running last month's answer.

    py -3 lib/top_arms.py --projects p04_python_xlarge,p05_python_refactor_large --top 10

One line, comma-separated, ready for `--methodologies`. The union is ordered by each arm's BEST
rank across the projects asked for, so an arm leading one list comes before one that placed tenth
on both; ties fall back to the name, which keeps the output identical on every run of the same
rows. `--per-project` prints one line per project instead, for a reader rather than a batch.
"""
import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = os.path.join(ROOT, "results_repository.csv")


def leaders(rows, project, top):
    """The `top` best-scoring arm names of one project, best first, one entry per arm.

    Per ARM and not per row: a project with repeats holds several rows of one arm, and a list that
    named it three times would spend three runs re-running one arm. An arm is taken at its best
    row, which is the same number the chart's list shows at rank 1 for that arm.
    """
    best = {}
    for r in rows:
        if r.get("prj_name") != project:
            continue
        try:
            ratio = float(r["sc_overall_ratio"])
        except (KeyError, TypeError, ValueError):
            continue
        name = (r.get("mth_name") or "").strip()
        if name and ratio > best.get(name, float("-inf")):
            best[name] = ratio
    return [n for n, _ in sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))][:top]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--projects", required=True,
                    help="comma-separated project names to take the leaders of")
    ap.add_argument("--top", type=int, default=10, help="how many per project (default 10)")
    ap.add_argument("--per-project", action="store_true",
                    help="print one labelled line per project instead of the union")
    args = ap.parse_args(argv)

    if not os.path.isfile(TABLE):
        sys.stderr.write("%s not found -- run --consolidate first\n" % TABLE)
        return 2
    with open(TABLE, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    projects = [p.strip() for p in args.projects.split(",") if p.strip()]
    rank = {}
    for project in projects:
        names = leaders(rows, project, args.top)
        if args.per_project:
            print("%s: %s" % (project, ",".join(names) or "(no scored row)"))
        for i, name in enumerate(names):
            rank[name] = min(rank.get(name, 10 ** 6), i)
    if not args.per_project:
        print(",".join(sorted(rank, key=lambda n: (rank[n], n))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
