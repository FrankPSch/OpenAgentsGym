"""The visible suite: the Coarsen.construct tests, and nothing else.

Why a file in the repository root rather than a path into `xarray/tests/`: lib/oracle.py builds
its target list from the template's root-level `test_*.py` glob, so a suite that lives deeper in
the tree is never collected. Importing the class here puts it in this module's namespace, pytest
collects it from this file, and the tests themselves stay in the repository where they belong --
no change to the oracle, and no second copy of the tests to drift.

Narrow on purpose. Handing pytest the whole of `xarray/tests/test_coarsen.py` would put 197
unrelated cases in the denominator, roughly half of them skips, which the oracle counts as
passes: a run that fixed nothing would still score about 0.99. Three real cases and a floor of
0.67 is what makes the row readable.
"""
from xarray.tests.test_coarsen import TestCoarsenConstruct  # noqa: F401
