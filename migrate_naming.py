"""One-time migration to the p##/m##/e## naming standard. See NAMING.md.

    py -3 migrate_naming.py --dry-run     # report, change nothing
    py -3 migrate_naming.py --apply       # rename and rewrite

Kept in the repository after the fact as the evidence for a commit that
rewrites recorded history: the rows in results_repository.csv and the run
directories they point at were renamed by this script and by nothing else.
It is idempotent - a second run reports nothing and changes nothing.

Method, and why it is one pass:

  Every old name goes into ONE alternation, longest first, applied with a
  single re.sub per file. A left-to-right single pass cannot rescan its own
  output, which is what makes the tricky cases fall out for free:

    "00_empty_01_python_small"  -> "m00_empty_p01_python_small"
        (run directory names are concatenations; each half matches once)
    "run_all_model_03.bat"      -> "run_all_e03.bat"
        (the whole filename is in the alternation and is longer than
         "model_03", so longest-first wins and the engine token never fires)

Three things had to be learned the hard way, each of them a re-run hazard.
They are described at the function that fixes them: build_maps reads BARE
names, replacer refuses a match preceded by a letter, and SELF_EXCLUDE keeps
the script from rewriting its own map.
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
    # 2026-09-14, a second rename on the same number: the name carried the
    # upstream repository and issue but not the task class, and the SWE-bench
    # instances are a class that will grow. The 09-12 entry above stays as it
    # was written - this file is the evidence for what was renamed when, so a
    # mapping is appended, never rewritten. Applied when no row and no run
    # directory referenced the old name, so nothing recorded was rewritten.
    "p10_xarray_7233": "p10_python_swe_xarray_7233",
}

# 00_empty and 00_sabotage both claimed 00. A number that identifies two things
# identifies neither, so sabotage takes the next free number.
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

# These two files are ABOUT the old names and must keep them. This script holds
# every old name as a map key, and the first run duly rewrote its own keys to
# the new names - after which a second run believed projects/p00_fail still
# needed renaming to projects/p00_fail and git refused to move a directory into
# itself. NAMING.md documents the same mapping and would rot the same way.
SELF_EXCLUDE = {"migrate_naming.py", "NAMING.md"}


def build_maps():
    """Complete the methodology map from disk, reading BARE names.

    An entry already carrying its kind letter is stripped back before being
    mapped, so m00_empty yields 00_empty -> m00_empty and never
    m00_empty -> mm00_empty.

    The first version mapped whatever it found to "m" + itself; re-run over an
    already-migrated tree it renamed 18 run directories to
    run_mm00_empty_pp01_python_small_... Skipping already-prefixed entries was
    the second wrong answer: it dropped 00_empty from the map entirely, so a
    directory still called run_00_empty_01_python_small_... had its project
    half renamed and its methodology half left alone. Stripping to the bare
    name keeps the entry AND makes the map idempotent.
    """
    for name in sorted(os.listdir(os.path.join(ROOT, "methodology"))):
        bare = re.sub(r"^m+(?=\d\d_)", "", name)
        if bare not in METHODS:
            METHODS[bare] = "m" + bare
    renamed = dict(PROJECTS)
    renamed.update(METHODS)
    renamed.update(ENGINES)

    # Two keys may share a target legitimately when one is the target's own
    # bare form - the entry that makes a re-run a no-op. 00_sabotage and
    # 47_sabotage both point at m47_sabotage for that reason: the first is the
    # renumber, the second the identity. A real collision is two DIFFERENT
    # things claiming one name, so identities are excluded before checking.
    claims = {}
    for k, v in renamed.items():
        if v == v[0] + k:
            continue
        claims.setdefault(v, []).append(k)
    dupes = {v: ks for v, ks in claims.items() if len(ks) > 1}
    if dupes:
        sys.exit("collision in the map: %s" % dupes)
    return renamed


def replacer(renamed):
    """One alternation, longest first, so a longer name always wins.

    The lookbehind is what makes the rewrite idempotent: a bare old name
    preceded by a letter is already the NEW name, since p01_python_small
    contains 01_python_small and m00_empty contains 00_empty. Without it a
    second pass produced pp01_python_small. An old name in a real reference is
    never preceded by a letter - it follows a separator, a quote, or the start
    of a line - so nothing legitimate is missed.
    """
    keys = sorted(list(BATCHES) + list(renamed), key=len, reverse=True)
    table = dict(BATCHES)
    table.update(renamed)
    pat = re.compile("(?<![A-Za-z])(?:%s)" % "|".join(re.escape(k) for k in keys))
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
    if os.path.basename(path) in SELF_EXCLUDE:
        return False
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

    # 1. directories and config files, through git so history follows the file.
    #    Every move is guarded on its source still existing. Directories were
    #    not guarded at first, so a second run asked git to move
    #    projects/00_fail when only projects/p00_fail was left, and git read
    #    the surviving destination as a directory to move INTO.
    candidates = []
    for old, new in sorted(PROJECTS.items()):
        candidates.append(("projects/%s" % old, "projects/%s" % new))
    for old, new in sorted(METHODS.items()):
        candidates.append(("methodology/%s" % old, "methodology/%s" % new))
    for old, new in sorted(ENGINES.items()):
        candidates.append((".llm_config.%s" % old, ".llm_config.%s" % new))
    for old, new in sorted(BATCHES.items()):
        candidates.append((old, new))
    moves = [(o, n) for o, n in candidates
             if o != n and os.path.exists(os.path.join(ROOT, o))]

    print("== %d tracked renames ==" % len(moves))
    for old, new in moves:
        print("   %-52s -> %s" % (old, new))
        if apply:
            git("mv", old, new)

    # 2. file contents: every tracked text file, plus the untracked per-run
    #    results under local/ that the published table is consolidated from
    targets = [p for p in git("ls-files").split("\n") if p and is_text(p)]
    runs_dir = os.path.join(ROOT, "local", "runs")
    if os.path.isdir(runs_dir):
        for d in sorted(os.listdir(runs_dir)):
            f = os.path.join(runs_dir, d, "results_run.csv")
            if os.path.isfile(f):
                targets.append(os.path.relpath(f, ROOT).replace("\\", "/"))

    changed = []
    for rel in targets:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        raw = open(path, "rb").read()
        try:
            text, enc = raw.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            text, enc = raw.decode("cp1252"), "cp1252"
        new = sub(text)
        if new != text:
            changed.append(rel)
            if apply:
                open(path, "wb").write(new.encode(enc))
    print("\n== %d files rewritten ==" % len(changed))
    for rel in changed[:8]:
        print("   " + rel)
    if len(changed) > 8:
        print("   ... and %d more" % (len(changed) - 8))

    # 3. run directories, named <methodology>_<project>_<stamp>_r<nn>
    if os.path.isdir(runs_dir):
        dir_moves = [(d, sub(d)) for d in sorted(os.listdir(runs_dir))
                     if sub(d) != d]
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
