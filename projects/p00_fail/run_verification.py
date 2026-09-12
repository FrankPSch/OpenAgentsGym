#!/usr/bin/env python3
"""Project oracle -- thin wrapper over lib/oracle.py (oam_targetpicture.md chapter 11)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from oracle import main  # noqa: E402

SIZE_REF = 4                        # SLOC of a known-good solution; recorded, not scored
MI_REF = 77.3                     # Maintainability Index of that solution; scores parsimony
REQUIRE_SMALLER_THAN_BASELINE = False
EXPECTS_TESTS = True

if __name__ == "__main__":
    sys.exit(main(size_ref=SIZE_REF, mi_ref=MI_REF,
                  require_smaller_than_baseline=REQUIRE_SMALLER_THAN_BASELINE,
                  expects_tests=EXPECTS_TESTS))
