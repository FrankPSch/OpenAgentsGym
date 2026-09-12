"""One-time migration to the p##/m##/e## naming standard. See NAMING.md.

Run once:  py -3 migrate_naming.py --dry-run     # report, change nothing
           py -3 migrate_naming.py --apply       # rename and rewrite

It is kept in the repository after the fact as the evidence for a commit that
rewrites recorded history: the 112 rows in results_repository.csv and the run
directories they point at were renamed by this script and by nothing else.

Method, and why it is one pass:

  Every old name is put into ONE alternation, longest first, and applied with a
  single re.sub per file. A left-to-right single pass cannot rescan its own
  output, which is what makes the tricky cases fall out for free:

    "00_empty_01_python_small"  -> "m00_empty_p01_python_small"
        (run directory names are just concatenations; each part matches once)
    "m00_empty"                 stays "m00_empty"
        (a second pass would have made it "mm00_empty")
    "run_all_model_03.bat"      -> "run_all_e03.bat"
        (the whole filename is in the alternation and is longer than
         "model_03", so longest-first wins and the engine token never fires)
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# --- the standard -----------------------------------------------------------
# <kind><nn>_<words>, lowercase [a-z0-9_] only, nn two digits, numbers permanent.

PROJECTS = {
    "00_fail": "p00_fail",
    "01_python_small": "p01_python_small",
    "02_python_medium": "p02_python_medium",
    "03_python_large": "p03_python_large",
    "04_python_xlarge": "p04_python_xlarge",
    "05_python_refactor_large": "p05_python_refactor_large",
    "06_qc_ema_cross": "p06_qc_ema_cross",
    "07_qc_bugfix_refactor": "p07_qc_bugfix_refactor",
    "10_xarray_7233": "p10_xarray_7233",
}

# 00_empty and 00_sabotage both claimed 00. A number that identifies two things
# defeats the purpose, so sabotage takes the next free number.
METHODS = {"00_sabotage": "m47_sabotage"}

# The family token is the ENGINE as the registry knows it: claude, gpt, and
# local (= the opencode CLI against LiteLLM). e09/e10 are retired - the claude
# CLI pointed at local models, reversed on 2026-09-11 - and have no config
# file, but they name rows that exist, so they get numbers like anything else.
ENGINES = {
    "model_01": "e01_claude_haiku_4_5",
    "model_02": "e02_claude_sonnet_5",
    "model_03": "e03_claude_opus_5",
    "model_04": "e04_claude_fable_5_1",
    "gpt_02": "e05_gpt_5_codex",
    "opencode_01": "e06_local_gptoss_20b",
    "opencode_02": "e07_local_qwen3_4b",
    "opencode_03": "e08_local_qwen3coder_30b",
    "local_05": "e09_claude_gptoss_20b",
    "local_07": "e10_claude_qwen3_4b",
}

# Batch filenames carry an engine in their own name. Renaming the engine but
# not the file is exactly the drift this standard removes.
BATCHES = {
    "run_all_model_03.bat": "run_all_e03.bat",
    "run_all_model_04.bat": "run_all_e04.bat",
    "run_screen_model_03.bat": "run_screen_e03.bat",
    "run_selected_model_04.bat": "run_selected_e04.bat",
    "run_smoke_model_02.bat": "run_smoke_e02.bat",
    "run_turbo_model_01.bat": "run_turbo_e01.bat",
}
for _old, _new in PROJECTS.items():
    BATCHES["run_engine_matrix.project_%s.bat" % _old.split("_")[0]] = (
        "run_engine_matrix.%s.bat" % _new.split("_")[0])


def build_maps():
    """Complete the methodology map from what is on disk, idempotently.

    The first version read the directory and mapped every entry to "m" + entry.
    Re-run after a partial migration that had already renamed the directories,
    it happily produced m00_empty -> mm00_empty and renamed 18 run directories
    to run_mm00_empty_pp01_python_small_... Anything already carrying its kind
    letter is therefore skipped, so a second run is a no-op.
    """
    for name in sorted(os.listdir(os.path.join(ROOT, "methodology"))):
        if re.match(r"^m\d\d_", name):
            continue
        if name not in METHODS:
            METHODS[name] = "m" + name
    renamed = dict(PROJECTS)
    renamed.update(METHODS)
    renamed.update(ENGINES)
    dupes = [v for v in set(renamed.values()) if list(renamed.values()).count(v) > 1]
    if dupes:
        sys.exit("collision in the map: %s" % dupes)
    return renamed


def replacer(renamed):
    """One alternation, longest first, so a longer name always wins."""
    keys = sorted(list(BATCHES) + list(renamed), key=len, reverse=True)
    table = dict(BATCHES)
    table.update(renamed)
    pat = re.compile("|".join(re.escape(k) for k in keys))
    return lambda text: pat.sub(lambda m: table[m.group(0)], text)


def git(*args):
    out = subprocess.run(["git"] + list(args), cwd=ROOT,
                         capture_output=True, text=True)
    if out.returncode:
        sys.exit("git %s failed: %s" % (" ".join(args), out.stderr.strip()))
    return out.stdout


TEXT_SUFFIXES = (".py", ".bat", ".md", ".csv", ".yaml", ".yml", ".json",
                 ".svg", ".txt", ".cfg", ".toml", ".gitignore")


def is_text(path):
    return path.endswith(TEXT_SUFFIXES) or os.path.basename(path).startswith(".llm_config.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.apply == args.dry_run:
        sys.exit("choose exactly one of --apply / --dry-run")
    apply = args.apply

    renamed = build_maps()
    sub = replacer(renamed)

    # 1. directories and config files, through git so history follows the file
    moves = []
    for old, new in sorted(PROJECTS.items()):
        moves.append(("projects/%s" % old, "projects/%s" % new))
    for old, new in sorted(METHODS.items()):
        moves.append(("methodology/%s" % old, "methodology/%s" % new))
    for old, new in sorted(ENGINES.items()):
        src = ".llm_config.%s" % old
        if os.path.exists(os.path.join(ROOT, src)):
            moves.append((src, ".llm_config.%s" % new))
    for old, new in sorted(BATCHES.items()):
        if os.path.exists(os.path.join(ROOT, old)):
            moves.append((old, new))

    print("== %d tracked renames ==" % len(moves))
    for old, new in moves:
        print("   %-52s -> %s" % (old, new))
        if apply:
            git("mv", old, new)

    # 2. file contents: every tracked text file, plus the untracked results
    #    under local/ that the published table is consolidated from
    targets = [p for p in git("ls-files").split("\n") if p and is_text(p)]
    runs_dir = os.path.join(ROOT, "local", "runs")
    run_rows = []
    if os.path.isdir(runs_dir):
        for d in sorted(os.listdir(runs_dir)):
            f = os.path.join(runs_dir, d, "results_run.csv")
            if os.path.isfile(f):
                run_rows.append(os.path.relpath(f, ROOT).replace("\\", "/"))
    targets += run_rows

    changed = 0
    hits = 0
    for rel in targets:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        raw = open(path, "rb").read()
        try:
            text = raw.decode("utf-8")
            enc = "utf-8"
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
            enc = "cp1252"
        new = sub(text)
        if new != text:
            changed += 1
            hits += sum(1 for _ in re.finditer("|".join(
                re.escape(v) for v in sorted(set(list(BATCHES.values()) +
                list(renamed.values())), key=len, reverse=True)), new))
            if apply:
                open(path, "wb").write(new.encode(enc))
    print("\n== %d files rewritten ==" % changed)

    # 3. run directories, named <methodology>_<project>_<stamp>_r01
    if os.path.isdir(runs_dir):
        dir_moves = []
        for d in sorted(os.listdir(runs_dir)):
            nd = sub(d)
            if nd != d:
                dir_moves.append((d, nd))
        print("== %d run directories renamed ==" % len(dir_moves))
        for old, new in dir_moves[:3]:
            print("   %s -> %s" % (old, new))
        if len(dir_moves) > 3:
            print("   ... and %d more" % (len(dir_moves) - 3))
        if apply:
            for old, new in dir_moves:
                os.rename(os.path.join(runs_dir, old), os.path.join(runs_dir, new))

    if not apply:
        print("\nDRY RUN - nothing was changed. Re-run with --apply.")


if __name__ == "__main__":
    main()
