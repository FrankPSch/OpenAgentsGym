#!/usr/bin/env python3
"""Project oracle -- thin wrapper over lib/oracle.py (oam_targetpicture.md chapter 11)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from oracle import main  # noqa: E402

SIZE_REF = 4                        # SLOC the reference patch adds; recorded, not scored
MI_REF = None                       # parsimony OFF -- see note below
REQUIRE_SMALLER_THAN_BASELINE = False
EXPECTS_TESTS = True

# MI_REF is None deliberately, and this is the one line that differs in kind from the synthetic
# projects. code_metrics() walks every non-test .py in the workspace, which here is the whole
# xarray source tree: 119 files, 62k SLOC, measured MI 0.0. A reference MI would therefore put
# every run on the parsimony floor regardless of what it wrote, so the factor is switched off and
# the score is pure correctness. That is also the right semantics for a repository-level task --
# the run edits four lines inside a framework it did not write, and there is no parsimony claim
# to make about the other 62k.

if __name__ == "__main__":
    sys.exit(main(size_ref=SIZE_REF, mi_ref=MI_REF,
                  require_smaller_than_baseline=REQUIRE_SMALLER_THAN_BASELINE,
                  expects_tests=EXPECTS_TESTS))
