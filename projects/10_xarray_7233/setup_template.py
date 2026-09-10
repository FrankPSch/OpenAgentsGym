#!/usr/bin/env python3
"""Materialise project_reset_template/ for this project. Run once, before the first run.

The template is a checkout of pydata/xarray at the commit the upstream fix was written against,
plus the fix's test changes, plus the three files in template_overlay/. It is ~2000 files and is
not committed: the repository holds this script and the overlay, the checkout is machine-local
and .gitignore'd, and both are reproducible from BASE_COMMIT and TEST_COMMIT below.

    py -3 projects/10_xarray_7233/setup_template.py [--force]

Needs `git` on PATH and network access to github.com. Takes about a minute; a blobless clone is
cached in local/_upstream/ so a second project on the same repository does not clone again.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/pydata/xarray.git"
# The commit the pull request was based on: the tree the run starts from, bug present.
BASE_COMMIT = "51d37d1be95547059251076b3fadaa317750aab3"
# The merge of pydata/xarray#7233 ("Ensure Coarsen.construct keeps all coords"). Its version of
# the test file is the suite; its version of xarray/core/rolling.py is the reference solution and
# is deliberately NOT copied into the template.
TEST_COMMIT = "e1936a98059ae29da2861f58a7aff4a56302aac1"
TEST_FILE = "xarray/tests/test_coarsen.py"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / "local" / "_upstream" / "xarray.git"
TEMPLATE = HERE / "project_reset_template"
OVERLAY = HERE / "template_overlay"


def run(args, **kw):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)
    if p.returncode:
        sys.stderr.write("FAILED: %s\n%s\n" % (" ".join(map(str, args)), p.stdout))
        raise SystemExit(1)
    return p.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="replace an existing template")
    args = ap.parse_args()

    if TEMPLATE.exists():
        if not args.force:
            print("template already present at %s (use --force to rebuild)" % TEMPLATE)
            return 0
        shutil.rmtree(TEMPLATE)

    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        print("cloning %s (blobless) ..." % REPO_URL)
        run(["git", "clone", "--bare", "--filter=blob:none", REPO_URL, str(CACHE)])
    else:
        run(["git", "--git-dir", str(CACHE), "fetch", "--quiet", "origin"])

    TEMPLATE.mkdir(parents=True)
    print("exporting %s ..." % BASE_COMMIT[:12])
    tar = subprocess.run(["git", "--git-dir", str(CACHE), "archive", BASE_COMMIT],
                         stdout=subprocess.PIPE, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(TEMPLATE)], input=tar, check=True)

    # The suite as the fix left it. Written straight from the commit rather than applied as a
    # patch: the upstream change also reorganised the surrounding tests, and a three-way apply
    # against the base tree would be a second thing that can fail for reasons of its own.
    print("writing %s from %s ..." % (TEST_FILE, TEST_COMMIT[:12]))
    blob = subprocess.run(["git", "--git-dir", str(CACHE), "show",
                           "%s:%s" % (TEST_COMMIT, TEST_FILE)],
                          stdout=subprocess.PIPE, check=True).stdout
    (TEMPLATE / TEST_FILE).write_bytes(blob)

    for src in sorted(OVERLAY.iterdir()):
        shutil.copy2(src, TEMPLATE / src.name)
        print("overlay: %s" % src.name)

    print("\ntemplate ready: %s" % TEMPLATE)
    print("baseline expected: 1 failed, 2 passed  (score 0.6667)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
