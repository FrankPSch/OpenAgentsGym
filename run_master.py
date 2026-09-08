#!/usr/bin/env python3
"""OpenAgentsGym harness -- oam_targetpicture.md chapters 12 and 13. Stdlib only, Python >= 3.9.

    py -3 run_master.py <project> <methodology> [--config <path>]
    py -3 run_master.py --matrix [--config <path>] [--workers N] [--skip-existing]
                                 [--projects a,b] [--methodologies x,y]
    py -3 run_master.py --consolidate
    py -3 run_master.py --gate [--campaign <name>] [--apparatus-only]

--config selects the campaign constants file. The files are the four capability levels
.llm_config.model_01 .. .llm_config.model_04 (chapter 9); the default is .llm_config.model_02, and a
relative path is resolved against the repository root.
"""
import csv
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Run directories are machine-local (`local/` is git-ignored, see .gitignore); the consolidated
# table is rebuildable from them and lives at the repo root so it is published with the repo.
LOCAL = ROOT / "local"
RESULTS_TABLE = ROOT / "results_repository.csv"
# Capability levels (chapter 9): .llm_config.model_01 (cheapest, apparatus checks) .. model_04
# (above the frontier tier). Level 2 is the default here; the model id lives only in the file.
DEFAULT_CONFIG = ".llm_config.model_02"
# Run directories live under local/ too: they are per-run artifacts and account data, never source.
RUNS = LOCAL / "runs"
IS_WIN = os.name == "nt"
PARAM_KEYS = ("definition_of_done", "constraint_order", "doc_types",
              "review_rounds", "gate_style", "phase_budget", "retry_policy")
FIXED_TAMPER = ("conftest.py", "pytest.ini", "pyproject.toml", ".requirements", ".environment")
PLACEHOLDER = re.compile(r"\{\{([a-z_]+)=([^}]*)\}\}")
VERSION_RE = re.compile(r"<!--\s*mth_version:\s*(.*?)\s*-->")
CLI_TIMEOUT_S = 3600
# The second layer under lib/oracle.py's own VERIFY_TIMEOUT_S (300 s, chapter 11): wide enough that
# a normal oracle run -- pytest plus the metrics -- never reaches it, so it fires only when the
# oracle process hangs somewhere pytest's own bound cannot see. Without either, an infinite loop in
# generated code stalled a matrix worker forever.
ORACLE_TIMEOUT_S = 420
UTF8_ENV = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

# Every long option step7 puts on the launch line, plus -p. The CLI accepts unknown options
# silently (verified: a bogus flag exits 0), so an option dropped by a CLI upgrade becomes an
# invisible no-op instead of an error -- which is exactly how --max-turns entered the harness.
REQUIRED_FLAGS = ("-p", "--model", "--effort", "--max-budget-usd", "--output-format",
                  "--permission-mode", "--allowedTools", "--strict-mcp-config", "--mcp-config",
                  "--no-session-persistence", "--setting-sources", "--add-dir")
# The review launch line (step 7b) adds one option to the implementer's set. It is validated only
# when a same-model review is configured, so an older CLI without it still runs REVIEW_PASS=none.
REVIEW_FLAGS = ("--disallowedTools",)
REVIEW_MODES = ("none", "same_model", "other_model")
# The --effort levels the CLI offers (chapter 9). A value outside them is rejected by the CLI
# itself, after the run directory and the venv exist, so it is checked in the pre-flight instead.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
# The --allowedTools list every arm launches with. An arm may replace it by shipping tools.txt,
# which cfg_tools then records (chapter 15).
DEFAULT_TOOLS = ("Read,Edit,Write,Glob,Grep,Agent,"
                 "Bash(python:*),Bash(pytest:*),"
                 "PowerShell(python:*),PowerShell(pytest:*)")
# One tools.txt line: a tool name, optionally with a parenthesised pattern. The CLI accepts an
# unrecognised entry silently, exactly as it accepts an unknown flag, so a typo would drop a tool
# with no visible error; the shape is checked before the run instead.
TOOL_LINE = re.compile(r"^[A-Za-z]+(\(.*\))?$")
# Conventional Comments (chapter 19.4) is what makes the findings a count rather than a guess.
# A model asked for bare lines still reaches for a bullet and a capital, and a finding lost to
# formatting is a miscount, not a stricter measurement -- so a leading markdown bullet and the
# label's case are tolerated. The label itself is not: a line without one is not a finding.
REVIEW_LINE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(issue|nitpick|question|praise)\s*:", re.I)
# The optional `changes=` suffix a finding may carry (lib/reviewer_prompt.md, and the schema
# 17_finding_schema deploys). It runs to the next `key=` field or to the end of the line, so it
# reads the same whether the schema puts `confidence=` after it or nothing does. `changes=none` is
# how the schema says a finding needs no edit, so it is not actionable and neither is a blank one.
CHANGES_FIELD = re.compile(r"\bchanges\s*=\s*(.*?)(?=\s+[a-z_]+\s*=|$)", re.I)
# The reviewer is stdin-only: no tools at all, so it cannot read the entry file, the methodology's
# own PLAN.md/DECISIONS.md/SUMMARY.md, or anything else the implementer left behind.
REVIEW_DISALLOWED = "Read,Edit,Write,Glob,Grep,Bash,PowerShell,Agent,WebFetch,WebSearch"
# Between the three parts of the reviewer's stdin. A rule the reviewer prompt itself states.
REVIEW_SEP = "\n\n" + "-" * 70 + "\n\n"
_CLI_CACHE = {}


