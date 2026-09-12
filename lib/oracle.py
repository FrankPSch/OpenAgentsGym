"""Shared project oracle -- oam_targetpicture.md chapter 11.

One implementation for every project. A project's run_verification.py is a thin wrapper that
supplies its own reference constants and any extra gate:

    import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
    from oracle import main
    sys.exit(main(size_ref=82, mi_ref=31.7))

Contract: run_verification.py <workspace> <run dir> [baseline|""] [holdout dir] [template dir]
Exit 0 = pass (tests green plus any project gate), 1 = fail, 2 = environment or setup error.
A pytest collection error caused by the agent's own code is a fail, not an environment error: it
is scored from the junit.xml pytest wrote and exits 1 (see run_pytest). So is an emptied source
tree, and so is a suite that outruns VERIFY_TIMEOUT_S -- the latter writes `timeout=1` beside the
zero score. Only pytest itself being unrunnable is exit 2.

The scored tree is made immune to workspace configuration first: pytest runs against an empty ini
of the oracle's own with `-o addopts=`, and any pytest config or hook file the template does not
ship is deleted and reported as `config_tampered=1` (chapter 11).

The fourth argument is the run's copy of the project's held-out suite (chapter 11). It is scored
separately and gates nothing: the exit code and `score` are the visible suite's, exactly as before.

The fifth is the project_reset_template. Its `test_*.py` and `conftest.py` are the only workspace
files handed to pytest, so a test file the agent wrote is never collected and a methodology cannot
grade its own homework. Omitted, the workspace's own root glob is used -- the standalone shape,
which only the pristine template can reach.

Score: (passed / total) * parsimony factor, where
    factor = clamp(mi / mi_ref, PARSIMONY_FLOOR, 1.0)
Matching or beating the reference solution's Maintainability Index scores 1.0; bulkier or more
convoluted code scores proportionally less, floored so parsimony can never outweigh correctness.
The factor applies to the post-run score only, never to the baseline.

`size_ref` is a per-project constant every wrapper declares (chapter 11 records the table); it is
recorded there, never scored, and the oracle does not write it.
"""
import ast
import builtins
import math
import os
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PARSIMONY_FLOOR = 0.8
# Wall-clock bound on the pytest invocation (chapter 11). An infinite loop in generated code is a
# statement about that code, not about the machine, so it is bounded instead of stalling a worker
# forever; the run scores 0.00 and exits 1. run_master applies a second, wider guard of its own.
VERIFY_TIMEOUT_S = 300
# What run_pytest returns when that bound is reached -- distinct from None, which is the environment.
TIMEOUT = "timeout"
# Files pytest reads as configuration. One the template does not ship is the agent's, and an added
# `pytest.ini` carrying `addopts = -k test_origin` deselects every test that contradicts the code:
# p00_fail scored 1.00 that way. They are removed before scoring and counted as tampering.
PYTEST_CONFIG_NAMES = ("pytest.ini", ".pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml")

DECISION = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp,
            ast.comprehension, ast.Assert)


SKIP_DIRS = {".venv", "__pycache__", ".git", ".pytest_cache", "build", "dist"}


def source_files(workspace):
    """Every non-test .py under the project_workspace, packages included."""
    out = []
    for path in sorted(workspace.rglob("*.py")):
        if path.name.startswith("test_") or path.name.endswith("_test.py"):
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(workspace).parts):
            continue
        out.append(path)
    return out


