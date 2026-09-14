"""Print the (project, methodology) cells a given CAMPAIGN does not yet have a row for.

`--min-rows` counts rows over every campaign, which is what levelling a table wants and exactly
what a per-engine sweep does not: p06_qc_ema_cross/m00_empty already has an opus row, so --min-rows
would skip it for sonnet too and the sonnet panel would keep its hole. This asks the narrower
question the published table can actually answer -- does THIS campaign hold a row for this pair --
and prints one `project methodology` line per gap, for a batch to loop over.

    py -3 lib/missing_cells.py --campaign .llm_config.e13_claude_sonnet_5_medium \\
        --projects p06_qc_ema_cross,p07_qc_bugfix_refactor --methodologies 00,34,47

Methodologies may be given as numbers, as a prefix (`m34`) or in full; each is resolved against the
directories under methodology/ so a list written from the chart's two-digit labels keeps working
after a directory is renamed, and a name that matches nothing is reported rather than silently
dropped -- a typo that quietly shortens a sweep is the expensive kind.
"""
import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = os.path.join(ROOT, "results_repository.csv")


def resolve(token, available):
    """`34`, `m34` or a full name -> the one methodology directory it names, or None."""
    token = token.strip()
    if not token:
        return None
    if token in available:
        return token
    stem = token if token.startswith("m") else "m" + token.zfill(2)
    hits = [m for m in available if m == stem or m.startswith(stem + "_")]
    return hits[0] if len(hits) == 1 else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--campaign", required=True, help="cfg_campaign value, e.g. .llm_config.e13_...")
    ap.add_argument("--projects", required=True)
    ap.add_argument("--methodologies", required=True)
    args = ap.parse_args(argv)

    available = sorted(d for d in os.listdir(os.path.join(ROOT, "methodology"))
                       if os.path.isdir(os.path.join(ROOT, "methodology", d)))
    wanted, unknown = [], []
    for token in args.methodologies.split(","):
        name = resolve(token, available)
        if name is None:
            if token.strip():
                unknown.append(token.strip())
        elif name not in wanted:
            wanted.append(name)
    if unknown:
        sys.stderr.write("unknown methodolog(ies): %s\n" % ", ".join(unknown))
        return 4

    have = set()
    if os.path.isfile(TABLE):
        with open(TABLE, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if (r.get("cfg_campaign") or "").strip() == args.campaign:
                    have.add(((r.get("prj_name") or "").strip(),
                              (r.get("mth_name") or "").strip()))

    for project in [p.strip() for p in args.projects.split(",") if p.strip()]:
        for name in wanted:
            if (project, name) not in have:
                print("%s %s" % (project, name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