def kill_tree(proc):
    """Kill a timed-out subprocess and everything it started.

    Killing the direct child alone leaves its own children holding the pipes and the harness hangs
    on the read instead. `taskkill /T /F` walks the tree on Windows; elsewhere the child was started
    in a session of its own, so one killpg reaches all of it.
    """
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(proc.pid, 9)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def template_test_count(template):
    """How many `test_*` functions the template's visible suite defines (chapter 11).

    The denominator the harness falls back to when it has to write a verification.txt itself -- an
    oracle killed by ORACLE_TIMEOUT_S wrote none -- so the row scores 0.00 over the real suite size
    rather than dropping out of the statistics with a blank score.
    """
    total = 0
    for path in sorted(template.glob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        total += len(re.findall(r"^\s*(?:async\s+)?def\s+test\w*\s*\(", text, re.M))
    return total


def child_env(extra=None):
    """os.environ plus a forced UTF-8 stdio, so Windows cp1252 cannot corrupt a pipe."""
    env = os.environ.copy()
    env.update(UTF8_ENV)
    if extra:
        env.update(extra)
    return env

def write_record(path, text):
    """Write a record file: a private temporary beside it, then an atomic rename.

    Everything else a run writes lives inside its own run directory, but the two invocation-level
    records -- `local/runs/_cli_help.txt` and `local/runs/_preflight_ancestors.txt` -- are written by every
    invocation, so two matrix workers can be inside the same `write_text` at once and leave a file
    that is half of each. `os.replace` is atomic on both platforms: a reader sees the old bytes or
    the new ones. The content is identical either way; the point is that the file stays readable.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("%s.%d.tmp" % (path.name, os.getpid()))
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(path))


COLUMNS = [
    "id_run", "id_timestamp", "id_repeat",
    "prj_name",
    "mth_name", "mth_version", "mth_chars",
    "mth_param_definition_of_done", "mth_param_constraint_order", "mth_param_doc_types",
    "mth_param_review_rounds", "mth_param_gate_style", "mth_param_phase_budget",
    "mth_param_retry_policy",
    "cfg_campaign",
    "cfg_engine", "cfg_cli_version", "cfg_model", "cfg_effort", "cfg_user_claude_md",
    "cfg_review_pass", "cfg_review_model", "cfg_fix_model", "cfg_review_prompt",
    "cfg_review_weight", "cfg_tools",
    "res_score_baseline", "res_score", "res_score_holdout",
    "res_bestof_n", "res_bestof_min", "res_bestof_max",
    "res_verification_passed", "res_verification_error",
    "res_verification_exit",
    "res_review_findings", "res_review_issues", "res_review_actionable", "res_review_fixed",
    "res_review_error",
    "res_tests_tampered", "res_files_added", "res_files_added_src", "res_diff_lines",
    "res_lines_added",
    "res_lines_removed", "res_artifacts", "res_subtype", "res_hit_turn_cap",
    "res_subagents_spawned", "res_permission_denials", "res_model_served",
    "res_sloc", "res_sloc_baseline", "res_sloc_delta",
    "res_chars", "res_complexity", "res_mi", "res_parsimony_factor",
    "res_max_func_sloc", "res_max_nesting", "res_lint_errors", "res_docstring_cov",
    "res_comment_density",
    "tk_input", "tk_output", "tk_thinking", "tk_cache_write", "tk_cache_read", "tk_cost_usd",
    "tk_bestof_cost_usd",
    "tk_review_input", "tk_review_output", "tk_review_cache_write", "tk_review_cache_read",
    "tk_review_cost_usd",
    "tk_fix_input", "tk_fix_output", "tk_fix_cache_write", "tk_fix_cache_read", "tk_fix_cost_usd",
    "prf_turns", "prf_duration_s", "prf_review_s", "prf_fix_s",
]

METRIC_COLUMNS = {
    "sloc": "res_sloc", "chars": "res_chars", "complexity": "res_complexity", "mi": "res_mi",
    "parsimony_factor": "res_parsimony_factor", "max_func_sloc": "res_max_func_sloc",
    "max_nesting": "res_max_nesting", "lint_errors": "res_lint_errors",
    "docstring_cov": "res_docstring_cov", "comment_density": "res_comment_density",
}

ARTIFACTS = ("PLAN.md", "DECISIONS.md", "SUMMARY.md", "REVIEW.md", "AGENT_BACKLOG.md",
             "RUN_NOTES.md")
# Declared artifacts that are a directory of files rather than one name: the ADR form of the D
# feature (chapter 19.3) writes one record per decision, so the glob is what detects it.
ARTIFACT_GLOBS = ("docs/adr/*.md",)

# Outside every diff figure (chapter 13): the entry file the harness itself deploys, and the three
# documents the D feature asks for. Neither is code the agent chose to add, and counting them made
# the restraint columns grow with mth_chars -- res_files_added read 4 on every 02_doctypes row for
# writing exactly what its methodology demanded. res_artifacts already records the three.
DIFF_EXCLUDED = ("CLAUDE.md", "AGENTS.md", "PLAN.md", "DECISIONS.md", "SUMMARY.md")


def csv_name(col):
    return col


def plain_name(col):
    """Strip a leading NN_ so files written while numeric prefixes were in use still merge."""
    return re.sub(r"^\d\d_(?=(id|prj|mth|cfg|res|tk|prf)_)", "", col)


class Abort(Exception):
    """What die() raises. Where it is caught decides how far the abort reaches (chapter 12).

    Caught before the repeat loop it ends the invocation; caught inside a repeat it ends that
    repeat, is written to `abort.txt` and to `_master.log`, and the next repeat starts. A
    `REPEATS=3` invocation therefore yields two rows and one recorded abort rather than one row and
    silence.
    """

    def __init__(self, msg, code):
        Exception.__init__(self, msg)
        self.msg, self.code = msg, code


def die(msg, code):
    print(msg)
    raise Abort(msg, code)


def step1_read_config(config=DEFAULT_CONFIG):
    """Read the campaign constants from the config file (KEY=VALUE, # comments allowed).

    The default is .llm_config.model_02; --config selects another level, so a cheap sweep
    (.llm_config.model_01) and the campaign proper differ by a file rather than by an edit.
    A relative path is resolved against the repository root, not the caller's cwd.
    """
    cfg = {}
    path = Path(config)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        die("ABORT: config file not found at %s" % path, 4)
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "=" not in line:
            die("ABORT: malformed line in %s: %r" % (path, raw), 4)
        k, v = line.split("=", 1)
        # `=value` is a malformed line, not a key: it would land in cfg[""] and the key it was
        # meant for would read as unset -- a silent default rather than a config error.
        if not k.strip():
            die("ABORT: malformed line in %s: %r" % (path, raw), 4)
        cfg[k.strip()] = v.strip()
    # The single gate on the engine. Every other coupling to this CLI is in this file and is
    # listed in chapter 18 under "GPT branch": nothing under methodology/, projects/, lib/ or the
    # batch files names a vendor, so a second engine is a change here and nowhere else.
    if cfg.get("ENGINE") != "claude":
        die("ABORT: ENGINE=claude is the only valid value (got %r)" % cfg.get("ENGINE"), 4)
    # An unset or blank REVIEW_PASS is `none`, so a config file written before the review pass
    # existed keeps working unchanged. A misspelt one is a config error, not a silent no-op.
    cfg["REVIEW_PASS"] = cfg.get("REVIEW_PASS", "").strip() or "none"
    if cfg["REVIEW_PASS"] not in REVIEW_MODES:
        die("ABORT: REVIEW_PASS=%s (got %r)" % ("|".join(REVIEW_MODES), cfg["REVIEW_PASS"]), 4)
    # The file's own name is the campaign label (cfg_campaign, chapter 13). It is set here rather
    # than read from the file, so it cannot disagree with the file that was actually used.
    cfg["CAMPAIGN"] = path.name
    return cfg


def review_prompt_path(cfg):
    """The reviewer prompt file (chapter 9). Blank REVIEW_PROMPT is the default one in lib/.

    A relative path resolves against the repository root, as --config and CLAUDE_CONFIG_DIR do, so
    a config file is portable between checkouts.
    """
    named = cfg.get("REVIEW_PROMPT", "").strip()
    p = Path(named) if named else Path("lib") / "reviewer_prompt.md"
    return p if p.is_absolute() else ROOT / p


def review_feedback_on(cfg):
    return (cfg.get("REVIEW_FEEDBACK", "").strip() or "0") == "1"


def best_of_n(cfg):
    return int(cfg.get("BEST_OF_N", "").strip() or "1")


def review_weight(cfg):
    """How many independent reviewers the review pass runs (chapter 9, REVIEW_WEIGHT).

    One reviewer's silence is not evidence: a pass that files no issue measures the reviewer as
    much as the code. n reviewers on the same prompt and the same diff, each in a working
    directory of its own, turn that into a sample -- the findings of all n are counted together.
    """
    return int(cfg.get("REVIEW_WEIGHT", "").strip() or "1")


def fix_model(cfg):
    """The model the step-7c fix call runs on, and the cfg_fix_model cell (chapter 9, FIX_MODEL).

    Blank FIX_MODEL means the implementer's MODEL, so the fix call is the implementer again in
    every respect, as it was before the key existed. The column is blank wherever the feedback
    loop is off, because there is no fix call there to carry a model.
    """
    if not review_feedback_on(cfg):
        return ""
    return cfg.get("FIX_MODEL", "").strip() or cfg["MODEL"]


def reject_alias(model, key):
    """Abort unless `model` is a canonical id (chapter 9). The test is the version part.

    A canonical id carries a digit in a dash-separated part after the first
    (`claude-sonnet-5`); a bare `opus`, `sonnet` or `sonnet-latest` does not. An alias silently
    re-points to a different model between campaigns while every column still reads as intended,
    which is why it is caught here rather than noticed in `res_model_served` afterwards.
    """
    parts = model.split("-")
    if not model or len(parts) < 2 or not any(c.isdigit() for p in parts[1:] for c in p):
        die("ABORT: %s=%r is an alias, not a canonical id -- an alias silently re-points to\n"
            "another model between campaigns and invalidates the comparison. Use the full id,\n"
            "e.g. claude-sonnet-5." % (key, model), 4)


def check_model(cfg):
    """MODEL must be a canonical id, and no fallback model may be configured (chapter 9, 15).

    `--fallback-model` substitutes a model silently on overload, which corrupts a comparison with
    no visible error, so it is checked here beside the alias rule. FIX_MODEL takes the same alias
    rule when it is set: it is a second model id on the row and an alias there is the same defect.
    REVIEW_MODEL takes it too, but on same_model only: there it is this vendor's id and `opus` is
    the same silent re-pointing as in MODEL, while on other_model it is a foreign vendor's id
    (`gpt-5`, `o3`) whose canonical form the digit-in-a-dashed-part rule would reject.
    """
    reject_alias(cfg.get("MODEL", "").strip(), "MODEL")
    named_fix = cfg.get("FIX_MODEL", "").strip()
    if named_fix:
        reject_alias(named_fix, "FIX_MODEL")
    named_review = cfg.get("REVIEW_MODEL", "").strip()
    if named_review and cfg.get("REVIEW_PASS", "") == "same_model":
        reject_alias(named_review, "REVIEW_MODEL")
    for key in ("CLAUDE_FALLBACK_MODEL",):
        if os.environ.get(key, "").strip() or cfg.get(key, "").strip():
            die("ABORT: %s is set -- a fallback model is substituted silently on overload and\n"
                "would corrupt the campaign with no visible error (chapter 14)." % key, 4)
    for source, items in (("the environment", os.environ.items()), ("the config", cfg.items())):
        for k, v in items:
            if "--fallback-model" in (v or ""):
                die("ABORT: --fallback-model appears in %s (%s) -- it substitutes a model\n"
                    "silently on overload and must never be set (chapter 14)." % (source, k), 4)


def check_config_keys(cfg):
    """Pre-flight validation of the keys carrying a type, a range or a path (chapter 9).

    Every abort names the key, so a mistyped config is a one-line fix rather than a hunt. It is
    exit 4 for the same reason a duplicate parameter key is: the run is already wrong and no
    environment work can make it right.
    """
    check_model(cfg)
    # EFFORT, MAX_BUDGET_USD, MAX_TURNS and REPEATS are read unguarded further down -- cfg["EFFORT"]
    # is on the launch line and in the campaign log, cfg["MAX_BUDGET_USD"] is the spending cap --
    # so a missing or mistyped one used to surface as a KeyError or a ValueError mid-run rather than
    # as a named abort here. All four are mandatory: every shipped config file carries them, and a
    # blank cap or a blank effort is not a default anyone should get silently.
    effort = cfg.get("EFFORT", "").strip()
    if effort not in EFFORT_LEVELS:
        die("ABORT: EFFORT=%s (got %r)" % ("|".join(EFFORT_LEVELS), effort), 4)
    budget = cfg.get("MAX_BUDGET_USD", "").strip()
    try:
        ok = float(budget) > 0
    except ValueError:
        ok = False
    if not ok:
        die("ABORT: MAX_BUDGET_USD must be a positive number of dollars (got %r)" % budget, 4)
    for key in ("MAX_TURNS", "REPEATS"):
        v = cfg.get(key, "").strip()
        if not v.isdigit() or int(v) < 1:
            die("ABORT: %s must be an integer >= 1 (got %r)" % (key, v), 4)
    fb = cfg.get("REVIEW_FEEDBACK", "").strip() or "0"
    if fb not in ("0", "1"):
        die("ABORT: REVIEW_FEEDBACK=0|1 (got %r)" % fb, 4)
    if fb == "1" and cfg["REVIEW_PASS"] == "none":
        die("ABORT: REVIEW_FEEDBACK=1 needs REVIEW_PASS != none -- there is no review to feed back",
            4)
    n = cfg.get("BEST_OF_N", "").strip() or "1"
    if not n.isdigit() or int(n) < 1:
        die("ABORT: BEST_OF_N must be an integer >= 1 (got %r)" % n, 4)
    w = cfg.get("REVIEW_WEIGHT", "").strip() or "1"
    if not w.isdigit() or int(w) < 1:
        die("ABORT: REVIEW_WEIGHT must be an integer >= 1 (got %r)" % w, 4)
    path = review_prompt_path(cfg)
    if not path.is_file():
        die("ABORT: REVIEW_PROMPT file not found at %s" % path, 4)


def allowed_tools(methodology):
    """The arm's --allowedTools list and the cfg_tools cell that records it (chapter 15).

    The default list is identical for every arm, so the tool set is not a treatment. An arm that
    ships `methodology/<M>/tools.txt` replaces it, and cfg_tools carries the deviation so chapter
    17 keeps rows with different tool sets out of one pivot.
    """
    src = ROOT / "methodology" / methodology / "tools.txt"
    if not src.is_file():
        return DEFAULT_TOOLS, "default"
    tools = [l.strip() for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not tools:
        die("ABORT: methodology/%s/tools.txt is empty" % methodology, 4)
    for line in tools:
        if not TOOL_LINE.match(line):
            die("ABORT: methodology/%s/tools.txt: %r is not a tool entry "
                "(Name or Name(pattern))" % (methodology, line), 4)
    return ",".join(tools), ",".join(tools)


def step2_make_run_dir(methodology, project, repeat, stamp):
    """Build the run id and create the run directory. Returns the id, the directory and the stamp.

    The id carries a one-second timestamp, so two workers of one matrix that start the same pair in
    the same second would build the same id and share one directory -- two runs writing one
    `result.json`, one `verification.txt` and one row. `exist_ok=False` is what catches that: on a
    collision the id is rebuilt from a fresh timestamp a second later, bounded at ten tries, and
    the caller takes the stamp back so `id_timestamp` still names the directory the run is in.
    """
    for _ in range(10):
        run_id = "run_%s_%s_%s_r%02d" % (methodology, project, stamp, repeat)
        run_dir = RUNS / run_id
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            return run_id, run_dir, stamp
        except FileExistsError:
            time.sleep(1)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    die("ABORT: run directory %s still exists after 10 attempts" % run_dir, 4)


def step3_snapshot_methodology(methodology, run_dir):
    """Copy methodology/<M>/ minus notes.md into the run directory."""
    src = ROOT / "methodology" / methodology
    if not src.is_dir():
        die("ABORT: methodology %r not found at %s" % (methodology, src), 4)
    shutil.copytree(src, run_dir / "methodology",
                    ignore=shutil.ignore_patterns("notes.md"))


def step4_copy_workspace(project, run_dir):
    """Copy projects/<P>/project_reset_template/ into the run's workspace. This copy is the reset."""
    template = ROOT / "projects" / project / "project_reset_template"
    if not template.is_dir():
        die("ABORT: project template not found at %s" % template, 4)
    workspace = run_dir / "project_workspace"
    shutil.copytree(template, workspace)
    return template, workspace


def render(text, source):
    """Render {{key=value}} to value verbatim. A duplicate key aborts the run."""
    seen = {}
    for m in PLACEHOLDER.finditer(text):
        key = m.group(1)
        if key in seen:
            die("ABORT: duplicate parameter key %r in %s "
                "(each key may occur at most once per entry file)" % (key, source), 4)
        seen[key] = m.group(2)
    return PLACEHOLDER.sub(lambda m: m.group(2), text), seen


def step5_deploy_entry_file(run_dir, workspace):
    """Render the placeholders and deploy the entry file as CLAUDE.md. Empty copy_to_root is fine.

    The target name is unconditional: `AGENTS.md` is the name the same source file takes under the
    GPT branch, and that branch is open (chapter 18). The source is named `agents_or_claude.md`
    because the text is already portable between the two -- only the destination waits.

    The source is the run's own snapshot (step 3), never `methodology/<M>/`: deploying from the
    source directory meant an edit between the two steps gave the agent a file the snapshot does
    not contain, so the run directory no longer recorded what ran (chapter 12, step 5).
    """
    src = run_dir / "methodology" / "copy_to_root" / "agents_or_claude.md"
    blanks = {"mth_chars": 0, "mth_version": ""}
    blanks.update({"mth_param_" + k: "" for k in PARAM_KEYS})
    if not src.is_file():
        return blanks
    raw = src.read_text(encoding="utf-8")
    rendered, params = render(raw, str(src))
    target = workspace / "CLAUDE.md"
    target.write_text(rendered, encoding="utf-8")
    out = {"mth_chars": len(rendered.encode("utf-8"))}
    first = rendered.splitlines()[0] if rendered.splitlines() else ""
    m = VERSION_RE.search(first)
    out["mth_version"] = m.group(1) if m else ""
    for k in PARAM_KEYS:
        out["mth_param_" + k] = params.get(k, "")
    return out


def venv_python(run_dir):
    return run_dir / (".venv/Scripts/python.exe" if IS_WIN else ".venv/bin/python")


def interpreter_cmd(version):
    """Return the base command that builds the venv, or None when it is not available."""
    candidates = [["py", "-" + version]] if IS_WIN else [["python" + version], ["python3"]]
    for cmd in candidates:
        try:
            p = subprocess.run(cmd + ["-c", "import sys"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, env=child_env())
            if p.returncode == 0:
                return cmd
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def read_triple(path):
    """Read passed=/total=/score= and their held-out counterparts from a verification*.txt."""
    out = {"passed": "", "total": "", "score": "",
           "passed_holdout": "", "total_holdout": "", "score_holdout": ""}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                if k.strip() in out:
                    out[k.strip()] = v.strip()
    return out


def copy_holdout(project, run_dir):
    """Copy projects/<P>/holdout_tests/*.py into local/runs/<id>/holdout/ and return that directory.

    Idempotent. The held-out suite never enters the project_workspace -- the agent must not see the
    tests it is scored on a second time, and a suite it cannot reach is a suite it cannot weaken,
    so it stays out of the tamper set. Returns None when the project ships none.

    **It must not exist while the agent runs.** `local/runs/<id>/holdout/` is one directory above
    the workspace the agent works in, so any `Bash(python:*)` call could read `../holdout/` and fit
    to it. Pre-flight therefore deletes it again before step 7 (drop_holdout) and step 8 re-creates
    it after the agent has exited (chapter 12, steps 6 and 8).
    """
    src = ROOT / "projects" / project / "holdout_tests"
    files = sorted(src.glob("*.py")) if src.is_dir() else []
    if not files:
        return None
    dst = run_dir / "holdout"
    dst.mkdir(parents=True, exist_ok=True)
    for path in files:
        shutil.copy2(path, dst / path.name)
    return dst


def drop_holdout(run_dir):
    """Remove local/runs/<id>/holdout/ again. Called before the agent is launched (chapter 12)."""
    shutil.rmtree(str(run_dir / "holdout"), ignore_errors=True)


def run_oracle(project, run_dir, workspace, baseline=False, holdout=None, out_dir=None):
    """Run the project's oracle. out_dir is where it writes, defaulting to the run directory.

    The two differ only under BEST_OF_N, where each candidate is scored into its own directory so
    the candidates cannot overwrite each other's verification.txt and metrics.txt.

    The template is the fifth argument: it is what tells the oracle which test files exist, so
    pytest collects the project's suite and never a test the agent wrote (chapter 11).

    The call is bounded by ORACLE_TIMEOUT_S. The oracle bounds pytest itself (VERIFY_TIMEOUT_S), so
    this is the second layer and fires only when the oracle process hangs outside pytest: the tree
    is killed, the run is recorded as a failing run with score 0.00 rather than stalling a worker,
    and run.log says TIMEOUT (chapter 11).
    """
    out_dir = out_dir or run_dir
    argv = [str(venv_python(run_dir)), str(ROOT / "projects" / project / "run_verification.py"),
            str(workspace), str(out_dir), "baseline" if baseline else "",
            str(holdout) if holdout else "",
            str(ROOT / "projects" / project / "project_reset_template")]
    kwargs = {} if IS_WIN else {"start_new_session": True}
    proc = subprocess.Popen(argv, cwd=str(run_dir), env=child_env(), **kwargs)
    try:
        proc.communicate(timeout=ORACLE_TIMEOUT_S)
        return proc.returncode
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        proc.communicate()
        target = out_dir / ("verification_baseline.txt" if baseline else "verification.txt")
        if not target.is_file():
            target.write_text("passed=0\ntotal=%s\nscore=0.00\npassed_holdout=\ntotal_holdout=\n"
                              "score_holdout=\ntimeout=1\n"
                              % template_test_count(ROOT / "projects" / project
                                                    / "project_reset_template"),
                              encoding="utf-8")
        print("TIMEOUT: %s exceeded %ds -- killed, scored 0.00"
              % (Path(argv[1]).name, ORACLE_TIMEOUT_S))
        return 1


def cli_help_and_version():
    """Query the installed CLI once per invocation and cache the answer."""
    if "help" not in _CLI_CACHE:
        claude = resolve_cli()
        env = child_env()
        h = subprocess.run([claude, "--help"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           env=env)
        v = subprocess.run([claude, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           env=env)
        _CLI_CACHE["help"] = (h.stdout or b"").decode("utf-8", "replace")
        text = (v.stdout or b"").decode("utf-8", "replace").strip().splitlines()
        _CLI_CACHE["version"] = text[0].strip() if text else ""
    return _CLI_CACHE["help"], _CLI_CACHE["version"]


def review_argv(template):
    """Split REVIEW_CMD into an argv list.

    posix=False so the backslashes of a Windows path survive the split; it leaves the quotes on a
    quoted token, which are stripped here. The template is a command, not a shell line -- no
    redirection, no pipes: the reviewer prompt goes in on stdin and stdout comes back.
    """
    out = []
    for tok in shlex.split(template, posix=False):
        if len(tok) > 1 and tok[0] == tok[-1] and tok[0] in "\"'":
            tok = tok[1:-1]
        out.append(tok)
    return out


def check_review_config(cfg):
    """Pre-flight for REVIEW_PASS=other_model: the command must be set and must exist.

    Same class of failure as a missing CLI flag -- the launch line cannot be trusted -- so the same
    exit 6, and it is checked before the implementer runs so nothing is spent on a run whose review
    cannot happen. same_model needs no check here: its flags go through check_cli_flags.
    """
    if cfg["REVIEW_PASS"] != "other_model":
        return
    template = cfg.get("REVIEW_CMD", "").strip()
    if not template:
        die("ABORT: REVIEW_CMD not set (REVIEW_PASS=other_model)", 6)
    argv = review_argv(template)
    if not argv or shutil.which(argv[0]) is None:
        die("ABORT: REVIEW_CMD executable %r not found on PATH (shutil.which)"
            % (argv[0] if argv else template), 6)


def check_cli_flags(cfg, record):
    """Abort unless every option the launch line uses is present in `claude --help`.

    The CLI ignores unknown options without complaint, so this is the only place a removed or
    renamed flag can be caught before tokens are spent. The help text is kept per run so a row
    stays diagnosable after a CLI upgrade. The review pass adds its own option to the set, and
    only when it is configured -- a CLI that cannot review is not a reason to fail a run that
    does not review.
    """
    help_text, version = cli_help_and_version()
    write_record(record, help_text)
    required = REQUIRED_FLAGS + (REVIEW_FLAGS if cfg["REVIEW_PASS"] == "same_model" else ())
    missing = [f for f in required if f not in help_text]
    if missing:
        die("ABORT: flag(s) not offered by this CLI (%s): %s\n"
            "The CLI accepts unknown options silently, so the launch line cannot be trusted.\n"
            "See %s" % (version or "unknown version", " ".join(missing), record), 6)
    return version


def step6_environment_and_preflight(cfg, project, template, workspace, run_dir):
    """Build the venv from the project's own .environment/.requirements, then pre-flight."""
    check_config_keys(cfg)
    cli_version = check_cli_flags(cfg, run_dir / "cli_help.txt")
    check_review_config(cfg)
    check_ancestor_entry_files(workspace, run_dir / "preflight_ancestors.txt")
    env_file = template / ".environment"
    version = ""
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("python="):
                version = line.strip().split("=", 1)[1].strip()
    if not version:
        die("ABORT: no python=<ver> in %s" % env_file, 4)

    # Exit 3 means one thing only: the interpreter the project pins is not on this machine, so the
    # run is skipped rather than failed. A venv or pip that breaks afterwards is a broken machine,
    # not a missing interpreter, and exits 4 naming the step and its log.
    base = interpreter_cmd(version)
    if base is None:
        die("SKIPPED: interpreter python=%s not available" % version, 3)
    p = subprocess.run(base + ["-m", "venv", str(run_dir / ".venv")],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=child_env())
    (run_dir / "venv.log").write_bytes(p.stdout or b"")
    if p.returncode != 0 or not venv_python(run_dir).is_file():
        die("ABORT: venv build failed for python=%s (step: python -m venv), see %s"
            % (version, run_dir / "venv.log"), 4)

    req = template / ".requirements"
    if req.is_file():
        p = subprocess.run([str(venv_python(run_dir)), "-m", "pip", "install", "-q", "-r", str(req)],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=child_env())
        (run_dir / "pip.log").write_bytes(p.stdout or b"")
        if p.returncode != 0:
            die("ABORT: dependency install failed (step: pip install -r .requirements), see %s"
                % (run_dir / "pip.log"), 4)

    oracle_less = not list(template.glob("test_*.py"))
    # The held-out suite is copied for the baseline and removed again before the agent can exist:
    # it lives one directory above the workspace, and `../holdout/` is readable by any python the
    # agent runs. Step 8 re-creates it (chapter 12, steps 6 and 8).
    try:
        rc = run_oracle(project, run_dir, workspace, baseline=True,
                        holdout=copy_holdout(project, run_dir))
    finally:
        drop_holdout(run_dir)
    if metric_value(run_dir / "verification_baseline.txt", "timeout") == "1":
        die("ABORT: pre-flight verification timed out on %s -- see verification_baseline.txt"
            % project, 4)
    if oracle_less:
        if rc == 2:
            die("ABORT: pre-flight environment error (exit 2) on oracle-less project %s" % project, 4)
    elif rc == 0:
        die("ABORT: pre-flight baseline PASSES on %s -- the project cannot measure anything" % project, 4)
    elif rc == 2:
        die("ABORT: pre-flight environment error (exit 2) on %s" % project, 4)
    # Vendor-shaped, both the path and the column name (cfg_user_claude_md): it records whether a
    # user-level entry file exists at all, and it is renamed with the GPT branch, not before.
    user_md = "present" if (Path.home() / ".claude" / "CLAUDE.md").is_file() else "absent"
    return oracle_less, user_md, cli_version


def check_ancestor_entry_files(workspace, record):
    """Chapter 15: no CLAUDE.md above the run root. Abort, do not warn.

    --setting-sources project drops the *user* memory file (verified: the user-level
    CLAUDE.md does not reach the agent, and it stays a label only, cfg_user_claude_md). It
    does not stop the CLI walking up from cwd and picking up project entry files in ancestor
    directories, and such a file enters every run as an invisible constant -- so it is not a
    thing to note in a column, it is a reason not to run.
    """
    found = []
    for parent in workspace.resolve().parents:
        for name in ("CLAUDE.md", "AGENTS.md"):
            p = parent / name
            if p.is_file():
                found.append(str(p))
    write_record(record, "\n".join(found) + ("\n" if found else ""))
    if found:
        die("ABORT: entry file(s) in an ancestor directory of the workspace -- chapter 15\n"
            "  " + "\n  ".join(found) + "\n"
            "The CLI auto-discovers these and they would enter every run as an invisible\n"
            "constant. Move the repository out from under that directory, or remove the file.",
            5)
    return found


def resolve_cli():
    """Resolve the CLI to something CreateProcess can launch.

    shutil.which() may hand back a .cmd/.bat shim, which subprocess cannot exec directly on
    Windows; prefer a sibling .exe when one exists, and abort when there is none rather than
    hand back a path CreateProcess cannot launch -- returning the shim only moved the failure to
    step 7, where it arrived as `WinError 193: %1 is not a valid Win32 application` after a run
    directory and a venv had already been built.

    A CLI that is not there, a CLI that cannot be launched and a CLI missing a flag are the same
    class of failure -- the launch line cannot be trusted -- so all three exit 6.
    """
    claude = shutil.which("claude")
    if claude is None:
        die("ABORT: 'claude' not found on PATH (shutil.which)", 6)
    p = Path(claude)
    if IS_WIN and p.suffix.lower() in (".cmd", ".bat", ""):
        exe = p.with_suffix(".exe")
        if exe.is_file():
            return str(exe)
        die("ABORT: 'claude' on PATH is %s, which CreateProcess cannot launch directly, and no\n"
            "sibling %s exists. Install the native Windows executable (or put its directory\n"
            "ahead of the shim on PATH) so the harness can start the CLI as a subprocess."
            % (p, exe.name), 6)
    return str(p)


def cli_env(cfg, run_dir):
    """The subprocess environment both CLI invocations run under -- step 7 and step 7b.

    One function, so the reviewer cannot drift onto a different interpreter or a different config
    directory from the implementer it is reviewing.
    """
    env = child_env()
    vroot = run_dir / ".venv"
    vbin = vroot / ("Scripts" if IS_WIN else "bin")
    env["VIRTUAL_ENV"] = str(vroot)
    env["PATH"] = str(vbin) + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONHOME", None)
    ccd = cfg.get("CLAUDE_CONFIG_DIR", "").strip()
    if ccd:
        env["CLAUDE_CONFIG_DIR"] = str((ROOT / ccd) if not os.path.isabs(ccd) else Path(ccd))
    else:
        env.pop("CLAUDE_CONFIG_DIR", None)
    return env


def implementer_argv(cfg, run_dir, tools, model=None):
    """The step-7 launch line. Every implementer invocation uses it, the fix call included.

    No --max-turns: Claude Code 2.1.251 has no such flag (it is an SDK option) and the CLI
    accepts unknown options silently, so passing it would be an invisible no-op. The run is
    bounded by --max-budget-usd; MAX_TURNS is a reporting threshold only (see res_hit_turn_cap).

    `model` overrides MODEL for one invocation and is used by the step-7c fix call alone
    (FIX_MODEL, chapter 9). Nothing else on the line moves with it: applying named issues is a
    different job from writing the code, and the tier it deserves is the open question.
    """
    # The CLI validates --mcp-config against a schema: a bare "{}" is rejected with
    # 'mcpServers: expected record, received undefined'. Written as a file, so no shell
    # quoting of JSON is involved and the run directory records what was actually passed.
    mcp = run_dir / "mcp_empty.json"
    mcp.write_text('{"mcpServers": {}}\n', encoding="utf-8")
    return [resolve_cli(), "-p",
            "--model", (model or cfg["MODEL"]), "--effort", cfg["EFFORT"],
            "--max-budget-usd", cfg["MAX_BUDGET_USD"],
            "--output-format", "json", "--permission-mode", "acceptEdits",
            # PowerShell is the shell tool Claude Code offers on Windows; a Bash-only list
            # denies the agent its own test run (observed as a permission_denial on
            # PowerShell "python -m pytest -q"). Both shells are listed so the policy is
            # the same restriction on either platform. Agent is the reviewer subagent the R
            # arms hand off to; it is listed unconditionally, because a tool set that varied
            # by arm would be a second treatment -- which is what cfg_tools records when an
            # arm ships tools.txt and replaces the list deliberately.
            "--allowedTools", tools,
            "--strict-mcp-config", "--mcp-config", str(mcp),
            "--no-session-persistence", "--setting-sources", "project",
            "--add-dir", str(run_dir / "methodology")]


def launch_implementer(cfg, run_dir, workspace, stdin, tools, out_path, err_path,
                       model=None, argv_name="cli_argv.txt"):
    """One implementer invocation with cwd = workspace and stdin piped in.

    Used by step 7, by each best-of-N candidate and by the feedback fix call, so those three
    cannot drift onto different flags, a different tool set or a different budget. The fix call
    passes its own `model` and its own `argv_name`: under FIX_MODEL the two launch lines really
    differ, and one file overwriting the other would leave the run directory unable to say which.
    """
    args = implementer_argv(cfg, run_dir, tools, model)
    (run_dir / argv_name).write_text("\n".join(args), encoding="utf-8")
    started = time.time()
    timed_out = False
    try:
        p = subprocess.run(args, cwd=str(workspace), input=stdin, text=True, encoding="utf-8",
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           env=cli_env(cfg, run_dir), timeout=CLI_TIMEOUT_S)
        out, err = p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired as e:
        timed_out = True
        out = e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        err = e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace")
    wall = time.time() - started
    out_path.write_text(out, encoding="utf-8")
    err_path.write_text(err, encoding="utf-8")
    return wall, timed_out


def step7_launch_cli(cfg, project, run_dir, workspace, tools):
    """Launch the CLI in the workspace with the project's prompt on stdin."""
    prompt = (ROOT / "projects" / project / "prompt.md").read_text(encoding="utf-8")
    return launch_implementer(cfg, run_dir, workspace, prompt, tools,
                              run_dir / "result.json", run_dir / "stderr.txt")


def step7a_best_of_n(cfg, project, run_dir, template, workspace, tools, n):
    """Run the implementer N times and keep the best candidate (chapter 12, step 7a).

    Sequential by design. Each candidate gets its own fresh copy of the template with the entry
    file deployed, and the highest res_score wins with the cheaper run breaking a tie. The winner
    becomes project_workspace/ and its output becomes result.json, so everything downstream --
    review, tamper, oracle, row -- sees one run. The candidates that lost are kept: their spend is
    real and lands in tk_bestof_cost_usd, and their workspaces stay in the run directory.

    **A candidate is scored on a throwaway copy, never in place.** The selection score needs the
    tamper set restored, but the winner must reach step 7b and step 8 exactly as its agent left it:
    a restore here would hide a weakened test from the reviewer's diff and would make
    res_tests_tampered read false on a row that tampered. So each candidate is copied to
    bestof_<n>/scored_workspace/, restored there and scored there, and the candidate workspace
    itself is untouched.
    """
    prompt = (ROOT / "projects" / project / "prompt.md").read_text(encoding="utf-8")
    # No held-out suite here. Candidates are launched and scored in turn, so a holdout/ directory
    # copied for candidate 1 would sit one level above candidate 2's workspace while its agent runs
    # (chapter 12, step 7a). Selection is on the visible res_score and nothing else, and the
    # winner's held-out fraction is measured for the row in step 8.
    names = tamper_names(template)
    cands = []
    for i in range(1, n + 1):
        ws = run_dir / ("project_workspace_%d" % i)
        shutil.copytree(template, ws)
        step5_deploy_entry_file(run_dir, ws)
        wall, timed_out = launch_implementer(cfg, run_dir, ws, prompt, tools,
                                             run_dir / ("result_%d.json" % i),
                                             run_dir / ("stderr_%d.txt" % i))
        out_dir = run_dir / ("bestof_%d" % i)
        out_dir.mkdir(parents=True, exist_ok=True)
        scored = out_dir / "scored_workspace"
        if scored.is_dir():
            shutil.rmtree(str(scored))
        shutil.copytree(ws, scored)
        restore_tamper(template, scored, names)
        # The strict-reduction gate reads the baseline SLOC out of its own output directory, so
        # each candidate needs the pre-flight metrics beside it.
        base = run_dir / "metrics_baseline.txt"
        if base.is_file():
            shutil.copy2(base, out_dir / "metrics_baseline.txt")
        run_oracle(project, run_dir, scored, baseline=False, holdout=None, out_dir=out_dir)
        triple = read_triple(out_dir / "verification.txt")
        data = result_record((run_dir / ("result_%d.json" % i)).read_text(encoding="utf-8"))
        try:
            cost = float((data or {}).get("total_cost_usd") or 0)
        except (TypeError, ValueError):
            cost = 0.0
        cands.append({"i": i, "ws": ws, "wall": wall, "timed_out": timed_out, "cost": cost,
                      "score": float(triple["score"]) if triple["score"] else -1.0})
        print("bestof: candidate %d score=%s usd=%s" % (i, triple["score"] or "", cost))
    best = min(cands, key=lambda c: (-c["score"], c["cost"], c["i"]))
    if workspace.is_dir():
        shutil.rmtree(str(workspace))
    shutil.copytree(best["ws"], workspace)
    shutil.copy2(run_dir / ("result_%d.json" % best["i"]), run_dir / "result.json")
    shutil.copy2(run_dir / ("stderr_%d.txt" % best["i"]), run_dir / "stderr.txt")
    scored = [c["score"] for c in cands if c["score"] >= 0]
    row = {"res_bestof_n": n,
           "res_bestof_min": ("%.2f" % min(scored)) if scored else "",
           "res_bestof_max": ("%.2f" % max(scored)) if scored else "",
           "tk_bestof_cost_usd": round(sum(c["cost"] for c in cands) - best["cost"], 6)}
    print("bestof: chose candidate %d" % best["i"])
    return best, row


def changes_field(line):
    """The finding line's `changes=` value, or "" when it carries none that names an edit.

    `res_review_actionable` is the count of `issue:` lines this returns a value for (chapter 13).
    A finding without the field named no edit; one with `changes=none` said in the schema's own
    words that there is none. Both are findings and neither is a thing to do.
    """
    m = CHANGES_FIELD.search(line)
    value = (m.group(1).strip() if m else "").strip("`\"'.,;")
    return "" if value.lower() in ("", "none") else value


def issue_lines(run_dir):
    """The `issue:` lines of review.md, verbatim -- the fix call's whole brief."""
    path = run_dir / "review.md"
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = REVIEW_LINE.match(line)
        if m and m.group(1).lower() == "issue":
            out.append(line.strip())
    return out


def step7c_feedback(cfg, project, run_dir, workspace, tools, review_error=False):
    """Act on the review: one more implementer invocation on the `issue:` lines (step 7c).

    Same launch line, same tools, same cwd and the same budget key as step 7 -- it is the
    implementer again, given the task, what the review found, and an instruction to fix that and
    nothing else. The oracle then runs on the result, so the row scores the fixed code.

    Its counters stay in tk_fix_*, never folded into tk_cost_usd: chapter 17 ranks on the first
    invocation's spend, and the fix is a treatment carried by every arm of a campaign that runs
    it. Its permission denials stay out of res_permission_denials for the same reason -- that
    column is read from result.json, which is the first call's.
    """
    row = {"res_review_fixed": "", "tk_fix_input": "", "tk_fix_output": "",
           "tk_fix_cache_write": "", "tk_fix_cache_read": "", "tk_fix_cost_usd": "",
           "prf_fix_s": ""}
    if not review_feedback_on(cfg):
        return row
    if review_error:
        # The review pass failed, so `no issue: lines` says nothing about the code. res_review_fixed
        # stays blank -- 0 would claim the review ran and found nothing to do (chapter 13).
        print("feedback: skipped -- res_review_error=1, the review produced no findings to act on")
        return row
    issues = issue_lines(run_dir)
    if not issues:
        # The pass ran and found nothing to fix. 0, not blank: blank means the feature was off.
        row["res_review_fixed"] = 0
        print("feedback: no issue: lines -- no fix call")
        return row
    stdin = REVIEW_SEP.join([
        (ROOT / "projects" / project / "prompt.md").read_text(encoding="utf-8").strip(),
        "\n".join(issues),
        (ROOT / "lib" / "feedback_prompt.md").read_text(encoding="utf-8").strip()])
    (run_dir / "fix_input.txt").write_text(stdin, encoding="utf-8")
    wall, _ = launch_implementer(cfg, run_dir, workspace, stdin, tools,
                                 run_dir / "fix.json", run_dir / "fix_stderr.txt",
                                 model=fix_model(cfg), argv_name="fix_argv.txt")
    row["prf_fix_s"] = round(wall, 1)
    row["res_review_fixed"] = 1
    data = result_record((run_dir / "fix.json").read_text(encoding="utf-8"))
    if data is not None:
        usage = data.get("usage") or {}
        row["tk_fix_input"] = usage.get("input_tokens", "")
        row["tk_fix_output"] = usage.get("output_tokens", "")
        row["tk_fix_cache_write"] = usage.get("cache_creation_input_tokens", "")
        row["tk_fix_cache_read"] = usage.get("cache_read_input_tokens", "")
        row["tk_fix_cost_usd"] = data.get("total_cost_usd", "")
    print("feedback: issues=%d fixed=1 dur=%ss" % (len(issues), row["prf_fix_s"]))
    return row


def result_record(raw):
    """The `result` object out of a CLI stdout, whether it is that object or a stream of them."""
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if isinstance(parsed, list):
        for item in reversed(parsed):
            if isinstance(item, dict) and item.get("type") == "result":
                return item
        return None
    return parsed if isinstance(parsed, dict) else None


def review_diff(template, workspace):
    """The unified diff the reviewer is given: `.py` files, workspace against template.

    Source and tests only, so every name in DIFF_EXCLUDED is already out: the Markdown a
    methodology tells the agent to write -- PLAN.md, DECISIONS.md, SUMMARY.md -- is the
    implementer's own plan and reasoning, which the reviewer must not see (chapter 12, step 7b),
    and the deployed CLAUDE.md is the methodology itself. The held-out suite never enters the
    project_workspace, so it cannot reach the reviewer either.
    """
    import difflib
    skip = {".venv", "__pycache__", ".git", ".pytest_cache"}

    def listing(root):
        out = {}
        for p in sorted(root.rglob("*.py")):
            rel = p.relative_to(root)
            if not p.is_file() or any(part in skip for part in rel.parts):
                continue
            out[str(rel).replace("\\", "/")] = p
        return out

    tmpl, work = listing(template), listing(workspace)
    chunks = []
    for name in sorted(set(tmpl) | set(work)):
        def lines(d, n):
            if n not in d:
                return []
            try:
                return d[n].read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                return []
        a, b = lines(tmpl, name), lines(work, name)
        if a != b:
            chunks.extend(difflib.unified_diff(a, b, fromfile="a/" + name, tofile="b/" + name,
                                               lineterm=""))
    return "\n".join(chunks) + ("\n" if chunks else "")


def review_model(cfg):
    """The reviewer's model id, as recorded in cfg_review_model.

    Blank REVIEW_MODEL on same_model means the implementer's model, so the column names it rather
    than leaving the reader to look up MODEL. On other_model it is the vendor id as configured --
    a foreign CLI does not report back what it served, so the declaration is the only record.
    """
    if cfg["REVIEW_PASS"] == "none":
        return ""
    named = cfg.get("REVIEW_MODEL", "").strip()
    if named:
        return named
    return cfg["MODEL"] if cfg["REVIEW_PASS"] == "same_model" else ""


def step7b_review(cfg, project, run_dir, workspace, template):
    """Independent review pass: a second invocation over the diff (chapter 12, step 7b).

    It runs after the agent exits and before the tamper set is restored, so what it reads is what
    the agent actually left behind. It is blind by construction, and by construction rather than by
    instruction: its whole input is the reviewer prompt, the project's prompt.md and the diff, it
    is given no tools, and its cwd is a directory created empty for the call. A reviewer that ran
    in the project_workspace with a file-reading tool would only have to open CLAUDE.md, PLAN.md or
    DECISIONS.md to see the implementer's methodology and reasoning -- and an other_model reviewer
    is an external process, which in that cwd would have write access to the workspace about to be
    scored. Its verdict gates nothing; it is measured, not obeyed.
    """
    mode = cfg["REVIEW_PASS"]
    row = {"res_review_findings": "", "res_review_issues": "", "res_review_actionable": "",
           "res_review_error": "",
           "tk_review_input": "", "tk_review_output": "", "tk_review_cache_write": "",
           "tk_review_cache_read": "", "tk_review_cost_usd": "", "prf_review_s": ""}
    if mode == "none":
        return row
    row["res_review_error"] = 0
    weight = review_weight(cfg)
    stdin = REVIEW_SEP.join([
        review_prompt_path(cfg).read_text(encoding="utf-8").strip(),
        (ROOT / "projects" / project / "prompt.md").read_text(encoding="utf-8").strip(),
        review_diff(template, workspace)])
    # One input for every reviewer of the weight: they are independent invocations of the same
    # prompt on the same diff, so the record that the pass was blind is one file.
    (run_dir / "review_input.txt").write_text(stdin, encoding="utf-8")
    if mode == "same_model":
        args = [resolve_cli(), "-p",
                "--model", review_model(cfg), "--effort", cfg["EFFORT"],
                "--max-budget-usd", cfg.get("REVIEW_MAX_BUDGET_USD", "1.00").strip() or "1.00",
                "--output-format", "json", "--permission-mode", "acceptEdits",
                # No tools and no --add-dir: stdin is the reviewer's only input. The list is
                # written out in full rather than left to the default, because an option the CLI
                # does not offer is accepted silently and a shorter list would look the same.
                "--disallowedTools", REVIEW_DISALLOWED,
                "--strict-mcp-config", "--mcp-config", str(run_dir / "mcp_empty.json"),
                "--no-session-persistence", "--setting-sources", "project"]
    else:
        args = review_argv(cfg["REVIEW_CMD"])
    (run_dir / "review_argv.txt").write_text("\n".join(args), encoding="utf-8")

    blocks, codes, wall = [], [], 0.0
    totals = {"tk_review_input": 0, "tk_review_output": 0, "tk_review_cache_write": 0,
              "tk_review_cache_read": 0, "tk_review_cost_usd": 0.0}
    for k in range(1, weight + 1):
        # A working directory of its own per reviewer, created empty for the call and left behind:
        # whatever a reviewer writes lands where it is evidence, never in the workspace about to be
        # scored, and two reviewers cannot see or overwrite each other's leftovers.
        suffix = "" if weight == 1 else "_%d" % k
        review_cwd = run_dir / ("review_cwd" + suffix)
        review_cwd.mkdir(parents=True, exist_ok=True)
        started = time.time()
        try:
            p = subprocess.run(args, cwd=str(review_cwd), input=stdin, text=True, encoding="utf-8",
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=cli_env(cfg, run_dir), timeout=CLI_TIMEOUT_S)
            out, err, rc = p.stdout or "", p.stderr or "", p.returncode
        except subprocess.TimeoutExpired as e:
            out = e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8",
                                                                                      "replace")
            err = e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8",
                                                                                      "replace")
            rc = "timeout"
        wall += time.time() - started
        codes.append(str(rc))
        # A reviewer that exits non-zero having printed nothing did not review: counting it as zero
        # findings and zero cost recorded a failed invocation as a clean review that found nothing,
        # and the feedback step then had nothing to fix. It is an error, and the counts are dropped
        # rather than reported partial (chapter 12, step 7b).
        if rc != 0 and not (out or "").strip():
            row["res_review_error"] = 1
        (run_dir / ("review_stderr%s.txt" % suffix)).write_text(err, encoding="utf-8")
        text = out
        if mode == "same_model":
            (run_dir / ("review%s.json" % suffix)).write_text(out, encoding="utf-8")
            data = result_record(out)
            text = ""
            if data is not None:
                text = data.get("result") or ""
                usage = data.get("usage") or {}
                for col, field in (("tk_review_input", "input_tokens"),
                                   ("tk_review_output", "output_tokens"),
                                   ("tk_review_cache_write", "cache_creation_input_tokens"),
                                   ("tk_review_cache_read", "cache_read_input_tokens")):
                    try:
                        totals[col] += int(usage.get(field) or 0)
                    except (TypeError, ValueError):
                        pass
                try:
                    totals["tk_review_cost_usd"] += float(data.get("total_cost_usd") or 0)
                except (TypeError, ValueError):
                    pass
        blocks.append(text)
    row["prf_review_s"] = round(wall, 1)
    if mode == "same_model":
        # Summed over the weight, not averaged: what the pass cost is what all its reviewers cost.
        row.update({k: v for k, v in totals.items() if k != "tk_review_cost_usd"})
        row["tk_review_cost_usd"] = round(totals["tk_review_cost_usd"], 6)
    # other_model leaves every tk_review_* blank: a foreign CLI's usage fields are not comparable
    # with this one's, and a number that is not comparable is worse than a blank (chapter 18).

    # One review.md whatever the weight. At weight 1 it is the reviewer's answer verbatim, as it
    # has always been; above 1 each block is introduced by `# reviewer k`, which carries no
    # Conventional Comments label and is therefore counted by nothing.
    if weight == 1:
        merged = blocks[0] if blocks else ""
    else:
        merged = "\n".join("# reviewer %d\n%s" % (i + 1, b.strip()) for i, b in enumerate(blocks))
    (run_dir / "review.md").write_text(merged, encoding="utf-8")
    if row["res_review_error"]:
        # Blank counts, not zeros: a zero says the reviewer read the diff and found nothing, which
        # is a measurement, and this pass produced none. Step 7c is skipped for the same reason.
        print("review: mode=%s weight=%d exit=%s ERROR -- an invocation exited non-zero with no "
              "output; counts blank, no fix call (see review_stderr*.txt)"
              % (mode, weight, ",".join(codes)))
        return row
    findings = issues = actionable = 0
    for line in merged.splitlines():
        m = REVIEW_LINE.match(line)
        if not m:
            continue
        findings += 1
        if m.group(1).lower() == "issue":
            issues += 1
            if changes_field(line):
                actionable += 1
    row["res_review_findings"] = findings
    row["res_review_issues"] = issues
    row["res_review_actionable"] = actionable
    print("review: mode=%s weight=%d exit=%s findings=%s issues=%s actionable=%s dur=%ss"
          % (mode, weight, ",".join(codes), findings, issues, actionable, row["prf_review_s"]))
    return row


def metric_value(path, key):
    """One key out of a metrics*.txt as text, blank when the file or the key is absent."""
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


def read_metrics(run_dir):
    """metrics.txt written by the oracle -> res_* columns (chapter 11)."""
    out = {}
    path = run_dir / "metrics.txt"
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            if k in METRIC_COLUMNS:
                out[METRIC_COLUMNS[k]] = v
    return out


def artifacts_present(template, workspace):
    """Which declared artifacts the agent actually produced -- adherence evidence.

    A name the project itself ships (04_python_xlarge's TASK_BACKLOG.md) is not evidence of anything:
    every arm would be credited with an artifact it was handed, so template-shipped names are
    filtered out and only what the agent added is listed.

    ARTIFACT_GLOBS covers the declared artifact that is a directory rather than a name: the ADR
    form of the D feature writes one record per decision, so `docs/adr/0001-*.md` is detected by
    its path and each record is listed under it (chapter 19.3).
    """
    found = [a for a in ARTIFACTS
             if (workspace / a).is_file() and not (template / a).is_file()]
    for pattern in ARTIFACT_GLOBS:
        for path in sorted(workspace.glob(pattern)):
            rel = path.relative_to(workspace).as_posix()
            if path.is_file() and not (template / rel).is_file():
                found.append(rel)
    return "|".join(found)


def diff_stats(template, workspace):
    """Files added, source files added, lines added and lines removed (chapter 19.1).

    res_files_added_src counts the added .py files alone. res_files_added conflates a scope
    violation with the Markdown artifacts the D methodologies are told to write, so it cannot
    carry a scope signal on its own.

    DIFF_EXCLUDED is out of all four figures: the deployed entry file is the harness's own, and
    PLAN.md, DECISIONS.md and SUMMARY.md are what the methodology asked for and res_artifacts
    already records. What is left is what the agent chose to write.
    """
    import difflib
    skip = {".venv", "__pycache__", ".git", ".pytest_cache"}

    def listing(root):
        out = {}
        for p in root.rglob("*"):
            rel = p.relative_to(root)
            if not p.is_file() or any(part in skip for part in rel.parts):
                continue
            name = str(rel).replace("\\", "/")
            if name in DIFF_EXCLUDED:
                continue
            out[name] = p
        return out
    tmpl, work = listing(template), listing(workspace)
    new = set(work) - set(tmpl)
    added = len(new)
    added_src = sum(1 for n in new if n.endswith(".py"))
    plus = minus = 0
    for name in sorted(set(tmpl) | set(work)):
        def lines(d, n):
            if n not in d:
                return []
            try:
                return d[n].read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                return []
        a, b = lines(tmpl, name), lines(work, name)
        for line in difflib.unified_diff(a, b, n=0):
            if line.startswith("+") and not line.startswith("+++"):
                plus += 1
            elif line.startswith("-") and not line.startswith("---"):
                minus += 1
    return added, added_src, plus, minus


def tamper_names(template):
    """The tamper set: the root test_*.py glob, the fixed config names, every file under fixtures/.

    A project whose format is defined by a fixture (04_python_xlarge) is otherwise passable by
    rewriting the file the code failed to parse, which would score 1.00 on the agent's own input.
    """
    return sorted({p.name for p in template.glob("test_*.py")} |
                  {n for n in FIXED_TAMPER if (template / n).is_file()} |
                  {p.relative_to(template).as_posix()
                   for p in template.glob("fixtures/*") if p.is_file()})


def restore_tamper(template, workspace, names):
    """Restore the tamper set from the template and report whether anything had been changed."""
    tampered = False
    for name in names:
        src, dst = template / name, workspace / name
        if not dst.is_file() or dst.read_bytes() != src.read_bytes():
            tampered = True
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return tampered


def step8_tamper_and_verify(project, template, workspace, run_dir):
    """Compare the tamper set, restore it from the template, copy the held-out suite, then score.

    This is the only restore that touches the scored workspace, under BEST_OF_N as well: the
    winner arrives here as its agent left it, so the comparison is the row's own evidence.
    """
    names = tamper_names(template)
    tampered = restore_tamper(template, workspace, names)
    rc = run_oracle(project, run_dir, workspace, baseline=False,
                    holdout=copy_holdout(project, run_dir))
    triple = read_triple(run_dir / "verification.txt")
    # The oracle deletes any pytest config or hook file the template does not ship and says so with
    # `config_tampered=1`: the restore above only puts template files back, so an *added* pytest.ini
    # or conftest.py is invisible to it and would otherwise leave res_tests_tampered false
    # (chapter 11). A timeout is reported the same way, and run.log is where it is said.
    config_tampered = metric_value(run_dir / "verification.txt", "config_tampered") == "1"
    if config_tampered:
        print("tamper: pytest config/hook file(s) not in the template were removed before scoring")
    if metric_value(run_dir / "verification.txt", "timeout") == "1":
        print("TIMEOUT: verification exceeded the oracle's own bound -- scored 0.00")
    # The oracle's own verdict, not a threshold on the score: a project with an extra gate
    # (05_python_refactor_large's strict reduction) can be fully green on the tests and still not
    # have done the task, and score == 1.0 would read that as a pass. Blank stays blank -- a
    # project that ships no tests measures nothing and must not report false.
    passed = "" if triple["score"] == "" else str(rc == 0).lower()
    added, added_src, plus, minus = diff_stats(template, workspace)
    out = {"res_tests_tampered": ("" if not names and not config_tampered
                                  else str(tampered or config_tampered).lower()),
            "res_files_added": added,
            "res_files_added_src": added_src,
            "res_diff_lines": plus + minus,
            "res_lines_added": plus,
            "res_lines_removed": minus,
            "res_artifacts": artifacts_present(template, workspace),
            "res_score": triple["score"],
            # The held-out fraction, unscaled and outside the gate: res_score - res_score_holdout
            # is the fitting-to-the-test measure (chapter 11). Blank when the project ships none.
            "res_score_holdout": triple["score_holdout"],
            "res_verification_passed": passed,
            "res_verification_error": str(rc == 2).lower(),
            "res_verification_exit": rc}
    out.update(read_metrics(run_dir))
    # The pre-flight metrics are already on disk; lifting the baseline SLOC into the row is what
    # makes res_sloc readable without opening the run directory -- 210 SLOC means one thing on a
    # 67-SLOC template and another on a 176-SLOC one. res_sloc_delta is the code actually written.
    out["res_sloc_baseline"] = metric_value(run_dir / "metrics_baseline.txt", "sloc")
    try:
        out["res_sloc_delta"] = int(out["res_sloc"]) - int(out["res_sloc_baseline"])
    except (KeyError, TypeError, ValueError):
        out["res_sloc_delta"] = ""
    return out


def step9_parse_and_write(cfg, run_dir, row):
    """Parse result.json, print the row and write results_run.csv."""
    blank = {c: "" for c in COLUMNS}
    blank.update(row)
    row = blank
    raw = (run_dir / "result.json").read_text(encoding="utf-8") if (run_dir / "result.json").is_file() else ""
    data = result_record(raw)

    if data is None:
        if not row.get("res_subtype"):
            row["res_subtype"] = "unparsable"
    else:
        usage = data.get("usage") or {}
        details = usage.get("output_tokens_details") or {}
        row["tk_input"] = usage.get("input_tokens", "")
        row["tk_output"] = usage.get("output_tokens", "")
        row["tk_thinking"] = details.get("thinking_tokens", "")
        row["tk_cache_write"] = usage.get("cache_creation_input_tokens", "")
        row["tk_cache_read"] = usage.get("cache_read_input_tokens", "")
        row["tk_cost_usd"] = data.get("total_cost_usd", "")
        turns = data.get("num_turns", "")
        row["prf_turns"] = turns
        cap = cfg.get("MAX_TURNS", "")
        row["res_hit_turn_cap"] = ("" if turns == "" or not cap
                                   else str(int(turns) >= int(cap)).lower())
        if not row.get("res_subtype"):
            row["res_subtype"] = data.get("subtype", "")
        stats = data.get("subagent_stats") or {}
        row["res_subagents_spawned"] = stats.get("spawned", "") if isinstance(stats, dict) else ""
        # A tool the --allowedTools list does not cover is denied silently. A compound shell
        # command such as `cd ...; python -m pytest` is not matched by a PowerShell(python:*)
        # rule and is denied whole, so the count separates an agent that skipped its tests from
        # a harness that blocked them.
        denials = data.get("permission_denials")
        row["res_permission_denials"] = len(denials) if isinstance(denials, list) else ""
        # modelUsage lists every model billed, including the small auxiliary model the CLI
        # uses for its own housekeeping (observed: a claude-haiku-4-5 entry alongside the
        # requested claude-opus-5). The first key is therefore not the model that did the
        # work; the entry that cost the most is.
        mu = data.get("modelUsage") or {}
        if isinstance(mu, dict) and mu:
            def spend(item):
                entry = item[1]
                if not isinstance(entry, dict):
                    return (0.0, 0)
                return (float(entry.get("costUSD") or 0), int(entry.get("outputTokens") or 0))
            key, entry = max(mu.items(), key=spend)
            row["res_model_served"] = entry.get("canonicalModel", key) if isinstance(entry, dict) else key
        ms = data.get("duration_ms")
        if isinstance(ms, (int, float)):
            row["prf_duration_s"] = round(ms / 1000.0, 1)

    with open(run_dir / "results_run.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow([csv_name(c) for c in COLUMNS])
        w.writerow([row[c] for c in COLUMNS])
    for c in COLUMNS:
        print("%s=%s" % (c, row[c]))
    return row


class Tee(object):
    """Mirror everything printed during a run into <run dir>/run.log (chapter 13.1).

    The console stays the live view; the file is the record that survives a closed window, and it
    is what makes an aborted or crashed run diagnosable after the fact.
    """

    def __init__(self, path):
        self.stream = sys.stdout
        self.fh = open(str(path), "a", encoding="utf-8")

    def write(self, text):
        self.stream.write(text)
        self.fh.write(text)

    def flush(self):
        self.stream.flush()
        self.fh.flush()

    def close(self):
        try:
            self.fh.close()
        except Exception:
            pass


def campaign_log(line):
    """Append one line per run to local/runs/_master.log -- the campaign-level history.

    Opened in append mode, one line, closed again: the file is shared by every matrix worker and is
    the one thing they write together, so it is never opened for writing and never held open. A
    short append is atomic on both platforms, which is what keeps two workers' lines whole.
    """
    path = RUNS / "_master.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), line))


def check_invocation(cfg):
    """The pre-flight checks that cannot come right on a later repeat (chapter 12).

    A config key of the wrong type, a `MODEL` alias, a flag this CLI does not offer, a reviewer
    command that is not on `PATH`, an entry file above the repository: each is exactly as wrong on
    repeat 3 as on repeat 1, so the invocation ends here instead of writing the same abort three
    times. Everything from the run directory onwards -- a venv that fails to build, a baseline that
    passes, an oracle environment error -- is recorded in that repeat and the loop continues.
    """
    check_config_keys(cfg)
    check_cli_flags(cfg, RUNS / "_cli_help.txt")
    check_review_config(cfg)
    check_ancestor_entry_files(RUNS / "_preflight" / "project_workspace",
                               RUNS / "_preflight_ancestors.txt")


def one_run(cfg, project, methodology, repeat, stamp):
    """One repeat. Returns 0, or the exit code of an abort that stops this repeat alone.

    An abort after the run directory exists is a fact about this repeat, not about the invocation:
    it is written to `abort.txt` beside the run's own `run.log`, logged in `_master.log`, and the
    caller starts the next repeat.
    """
    try:
        run_id, run_dir, stamp = step2_make_run_dir(methodology, project, repeat, stamp)
    except Abort as exc:
        # No run directory, so no abort.txt and no run.log: the campaign log is the only record.
        campaign_log("ABORT exit=%d %s" % (exc.code, exc.msg.replace("\n", " ")))
        return exc.code
    tee = Tee(run_dir / "run.log")
    saved_stdout, sys.stdout = sys.stdout, tee
    try:
        # Inside the try and read with .get: a missing key here would raise before the finally
        # existed and leave sys.stdout pointing at a closed Tee for the rest of the campaign.
        campaign_log("START %s model=%s effort=%s"
                     % (run_id, cfg.get("MODEL", ""), cfg.get("EFFORT", "")))
        _one_run_body(cfg, project, methodology, repeat, stamp, run_id, run_dir)
        return 0
    except Abort as exc:
        (run_dir / "abort.txt").write_text("exit=%d\n%s\n" % (exc.code, exc.msg), encoding="utf-8")
        campaign_log("ABORT %s exit=%d %s" % (run_id, exc.code, exc.msg.replace("\n", " ")))
        print("ABORT %s exit=%d -- see %s" % (run_id, exc.code, run_dir / "abort.txt"))
        return exc.code
    except BaseException as exc:
        campaign_log("ERROR %s %s: %s" % (run_id, type(exc).__name__, exc))
        raise
    finally:
        sys.stdout = saved_stdout
        tee.close()


def _one_run_body(cfg, project, methodology, repeat, stamp, run_id, run_dir):
    print("=== %s" % run_id)
    step3_snapshot_methodology(methodology, run_dir)
    template, workspace = step4_copy_workspace(project, run_dir)
    mth = step5_deploy_entry_file(run_dir, workspace)
    _, user_md, cli_version = step6_environment_and_preflight(cfg, project, template, workspace,
                                                              run_dir)
    baseline = read_triple(run_dir / "verification_baseline.txt")
    tools, cfg_tools = allowed_tools(methodology)
    n = best_of_n(cfg)
    bestof = {}
    if n > 1:
        best, bestof = step7a_best_of_n(cfg, project, run_dir, template, workspace, tools, n)
        wall, timed_out = best["wall"], best["timed_out"]
    else:
        wall, timed_out = step7_launch_cli(cfg, project, run_dir, workspace, tools)
    # 7b before 8: the reviewer must read the diff the agent left, not the one the tamper restore
    # produces, and it must not see the oracle's verdict on the code it is reviewing. Under
    # BEST_OF_N it reviews the chosen workspace alone.
    rev = step7b_review(cfg, project, run_dir, workspace, template)
    # 7c after 7b and before 8: the fix call acts on the review, and the oracle scores what it left.
    fix = step7c_feedback(cfg, project, run_dir, workspace, tools,
                          review_error=rev.get("res_review_error") == 1)
    res = step8_tamper_and_verify(project, template, workspace, run_dir)
    row = {"id_run": run_id, "id_timestamp": stamp, "id_repeat": repeat, "prj_name": project,
           "mth_name": methodology,
           "cfg_campaign": cfg["CAMPAIGN"],
           "cfg_engine": cfg["ENGINE"], "cfg_cli_version": cli_version,
           "cfg_model": cfg["MODEL"], "cfg_effort": cfg["EFFORT"],
           "cfg_user_claude_md": user_md,
           "cfg_review_pass": cfg["REVIEW_PASS"], "cfg_review_model": review_model(cfg),
           "cfg_fix_model": fix_model(cfg),
           "cfg_review_prompt": ("" if cfg["REVIEW_PASS"] == "none"
                                 else review_prompt_path(cfg).name),
           "cfg_review_weight": ("" if cfg["REVIEW_PASS"] == "none" else review_weight(cfg)),
           "cfg_tools": cfg_tools,
           "res_score_baseline": baseline["score"],
           "prf_duration_s": round(wall, 1)}
    row.update(mth)
    row.update(bestof)
    row.update(rev)
    row.update(fix)
    row.update(res)
    if timed_out:
        row["res_subtype"] = "harness_timeout"
    out = step9_parse_and_write(cfg, run_dir, row)
    campaign_log("DONE  %s score=%s passed=%s usd=%s turns=%s dur=%ss" % (
        run_id, out.get("res_score", ""), out.get("res_verification_passed", ""),
        out.get("tk_cost_usd", ""), out.get("prf_turns", ""), out.get("prf_duration_s", "")))
    return out


def read_table(path):
    """The published results_repository.csv as a list of records, empty when there is none."""
    if not path.is_file():
        return []
    with open(str(path), newline="", encoding="utf-8") as fh:
        return [{plain_name(k): v for k, v in rec.items() if k} for rec in csv.DictReader(fh)]


def consolidate():
    """Merge every local/runs/*/results_run.csv into results_repository.csv.

    Rows are matched by column name, not by position, and a column a run predates is left blank.
    A schema change therefore never orphans earlier runs (chapter 13).

    **The published table is an input, not only an output.** `local/runs/` is git-ignored, so a
    fresh checkout has none of the runs behind the published rows: rebuilding from the run
    directories alone emptied the table on the first consolidation after a clone. Every row already
    in the table whose `id_run` has no local `results_run.csv` is therefore kept as it stands, and a
    local run overwrites the row of the same id. `local/runs_archive/` is still not read.

    A repeat that aborted has no results_run.csv and contributes no row, which is correct and
    invisible -- so the count is printed: a campaign that expected 42 rows and got 40 must not have
    to notice that on its own.
    """
    paths = sorted((RUNS).glob("*/results_run.csv"))
    aborted = sorted(p.parent.name for p in (RUNS).glob("*/abort.txt"))
    records, seen = [], []

    def note(rec):
        for k in rec:
            if k not in seen:
                seen.append(k)

    # Order: the published rows first, as they stand, then the local runs -- a local row replaces
    # the table row of the same id in place, so a re-consolidation does not reshuffle the file.
    index = {}
    for rec in read_table(RESULTS_TABLE):
        note(rec)
        index[rec.get("id_run", "")] = len(records)
        records.append(rec)
    kept = len(records)
    from_runs = 0
    for p in paths:
        with open(str(p), newline="", encoding="utf-8") as fh:
            for rec in csv.DictReader(fh):
                rec = {plain_name(k): v for k, v in rec.items() if k}
                note(rec)
                from_runs += 1
                rid = rec.get("id_run", "")
                if rid and rid in index:
                    kept -= 1
                    records[index[rid]] = rec
                else:
                    index[rid] = len(records)
                    records.append(rec)
    # The header is COLUMNS whole, plus anything a row carries that COLUMNS does not. Writing only
    # the columns some row had left the published table one column short of the schema for as long
    # as no run had produced the new one, and chapter 13 states the header *is* COLUMNS: a reader
    # comparing the file against the chapter would have found a column missing rather than blank.
    columns = list(COLUMNS) + [c for c in seen if c not in COLUMNS]
    out = RESULTS_TABLE
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(str(out), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow([csv_name(c) for c in columns])
        for rec in records:
            w.writerow([rec.get(c, "") for c in columns])
    missing = [c for c in COLUMNS if c not in seen]
    print("wrote %s (%d rows, %d columns)" % (out, len(records), len(columns)))
    print("  %d row(s) kept from the published table, %d from local/runs" % (kept, from_runs))
    for line in mixed_campaign_report(records):
        print("  %s" % line)
    if missing:
        # Informational: the column is in the header with a blank cell in every row, which is what
        # a column no run has produced yet looks like. Not a warning -- nothing is missing.
        print("  blank in every row (no run carries them yet): %s" % ", ".join(missing))
    if aborted:
        print("  aborted repeats: %d (see local/runs/<id>/abort.txt)" % len(aborted))
        for run_id in aborted:
            print("    %s" % run_id)


GATE_ANCHOR_MTH = "00_sabotage"
GATE_INCUMBENT_MTH = "08_process_doctypes_roles_guardrails"
# The incumbent's name before it was spelled out. Rows written under the old name are still on
# disk and are still the incumbent's rows, so the gate reads both and pools them (chapter 16); a
# rename that quietly dropped a campaign's baseline arm would report "no incumbent rows" as PASS.
GATE_INCUMBENT_LEGACY = "08_all"
GATE_ANCHOR_PRJ = "00_fail"


# Chapter 17 forbids pooling rows whose constants differ, and cfg_campaign is only the config
# file's base name: two different files of the same name, or one edited between two runs, share the
# label. These are the columns one campaign must agree on for the label to mean anything.
CAMPAIGN_CONSTANTS = ("cfg_model", "cfg_effort", "cfg_review_pass", "cfg_review_model",
                      "cfg_fix_model", "cfg_review_weight", "cfg_tools")


def mixed_constants(rows):
    """The CAMPAIGN_CONSTANTS columns on which these rows disagree -> the differing values.

    Empty when the rows really are one campaign. A non-empty result means the label is pooling runs
    chapter 17 says are two treatments, which no column can repair after the fact.
    """
    out = {}
    for col in CAMPAIGN_CONSTANTS:
        values = sorted({(r.get(col) or "").strip() for r in rows})
        if len(values) > 1:
            out[col] = values
    return out


def mixed_campaign_report(rows):
    """One line per campaign whose rows disagree on a constant -- printed by --consolidate."""
    groups = {}
    for r in rows:
        groups.setdefault((r.get("cfg_campaign") or "(no cfg_campaign)").strip(), []).append(r)
    lines = []
    for campaign in sorted(groups):
        mixed = mixed_constants(groups[campaign])
        if mixed:
            lines.append("MIXED campaign %s: %s (chapter 17 -- these rows are not one campaign)"
                         % (campaign, "; ".join("%s=%s" % (c, "|".join(v))
                                                for c, v in sorted(mixed.items()))))
    return lines


def median(values):
    """The middle value, the mean of the two middle ones on an even count. None on no values."""
    s = sorted(values)
    if not s:
        return None
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


def as_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def strict_reduction_projects():
    """The projects whose oracle sets REQUIRE_SMALLER_THAN_BASELINE (chapter 11).

    Read from the oracles rather than listed here: on such a project the pristine baseline passes
    its tests and pre-flight fails on the gate instead, so `res_score_baseline` of 1.00 is the
    expected value there and nowhere else.
    """
    out = set()
    for path in sorted((ROOT / "projects").glob("*/run_verification.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"REQUIRE_SMALLER_THAN_BASELINE\s*=\s*True", text):
            out.add(path.parent.name)
    return out


def gate(campaign=None, apparatus_only=False):
    """Print the three chapter-16 conditions per campaign, PASS or FAIL, with their numbers.

    It reads `results_repository.csv` and nothing else, and groups by `cfg_campaign`: the
    conditions are statements about one set of rows sharing its constants, and pooling two
    campaigns would compare a sabotage run of one against an incumbent run of the other. It is the
    validity check chapter 16 demands, printed after every rebuild -- not an analysis: no ranking,
    no cost, no pivot. Exit 0 when every campaign holds, 1 when one does not.

    `campaign` narrows it to one label; `apparatus_only` drops the first condition, which needs
    ranking rows the cheap campaign was never meant to buy, and adds the one the cheap campaign
    exists to answer: no repeat aborted and no row carries a `res_subtype` other than `success`
    (chapter 16).

    Two verdicts other than PASS/FAIL exist, and both exit 1. A campaign whose rows disagree on the
    constants chapter 17 pools by is MIXED: the label is the config file's base name, so an edited
    file or a second file of that name shares it, and no condition over pooled rows means anything.
    A ranking project that has one anchor of condition 1 but not the other is INCOMPLETE: skipping
    it silently let a campaign missing half its gate print PASS.
    """
    path = RESULTS_TABLE
    if not path.is_file():
        print("gate: %s not found -- run --consolidate first" % path.name)
        return 2
    with open(str(path), newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)]
    groups = {}
    for r in rows:
        groups.setdefault((r.get("cfg_campaign") or "(no cfg_campaign)").strip(), []).append(r)
    if campaign is not None:
        groups = {k: v for k, v in groups.items() if k == campaign}
        if not groups:
            print("gate: no rows for campaign %s" % campaign)
            return 1
    gated = strict_reduction_projects()
    print("gate: %s, %d row(s), %d campaign(s)%s"
          % (path.name, sum(len(v) for v in groups.values()), len(groups),
             " -- apparatus only" if apparatus_only else ""))
    ok = True

    # The rollup word, most severe first: MIXED (the rows are not one campaign, so nothing
    # computed over them means anything) beats INCOMPLETE (a condition could not be judged)
    # beats FAIL beats PASS. Only PASS exits 0.
    mixed_any = incomplete = False

    def verdict(passed, title, detail, label=None):
        print("  %s  %s" % (label or ("PASS" if passed else "FAIL"), title))
        for line in detail:
            print("        %s" % line)
        return passed

    for campaign in sorted(groups):
        rs = groups[campaign]
        print("")
        print("campaign %s -- %d row(s)" % (campaign, len(rs)))

        # Before any condition: one label must stand for one set of constants (chapter 17). Rows
        # that disagree are two campaigns wearing one name, and a condition over them is arithmetic
        # on a mixture rather than a statement about a campaign.
        mixed = mixed_constants(rs)
        if mixed:
            mixed_any = True
            ok &= verdict(False, "the campaign's rows share their constants",
                          ["%s: %s" % (c, " | ".join(v or "(blank)" for v in vals))
                           for c, vals in sorted(mixed.items())]
                          + ["chapter 17: rows differing on these columns are not pooled"],
                          label="MIXED")

        detail, verdicts = [], []
        projects = ([] if apparatus_only
                    else sorted({r.get("prj_name", "") for r in rs} - {GATE_ANCHOR_PRJ}))
        half = []
        for prj in projects:
            def scores(*names):
                return [s for s in (as_float(r.get("res_score"))
                                    for r in rs
                                    if r.get("prj_name") == prj and r.get("mth_name") in names)
                        if s is not None]
            bad = scores(GATE_ANCHOR_MTH)
            good = scores(GATE_INCUMBENT_MTH, GATE_INCUMBENT_LEGACY)
            if not bad and not good:
                # Not a ranking project of this campaign at all -- the smoke run on
                # 01_python_small carries neither anchor and is not a gap in the gate.
                continue
            if not bad or not good:
                # One anchor and not the other: the comparison cannot be made, and skipping the
                # project let a campaign missing half its gate print PASS (chapter 16).
                half.append("%s: %s rows=%d, %s rows=%d -- the other anchor is missing"
                            % (prj, GATE_ANCHOR_MTH, len(bad), GATE_INCUMBENT_MTH, len(good)))
                continue
            m_bad, m_good = median(bad), median(good)
            verdicts.append(m_bad < m_good)
            detail.append("%s: median res_score %s %.3f (n=%d) vs %s %.3f (n=%d)"
                          % (prj, GATE_ANCHOR_MTH, m_bad, len(bad),
                             GATE_INCUMBENT_MTH, m_good, len(good)))
            if not m_bad < m_good:
                detail[-1] += "  <-- sabotage does not lose"
        if not detail:
            detail.append("no project with both %s and %s rows" % (GATE_ANCHOR_MTH,
                                                                   GATE_INCUMBENT_MTH))
        if not apparatus_only:
            if half:
                incomplete = True
                ok &= verdict(False,
                              "%s scores worse than %s" % (GATE_ANCHOR_MTH, GATE_INCUMBENT_MTH),
                              detail + half, label="INCOMPLETE")
            else:
                ok &= verdict(bool(verdicts) and all(verdicts),
                              "%s scores worse than %s" % (GATE_ANCHOR_MTH, GATE_INCUMBENT_MTH),
                              detail)

        fails = [r for r in rs if r.get("prj_name") == GATE_ANCHOR_PRJ]
        passing = [r["id_run"] for r in fails if (r.get("res_verification_passed") or "") == "true"]
        detail = ["%d %s row(s), res_verification_passed=true on %d"
                  % (len(fails), GATE_ANCHOR_PRJ, len(passing))]
        detail += ["  %s" % rid for rid in passing]
        ok &= verdict(bool(fails) and not passing,
                      "%s never reaches res_verification_passed" % GATE_ANCHOR_PRJ, detail)

        judged = [r for r in rs if as_float(r.get("res_score_baseline")) is not None]
        offenders = [r["id_run"] for r in judged
                     if as_float(r["res_score_baseline"]) >= 1.0 and r.get("prj_name") not in gated]
        detail = ["%d row(s) with a baseline score, %d at 1.00 outside the strict-reduction gate "
                  "(%s)" % (len(judged), len(offenders), ", ".join(sorted(gated)) or "none")]
        detail += ["  %s" % rid for rid in offenders]
        ok &= verdict(bool(judged) and not offenders,
                      "the pristine baseline fails pre-flight", detail)

        if apparatus_only:
            # An aborted repeat writes no row, so it carries no campaign and the count is over
            # `local/runs/` whole. That is the conservative reading and the right one here: the question
            # is whether the machine is fit to run a more expensive campaign, and an abort left
            # behind by anything is an answer to it.
            aborted = sorted(p.parent.name for p in (RUNS).glob("*/abort.txt"))
            bad = [r.get("id_run", "") for r in rs
                   if (r.get("res_subtype") or "").strip() != "success"]
            detail = ["%d aborted repeat(s) under local/runs/ (no row, so no campaign to filter by)"
                      % len(aborted)]
            detail += ["  %s" % rid for rid in aborted]
            detail.append("%d row(s) with res_subtype other than success" % len(bad))
            detail += ["  %s" % rid for rid in bad]
            ok &= verdict(not aborted and not bad,
                          "no aborted repeat and no res_subtype other than success", detail)

    print("")
    if ok and groups:
        rollup = "PASS"
    elif mixed_any:
        rollup = "MIXED"
    elif incomplete:
        rollup = "INCOMPLETE"
    else:
        rollup = "FAIL"
    print("gate: %s" % rollup)
    return 0 if (ok and groups) else 1


# Seconds between two worker starts. The CLI's own start-up is the contended part -- config,
# credentials, an MCP handshake -- and starting N workers on the same instant is the one moment a
# matrix can trip over itself for a reason that has nothing to do with the runs.
MATRIX_STAGGER_S = 2.0


def pop_option(args, name):
    """Take `--name <value>` out of args. Returns (value, remaining); None when the flag is absent.

    A flag given without a value returns "", which every caller treats as a usage error -- the same
    exit 2 as too few arguments, since a matrix launched on a half-written flag is not a matrix.
    """
    if name not in args:
        return None, args
    i = args.index(name)
    if i + 1 >= len(args) or args[i + 1].startswith("--"):
        return "", args[:i] + args[i + 1:]
    return args[i + 1], args[:i] + args[i + 2:]


def matrix_names(kind, wanted):
    """The directory listing under `kind`, sorted, minus names starting with `_`, minus what
    `wanted` does not name.

    The listing is the matrix, exactly as the two `for /d` loops it replaces read it: a new project
    or methodology joins by existing. A leading `_` is what marks a directory that is not an arm --
    the harness's own `local/runs/_*` convention, applied here so scratch can live beside the real thing.
    """
    names = sorted(p.name for p in (ROOT / kind).iterdir()
                   if p.is_dir() and not p.name.startswith("_"))
    if wanted is None:
        return names
    picked = [n.strip() for n in wanted.split(",") if n.strip()]
    unknown = [n for n in picked if n not in names]
    if unknown:
        die("ABORT: no such %s: %s" % (kind, ", ".join(unknown)), 2)
    return [n for n in names if n in picked]


def row_counts():
    """How many rows are on disk per (prj_name, mth_name, cfg_campaign).

    Read from the runs rather than from `results_repository.csv`, which is rebuilt after the matrix
    and would therefore be a snapshot of the run before. It is what `--skip-existing` filters on and
    what decides whether a pair produced a row.
    """
    out = {}
    for path in sorted((RUNS).glob("*/results_run.csv")):
        try:
            with open(str(path), newline="", encoding="utf-8") as fh:
                for rec in csv.DictReader(fh):
                    rec = {plain_name(k): v for k, v in rec.items() if k}
                    key = (rec.get("prj_name", ""), rec.get("mth_name", ""),
                           rec.get("cfg_campaign", ""))
                    out[key] = out.get(key, 0) + 1
        except OSError:
            continue
    return out


def matrix_drain(fh, worker, rc):
    """Move one finished worker's captured output into the matrix log, prefixed by its pair.

    Each worker writes to a private temporary file and its lines are copied here when it exits, so
    one log holds every run and no two workers interleave a line. The prefix is what makes the file
    readable at N workers: every line says which pair produced it.
    """
    prefix = "%s %s | " % worker["pair"]
    worker["tmp"].seek(0)
    for line in worker["tmp"]:
        fh.write(prefix + line.rstrip("\r\n") + "\n")
    fh.write("%sexit=%d dur=%ss\n" % (prefix, rc, round(time.time() - worker["started"], 1)))
    fh.flush()
    worker["tmp"].close()


def run_matrix(args):
    """`--matrix`: run the whole pair list, then consolidate and gate (chapter 12).

    One implementation of the matrix, which `run_all_model_04.bat` and `run_turbo_model_01.bat` both call: two nested
    `for /d` loops in a batch file cannot skip what has already run, cannot run two pairs at once
    and cannot say at the end how many rows they produced. Each pair is one `run_master.py P M`
    subprocess and runs once; `REPEATS` applies inside it, as it always has.

    Workers are subprocesses, not threads: a run is a chain of subprocesses of its own and its state
    is a directory, so N workers are N independent invocations that share only `local/runs/_master.log`,
    which is appended to a line at a time. They start `MATRIX_STAGGER_S` apart and the queue is
    handed out one pair at a time to whichever worker is free, so a slow pair delays nothing but
    itself. `--workers 1` is the sequential matrix the batch files ran.

    Exit 0 when every pair produced at least one row, 1 otherwise. The gate's own verdict is printed
    but does not decide it: a matrix answers "did every pair run", chapter 16 answers "is the
    apparatus sound", and folding the two would make a red gate look like a broken sweep.
    """
    config, args = pop_option(args, "--config")
    workers_txt, args = pop_option(args, "--workers")
    projects_txt, args = pop_option(args, "--projects")
    mths_txt, args = pop_option(args, "--methodologies")
    skip_existing = "--skip-existing" in args
    args = [a for a in args if a != "--skip-existing"]
    if args or "" in (config, workers_txt, projects_txt, mths_txt):
        print(__doc__)
        return 2
    if workers_txt is not None and (not workers_txt.isdigit() or int(workers_txt) < 1):
        print("ABORT: --workers takes an integer >= 1 (got %r)" % workers_txt)
        return 2
    workers = int(workers_txt or "1")
    config = config or DEFAULT_CONFIG

    try:
        # The config is read here for its name and for the keys that are wrong for every pair
        # alike; each run reads it again for itself. A campaign that would abort 174 times aborts
        # once instead.
        cfg = step1_read_config(config)
        check_config_keys(cfg)
        pairs = [(p, m) for p in matrix_names("projects", projects_txt)
                 for m in matrix_names("methodology", mths_txt)]
    except Abort as exc:
        return exc.code
    campaign = cfg["CAMPAIGN"]

    before = row_counts()
    if skip_existing:
        pairs = [(p, m) for p, m in pairs if not before.get((p, m, campaign))]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = RUNS / ("_matrix_%s_%s.log" % (campaign, stamp))
    log.parent.mkdir(parents=True, exist_ok=True)
    before_aborts = len(list((RUNS).glob("*/abort.txt")))
    print("matrix: campaign %s, %d pair(s), %d worker(s), log %s"
          % (campaign, len(pairs), workers, log.name))

    queue, running, last_start, done = list(pairs), [], 0.0, 0
    fh = open(str(log), "a", encoding="utf-8")
    try:
        while queue or running:
            for w in list(running):
                rc = w["proc"].poll()
                if rc is None:
                    continue
                running.remove(w)
                done += 1
                matrix_drain(fh, w, rc)
                print("matrix: [%d/%d] %s %s exit=%d dur=%ss"
                      % (done, len(pairs), w["pair"][0], w["pair"][1], rc,
                         round(time.time() - w["started"], 1)))
            while (queue and len(running) < workers
                   and time.time() - last_start >= MATRIX_STAGGER_S):
                prj, mth = queue.pop(0)
                tmp = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
                proc = subprocess.Popen(
                    [sys.executable, str(ROOT / "run_master.py"), prj, mth, "--config", config],
                    cwd=str(ROOT), stdout=tmp, stderr=subprocess.STDOUT, env=child_env())
                last_start = time.time()
                running.append({"pair": (prj, mth), "proc": proc, "tmp": tmp,
                                "started": last_start})
                print("matrix: start %s %s" % (prj, mth))
            if queue or running:
                time.sleep(0.5)
    finally:
        fh.close()

    after = row_counts()
    produced = sum(after.values()) - sum(before.values())
    aborts = len(list((RUNS).glob("*/abort.txt"))) - before_aborts
    missing = [(p, m) for p, m in pairs
               if after.get((p, m, campaign), 0) <= before.get((p, m, campaign), 0)]
    print("")
    print("matrix: pairs run %d, rows produced %d, aborts %d" % (len(pairs), produced, aborts))
    for prj, mth in missing:
        print("  no row: %s %s" % (prj, mth))
    print("")
    consolidate()
    print("")
    gate()
    return 1 if missing else 0


def main():
    args = [a for a in sys.argv[1:] if a != ""]
    if args and args[0] == "--consolidate":
        consolidate()
        return 0
    if args and args[0] == "--matrix":
        return run_matrix(args[1:])
    if args and args[0] == "--gate":
        rest = args[1:]
        campaign, rest = pop_option(rest, "--campaign")
        apparatus_only = "--apparatus-only" in rest
        rest = [a for a in rest if a != "--apparatus-only"]
        # --apparatus-only names two of the three conditions plus one of its own, and all three
        # are statements about one campaign's rows, so it has no meaning without --campaign.
        if rest or campaign == "" or (apparatus_only and campaign is None):
            print(__doc__)
            return 2
        return gate(campaign, apparatus_only)
    config = DEFAULT_CONFIG
    if "--config" in args:
        i = args.index("--config")
        if i + 1 >= len(args):
            print(__doc__)
            return 2
        config = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) != 2:
        print(__doc__)
        return 2
    project, methodology = args
    try:
        cfg = step1_read_config(config)
        check_invocation(cfg)
    except Abort as exc:
        campaign_log("ABORT exit=%d %s" % (exc.code, exc.msg.replace("\n", " ")))
        return exc.code
    repeats = int(cfg.get("REPEATS", "1"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # The exit code is the worst abort seen, and 0 only if every repeat produced a row. The loop
    # itself does not stop: two rows and one recorded abort are worth more than one row.
    worst = 0
    for r in range(1, repeats + 1):
        worst = max(worst, one_run(cfg, project, methodology, r, stamp))
    return worst


if __name__ == "__main__":
    sys.exit(main())