def complexity_of(path):
    """Cyclomatic complexity, standard decision-point count: decision points + 1 per callable."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return -1
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            m = 1
            for sub in ast.walk(node):
                if isinstance(sub, DECISION):
                    m += 1
                elif isinstance(sub, ast.BoolOp):
                    m += len(sub.values) - 1
            total += m
    return total


# --- code metrics (oam_targetpicture.md chapter 11) ------------------------------
# All standard measures, computed from the AST with the standard library only.
#   SLOC             non-blank, non-comment lines, docstring lines included
#   chars            total characters of non-test source
#   complexity       cyclomatic, decision points + 1 per callable (McCabe)
#   mi               Maintainability Index, SEI normalised variant:
#                    max(0, (171 - 5.2 ln V - 0.23 G - 16.2 ln LOC) * 100 / 171)
#                    over Halstead volume V = N * log2(n), which is an intermediate of MI and is
#                    not itself recorded
#   max_func_sloc    longest callable, in SLOC
#   max_nesting      deepest nesting of blocks
#   lint_errors      unused imports, bare except, shadowed builtins, unused locals
#   docstring_cov    share of module and public callables carrying a docstring, 0-100
#   comment_density  comment lines / SLOC, 0-100

OPERATOR_NODES = (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Assign, ast.AugAssign,
                  ast.Call, ast.Subscript, ast.Attribute, ast.Return, ast.If, ast.For, ast.While,
                  ast.With, ast.Raise, ast.Try, ast.Import, ast.ImportFrom, ast.Lambda)
BLOCK_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try,
               ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
BUILTIN_NAMES = set(dir(__builtins__)) if isinstance(__builtins__, type(ast)) else set(dir(builtins))


def _halstead(tree):
    ops, opnds, n_ops, n_opnds = set(), set(), 0, 0
    for node in ast.walk(tree):
        if isinstance(node, OPERATOR_NODES):
            ops.add(type(node).__name__); n_ops += 1
        if isinstance(node, ast.Name):
            opnds.add(node.id); n_opnds += 1
        elif isinstance(node, ast.Constant):
            opnds.add(repr(node.value)); n_opnds += 1
    n, N = len(ops) + len(opnds), n_ops + n_opnds
    return (N * math.log(n, 2)) if n > 1 and N else 0.0


def _nesting(node, depth=0):
    best = depth
    for child in ast.iter_child_nodes(node):
        d = depth + 1 if isinstance(child, BLOCK_NODES) else depth
        best = max(best, _nesting(child, d))
    return best


def _func_sloc(node, lines):
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno)
    return sum(1 for l in lines[start:end] if l.strip() and not l.strip().startswith("#"))


def _lint(tree, lines):
    errors = 0
    imported, used = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                imported.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            pass
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            errors += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and \
                node.name in BUILTIN_NAMES:
            errors += 1
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and \
                node.id in BUILTIN_NAMES:
            errors += 1
    errors += len(imported - used)
    return errors


def _docstring_cov(tree):
    total = 1
    have = 1 if ast.get_docstring(tree) else 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name.startswith("_"):
                continue
            total += 1
            if ast.get_docstring(node):
                have += 1
    return 100.0 * have / total if total else 0.0


def code_metrics(workspace):
    """Every metric over the non-test sources, as one flat dict."""
    out = {"sloc": 0, "chars": 0, "complexity": 0, "mi": 0.0,
           "max_func_sloc": 0, "max_nesting": 0, "lint_errors": 0,
           "docstring_cov": 0.0, "comment_density": 0.0}
    files = source_files(workspace)
    if not files:
        return out
    volume = 0.0
    docs, comments = [], 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        out["chars"] += len(text)
        out["sloc"] += sum(1 for l in lines if l.strip() and not l.strip().startswith("#"))
        comments += sum(1 for l in lines if l.strip().startswith("#"))
        out["complexity"] += max(0, complexity_of(path))
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        volume += _halstead(tree)
        out["max_nesting"] = max(out["max_nesting"], _nesting(tree))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out["max_func_sloc"] = max(out["max_func_sloc"], _func_sloc(node, lines))
        out["lint_errors"] += _lint(tree, lines)
        docs.append(_docstring_cov(tree))
    if out["sloc"]:
        out["comment_density"] = round(100.0 * comments / out["sloc"], 1)
    if docs:
        out["docstring_cov"] = round(sum(docs) / len(docs), 1)
    g, loc = out["complexity"], out["sloc"]
    if volume > 0 and loc > 0:
        mi = (171 - 5.2 * math.log(volume) - 0.23 * g - 16.2 * math.log(loc)) * 100.0 / 171.0
        out["mi"] = round(max(0.0, min(100.0, mi)), 1)
    return out


def parsimony_factor(mi, mi_ref):
    """Maintainability Index of the run against a known-good solution's MI.

    factor = clamp(mi / mi_ref, PARSIMONY_FLOOR, 1.0)

    MI already combines Halstead volume, cyclomatic complexity and size, so it supersedes the raw
    line count: a run that matches or beats the reference scores 1.0, and one that is bulkier or
    more convoluted scores proportionally less, bounded so it can never outweigh correctness.

    An MI of 0 is the worst measurable code, not the absence of a measurement, so it takes the
    floor: rewarding it with 1.0 gave an emptied or unparsable source tree the best factor there is.
    Only an unset MI_REF -- no reference to divide by -- leaves the factor at 1.0.
    """
    if not mi_ref:
        return 1.0
    return max(PARSIMONY_FLOOR, min(1.0, float(mi) / mi_ref))


def read_metric(path, key):
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return int(line.split("=", 1)[1])
    return None


def test_files(template):
    """The template's own test files: the root `test_*.py` glob plus `conftest.py`.

    This list -- never a directory -- is what pytest is pointed at, so a test file the agent added
    is not collected and an arm cannot raise its own score by writing passing tests. The glob is
    root-level only, exactly as the tamper set is (chapter 11).
    """
    names = sorted(p.name for p in template.glob("test_*.py"))
    if (template / "conftest.py").is_file():
        names.append("conftest.py")
    return names


def count_test_functions(workspace, targets):
    """How many `test_*` callables the suite defines -- the denominator when pytest collected none.

    Cheap and best-effort: a file that will not parse contributes nothing, which is the same answer
    pytest reached. It is only ever consulted when the junit carries no testcase at all, so a run
    that collected nothing still scores 0.00 instead of dropping out of the statistics.
    """
    total = 0
    for name in (targets or []):
        path = workspace / name
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                    node.name.startswith("test"):
                total += 1
    return total


def strip_pytest_config(workspace, template):
    """Delete every pytest configuration or hook file the template does not ship (chapter 11).

    Restoring the tamper set only puts back what the template contains, so a file the agent *added*
    survived it: a `pytest.ini` with `addopts = -k test_origin` deselected the contradictory tests
    and p00_fail scored 1.00. Anything pytest reads as configuration or as a hook -- a `conftest.py`
    at any depth, the ini/cfg/toml names -- is therefore removed before scoring and reported as
    tampering; the row is then scored on the cleaned tree, exactly as a restored one is.

    Returns the removed paths, relative and posix-style. Empty when the template is the workspace
    (the standalone shape), where every such file is the project's own.
    """
    removed = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name != "conftest.py" and path.name not in PYTEST_CONFIG_NAMES:
            continue
        if (template / rel).is_file():
            continue
        path.unlink()
        removed.append(rel.as_posix())
    return removed


def _kill_tree(proc):
    """Kill the timed-out pytest and everything it started.

    Killing the direct child alone leaves a subprocess it spawned holding the pipes, and the run
    hangs on the read instead of on the child. On Windows `taskkill /T /F` walks the tree; elsewhere
    the child was started in a session of its own, so one killpg reaches all of it.
    """
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def run_pytest(workspace, junit, holdout=None, targets=None):
    """Run the template's test files and, when there is one, the held-out suite in one invocation.

    Returns ((total, passed), (total_holdout, passed_holdout), collected_visible), None on an
    environment error, or TIMEOUT when the invocation outran VERIFY_TIMEOUT_S. The second pair is
    (0, 0) when no held-out suite was collected; `collected_visible` counts every visible test case
    the junit carries, skipped ones included, which is what the caller compares against the
    template's own test-function count.

    An environment error is "pytest could not run at all" and nothing else: pytest missing, a usage
    or internal error (exit 3, 4), or no junit.xml written. Whenever pytest wrote a junit.xml that
    parses, the run is scored from it whatever the exit code was -- a collection error caused by the
    agent's own code (a SyntaxError or a failed import in the workspace) exits 2 and still writes
    <error> entries, and that is a run that scores 0.00, not a broken machine. Classifying it as an
    environment error wrote no verification.txt at all, so the row carried a blank res_score and
    left the campaign statistics entirely (chapter 11).

    `targets` are the file names of the template's suite; pytest is given those paths under the
    workspace and nothing else, so nothing the agent wrote is collected. They are restored from the
    template before scoring (chapter 12, step 8), so what runs is the project's suite verbatim.

    cwd is the workspace, so `python -m pytest` puts it on sys.path and the held-out file's
    `import <module>` resolves exactly as the visible suite's does; --rootdir keeps the workspace
    the root although a second directory is collected. (Should a held-out import ever fail under
    the default prepend import mode, --import-mode=importlib is the fallback.) The junit XML is
    counted per test file, so the visible pair is the template suite alone.
    """
    if junit.exists():
        junit.unlink()
    files = [str(workspace / n) for n in (targets or []) if (workspace / n).is_file()]
    if not files:
        return None
    # pytest is run immune to whatever configuration the workspace holds: `-c <an empty ini the
    # oracle writes beside the junit>` makes that file the one and only inifile, so pytest.ini,
    # tox.ini, setup.cfg and pyproject.toml in the workspace are ignored, and `-o addopts=` clears
    # any addopts that reached it another way. Without this an added `addopts = -k ...` silently
    # deselected the failing tests (chapter 11).
    empty_ini = junit.parent / "pytest_empty.ini"
    empty_ini.parent.mkdir(parents=True, exist_ok=True)
    empty_ini.write_text("[pytest]\n", encoding="utf-8")
    argv = [sys.executable, "-m", "pytest", "-q", "-c", str(empty_ini), "-o", "addopts=",
            "-p", "no:cacheprovider",
            "--rootdir", str(workspace), "--junitxml", str(junit)] + files
    names = {p.name for p in holdout.glob("test_*.py")} if holdout else set()
    if names:
        argv.append(str(holdout))
    # Popen rather than subprocess.run, so the timeout can kill the whole tree: an infinite loop in
    # the code under test stalled a worker forever (chapter 11, VERIFY_TIMEOUT_S).
    kwargs = {} if os.name == "nt" else {"start_new_session": True}
    proc = subprocess.Popen(argv, cwd=str(workspace), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, **kwargs)
    try:
        _, stderr = proc.communicate(timeout=VERIFY_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        proc.communicate()
        return TIMEOUT
    err = (stderr or b"").decode("utf-8", "replace")
    if proc.returncode == 1 and "No module named pytest" in err:
        return None
    # Exit 3 and 4 are pytest's own internal and usage errors, and no junit.xml means pytest never
    # got as far as writing one: those are the environment. Every other exit code with a junit
    # beside it is scored from that file -- see the docstring.
    if proc.returncode in (3, 4) or not junit.is_file():
        return None
    try:
        suite = ET.parse(str(junit)).getroot()
    except ET.ParseError:
        return None
    suite = suite if suite.tag == "testsuite" else suite.find("testsuite")
    if suite is None:
        return None

    stems = {n[:-3] for n in names}
    counts = {False: [0, 0], True: [0, 0]}
    # Every visible case the junit carries, skipped ones included: `total` drops a skip on purpose,
    # so it cannot answer "was every test the template defines actually collected".
    collected = {False: 0, True: 0}
    seen = 0
    for case in suite.iter("testcase"):
        seen += 1
        # xunit2 (the default) carries no file attribute, so the module name in classname is
        # what identifies the file; xunit1 carries file. Held-out files are test_<module>_holdout
        # and can therefore not collide with the workspace's own test_<module>.
        path = case.get("file") or ""
        # A collection error carries an empty classname; pytest reports the module stem as the
        # test name there (`test_x` for test_x.py), which is what identifies the file instead.
        ident = case.get("classname", "") or case.get("name", "")
        is_holdout = (path.replace("\\", "/").rsplit("/", 1)[-1] in names if path
                      else any(part in stems for part in ident.split(".")))
        collected[is_holdout] += 1
        # A skipped test is neither passed nor failed, so it leaves the fraction entirely: a
        # skipif on the machine's interpreter would otherwise lower the score for a reason that
        # has nothing to do with the methodology.
        if any(c.tag == "skipped" for c in case):
            continue
        bad = any(c.tag in ("failure", "error") for c in case)
        counts[is_holdout][0] += 1
        counts[is_holdout][1] += 0 if bad else 1
    if not seen:
        # pytest ran but collected nothing at all, so the junit carries no testcase to count. The
        # suite's own test functions are the denominator, which keeps the row at 0.00 rather than
        # at a blank score; 0 when even that cannot be read, and 0/0 is 0.00 as well. A run whose
        # cases were all skipped is not this case -- those left the fraction on purpose.
        counts[False][0] = count_test_functions(workspace, targets)
        # The same number is the collected count here, so the caller's shortfall check -- which
        # would otherwise add this denominator a second time -- is a no-op on a run that collected
        # nothing at all. That run already scores 0.00 over the full suite.
        collected[False] = counts[False][0]
    return tuple(counts[False]), tuple(counts[True]), collected[False]


def main(size_ref=None, mi_ref=None, require_smaller_than_baseline=False,
         expects_tests=True, argv=None):
    # size_ref is accepted because every project declares it (chapter 11) and the declaration is
    # the record; nothing here scores it or writes it out.
    argv = sys.argv if argv is None else argv
    if len(argv) < 3:
        sys.stderr.write("usage: run_verification.py <workspace> <run dir> "
                         "[baseline|\"\"] [holdout dir] [template dir]\n")
        return 2
    workspace, run_dir = Path(argv[1]).resolve(), Path(argv[2]).resolve()
    baseline = len(argv) > 3 and argv[3] == "baseline"
    holdout = Path(argv[4]).resolve() if len(argv) > 4 and argv[4] else None
    if holdout is not None and not holdout.is_dir():
        holdout = None
    template = Path(argv[5]).resolve() if len(argv) > 5 and argv[5] else None
    if template is None or not template.is_dir():
        template = workspace
    targets = test_files(template)
    run_dir.mkdir(parents=True, exist_ok=True)
    target = run_dir / ("verification_baseline.txt" if baseline else "verification.txt")
    metrics = run_dir / ("metrics_baseline.txt" if baseline else "metrics.txt")

    # Before the metrics and before pytest: a pytest config or hook file the template does not ship
    # is the agent's, it is deleted, and the row is scored on the cleaned tree (chapter 11). The
    # removal is recorded in verification.txt as `config_tampered=1`, which the harness lifts into
    # res_tests_tampered -- a restore that only puts back template files cannot see this class.
    stripped = strip_pytest_config(workspace, template)
    marks = "config_tampered=1\n" if stripped else ""

    m = code_metrics(workspace)
    sloc = m["sloc"]
    # mi_ref is written for audit -- it is what the factor was divided by -- and is deliberately
    # not lifted into a results column: it is a project constant, identical on every row.
    m["mi_ref"] = mi_ref if mi_ref else ""
    m["parsimony_factor"] = round(parsimony_factor(m["mi"], mi_ref), 3)
    metrics.write_text("".join("%s=%s\n" % (k, m[k]) for k in sorted(m)), encoding="utf-8")

    if not [n for n in targets if n.startswith("test_")] or not expects_tests:
        # A project whose template ships no test file has no oracle. Any test file present was
        # written by the agent itself, so running it would let a methodology score itself.
        target.write_text("passed=\ntotal=\nscore=\npassed_holdout=\ntotal_holdout=\n"
                          "score_holdout=\n", encoding="utf-8")
        return 0

    result = run_pytest(workspace, run_dir / ("junit_baseline.xml" if baseline else "junit.xml"),
                        holdout, targets)
    if result is None:
        return 2
    expected = count_test_functions(template, targets)
    if result is TIMEOUT:
        # A suite that never finishes is a failure of the code under test, not a broken machine, so
        # it is exit 1 with score 0.00 over the template's own test count -- res_verification_error
        # stays false and res_verification_exit stays 1. The `timeout=1` marker is what lets the
        # harness say TIMEOUT in run.log without a column of its own (chapter 11).
        target.write_text("passed=0\ntotal=%s\nscore=0.0000\npassed_holdout=\ntotal_holdout=\n"
                          "score_holdout=\ntimeout=1\n%s" % (expected, marks), encoding="utf-8")
        return 1
    (total, passed), (total_h, passed_h), collected = result
    # An emptied or deleted implementation is a scored fail, never an environment error: pytest ran
    # and reported the import failures, and returning 2 here dropped that row out of the statistics
    # with a blank score. sloc 0 leaves the metrics at zero and MI 0 takes the parsimony floor.
    #
    # Whatever pytest collected must cover what the template defines. A shortfall means tests were
    # deselected or made uncollectable -- the very thing an added pytest.ini bought -- so the
    # missing ones are counted as failures instead of shrinking the denominator (chapter 11).
    if collected < expected:
        total += expected - collected

    # The visible suite alone defines passed/total/score and the exit code. The held-out suite is
    # a second, unscaled fraction beside them: res_score - res_score_holdout is what measures
    # fitting-to-the-test, and folding it into one number would hide exactly that.
    score = (float(passed) / total) if total else 0.0
    if not baseline:
        score *= m["parsimony_factor"]
    holdout_lines = "passed_holdout=\ntotal_holdout=\nscore_holdout=\n"
    if total_h:
        holdout_lines = "passed_holdout=%s\ntotal_holdout=%s\nscore_holdout=%.4f\n" % (
            passed_h, total_h, float(passed_h) / total_h)
    target.write_text("passed=%s\ntotal=%s\nscore=%.4f\n%s%s" % (passed, total, score,
                                                                holdout_lines, marks),
                      encoding="utf-8")

    green = bool(total) and passed == total
    if require_smaller_than_baseline:
        base_sloc = read_metric(run_dir / "metrics_baseline.txt", "sloc")
        if baseline:
            # The pristine module already passes its own tests, so it is by definition not yet
            # simplified: baseline verification fails on the gate, not on the tests.
            return 1 if green else 2
        if base_sloc is None:
            return 2
        return 0 if green and sloc < base_sloc else 1
    return 0 if green else 1
