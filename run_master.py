#!/usr/bin/env python3
"""OpenAgentsGym harness -- oam_targetpicture.md chapters 12 and 13. Stdlib only, Python >= 3.9.

    py -3 run_master.py <project> <methodology> [--config <path>]
    py -3 run_master.py --matrix [--config <path>] [--workers N] [--skip-existing]
                                 [--projects a,b] [--methodologies x,y]
    py -3 run_master.py --consolidate
    py -3 run_master.py --gate [--campaign <name>] [--apparatus-only]

--config selects the campaign constants file. The files are the four capability levels
.llm_config.e01_claude_haiku_4_5 .. .llm_config.e04_claude_fable_5_1 (chapter 9); the default is .llm_config.e02_claude_sonnet_5, and a
relative path is resolved against the repository root.
"""
import ast
import csv
import json
import math
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
# Capability levels (chapter 9): .llm_config.e01_claude_haiku_4_5 (cheapest, apparatus checks) .. e04_claude_fable_5_1
# (above the frontier tier). Level 2 is the default here; the model id lives only in the file.
DEFAULT_CONFIG = ".llm_config.e02_claude_sonnet_5"
# Run directories live under local/ too: they are per-run artifacts and account data, never source.
RUNS = LOCAL / "runs"
IS_WIN = os.name == "nt"
PARAM_KEYS = ("definition_of_done", "constraint_order", "doc_types",
              "review_rounds", "gate_style", "phase_budget", "retry_policy")
FIXED_TAMPER = ("conftest.py", "pytest.ini", "pyproject.toml", ".requirements", ".environment")
PLACEHOLDER = re.compile(r"\{\{([a-z_]+)=([^}]*)\}\}")
VERSION_RE = re.compile(r"<!--\s*mth_version:\s*(.*?)\s*-->")
# Raised from 3600 to 4h on 2026-09-13. gpt-oss-20b reached this bound on
# p03_python_large while still working (52 turns, 135 diff lines, score 0.8000
# partial), so the old value was measuring the harness rather than the model.
#
# THIS IS A CAMPAIGN CONSTANT. Every local row taken before this date ran under
# 3600 s, and a row censored at 3600 s is not comparable with one censored at
# 14400 s -- a `harness_timeout` row says "we stopped it", not "it failed".
# Rows on either side of this change must not be pooled. Since 2026-09-14 the
# value is written to cfg_walltime_s on every row and is a CAMPAIGN_CONSTANT, so
# the gate names such a mix instead of the reader having to know the date. Rows
# written before that column exists are blank, which the gate also names.
CLI_TIMEOUT_S = 4 * 3600
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
TOOL_LINE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\*?(\(.*\))?$")
# Conventional Comments (chapter 19.4) is what makes the findings a count rather than a guess.
# A model asked for bare lines still reaches for a bullet and a capital, and a finding lost to
# formatting is a miscount, not a stricter measurement -- so a leading markdown bullet and the
# label's case are tolerated. The label itself is not: a line without one is not a finding.
REVIEW_LINE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(issue|nitpick|question|praise)\s*:", re.I)
# The optional `changes=` suffix a finding may carry (lib/reviewer_prompt.md, and the schema
# m17_finding_schema deploys). It runs to the next `key=` field or to the end of the line, so it
# reads the same whether the schema puts `confidence=` after it or nothing does. `changes=none` is
# how the schema says a finding needs no edit, so it is not actionable and neither is a blank one.
CHANGES_FIELD = re.compile(r"\bchanges\s*=\s*(.*?)(?=\s+[a-z_]+\s*=|$)", re.I)
# The reviewer is stdin-only: no tools at all, so it cannot read the entry file, the methodology's
# own PLAN.md/DECISIONS.md/SUMMARY.md, or anything else the implementer left behind.
REVIEW_DISALLOWED = "Read,Edit,Write,Glob,Grep,Bash,PowerShell,Agent,WebFetch,WebSearch"
# Between the three parts of the reviewer's stdin. A rule the reviewer prompt itself states.
REVIEW_SEP = "\n\n" + "-" * 70 + "\n\n"

# --------------------------------------------------------------------------------------------
# The engine registry (chapter 18, "GPT branch"). One table, read by every site that used to
# name a vendor.
#
# Until now `claude` was not a choice, it was the harness: the binary name, the entry file the
# methodology is deployed as, the flags on the launch line, the environment variables that move
# the endpoint, the shape of the JSON that comes back and even the rule for what counts as a
# canonical model id were all written out in place. Each of those was a separate reason the file
# could only run one CLI, and a second engine added by editing them one at a time would leave
# thirteen places that must agree and no way to see whether they do. They are gathered here
# instead: an engine is a row in this table, and a site that differs between engines reads the
# row rather than testing the name. The dispatch that is left -- `engine_implementer_argv` and
# `engine_result_record` -- is two functions, because an argv list and a stdout format are not
# data and pretending otherwise would only move the branch somewhere harder to find.
#
# The `claude` row is a transcription, not a redesign: every value in it is the literal that
# stood at the site it replaces. 95 published rows were produced by that path and must stay
# comparable with the rows produced after this change, so the row is the one part of this table
# that is not free to be improved.
#
# Fields:
#   binary        the executable resolve_cli() looks for on PATH.
#   entry_file    what methodology/copy_to_root/agents_or_claude.md is deployed as. The source
#                 file is named for both because the text was always portable; only the
#                 destination waited.
#   prompt_via    "stdin" or "argv" -- where the project prompt is handed to the CLI.
#   help_argv     the argv that prints the help text check_cli_flags validates against. Not
#                 every CLI puts its run flags in the top-level help; opencode puts them under
#                 the subcommand, so the probe follows the CLI rather than the probe deciding
#                 the CLI is unvalidatable.
#   required_flags / review_flags  the options that must appear in that help text.
#   config_dir_env / base_url_env  the two environment variables a campaign may move. None
#                 means this engine offers no such knob, and the config key is then rejected
#                 rather than set and silently ignored.
#   fallback_keys the env/config keys that would substitute a model silently (check_model).
#   model_rule    which id shape reject_alias enforces (see that function).
#   native_provider  the value of PROVIDER that means "this engine's own endpoint".
#   effort_enforced  whether `--effort` (or an equivalent) actually reaches the model.
#   native_bound  what cfg_bound reads when the run is served natively -- the cap that really
#                 binds the run, not the cost figure that merely gets reported.
#   allowed_tools whether the engine takes an --allowedTools list at all; see tools_note.
#   tested        False marks an engine whose row has never been run end to end.
# --------------------------------------------------------------------------------------------
ENGINES = {
    "claude": {
        "binary": "claude",
        "entry_file": "CLAUDE.md",
        "prompt_via": "stdin",
        "help_argv": ("--help",),
        "version_argv": ("--version",),
        "required_flags": REQUIRED_FLAGS,
        "review_flags": REVIEW_FLAGS,
        "config_dir_env": "CLAUDE_CONFIG_DIR",
        "base_url_env": "ANTHROPIC_BASE_URL",
        "fallback_keys": ("CLAUDE_FALLBACK_MODEL",),
        "model_rule": "anthropic_canonical",
        "native_provider": "anthropic",
        "effort_enforced": True,
        "native_bound": "usd",
        "allowed_tools": True,
        "launch_style": "claude",
        "result_style": "claude",
        "tested": True,
        # The grammar of methodology/<M>/tools.txt and projects/<P>/tools.txt is this CLI's
        # `Name` / `Name(pattern)` form, and those files live outside this harness: they are the
        # arms' own material and are not rewritten for a second engine.
        "tools_note": "--allowedTools, Name(pattern) grammar as written in tools.txt",
    },
    "opencode": {
        "binary": "opencode",
        # opencode reads AGENTS.md, the cross-vendor name. Nothing in the entry file's text is
        # vendor-specific, so the same methodology deploys unchanged under a different name.
        "entry_file": "AGENTS.md",
        # `opencode run "<prompt>"` takes the task as a positional argument. Handing it on stdin
        # instead would start an interactive session with an empty task, which is not the same
        # run with a different pipe -- it is no run at all.
        "prompt_via": "argv",
        # The top-level help lists subcommands; the flags the launch line uses belong to `run`.
        # Probing the top-level help would report every flag missing and probing nothing would
        # drop the check, so the probe is the subcommand's own help.
        "help_argv": ("run", "--help"),
        "version_argv": ("--version",),
        # Only what the launch line actually passes. There is no budget flag, no effort flag,
        # no permission mode and no tool allowlist to require: an engine is checked against the
        # line it is launched with, never against another engine's line.
        "required_flags": ("--format", "-m"),
        "review_flags": (),
        "config_dir_env": None,
        "base_url_env": None,
        "fallback_keys": (),
        "model_rule": "provider_slash_model",
        # A run is addressed to `provider/model` and the provider is part of the id, so there is
        # no endpoint that is "opencode's own" the way there is one for a first-party CLI.
        # PROVIDER is therefore declared, as it is for any gateway, and never assumed.
        "native_provider": "",
        # No effort knob on the launch line. cfg_effort would otherwise read as a treatment that
        # never happened (see engine_columns).
        "effort_enforced": False,
        # Cost IS reported per step (LiteLLM prices it upstream), but a figure that is reported
        # is not a cap that binds: there is no per-run budget flag to stop a run at it. The only
        # thing that actually ends a runaway run here is CLI_TIMEOUT_S. See engine_columns.
        "native_bound": "walltime",
        "allowed_tools": False,
        "launch_style": "opencode",
        "result_style": "opencode_stream",
        # True since 2026-09-12. opencode 1.18.30 has now been run end to end through this
        # harness -- project, methodology, oracle, row -- twenty times across p01_python_small
        # and p03_python_large with all three local models. The launch line and the stdout
        # contract were observed first (`run --format json -m provider/model`, prompt
        # positional, newline-delimited JSON, exit 0 clean / 1 failed), and
        # stream_result_record was rewritten against that capture when two of its assumptions
        # proved wrong: accounting is nested under `part`, and no event carries a model id.
        #
        # What the campaign then settled, which the CLI capture could not: AGENTS.md IS picked
        # up from the workspace (cfg_entry_file records it on every row), the agent's own test
        # run works without --add-dir, verification and scoring produce real values (0.953 on
        # p01 with qwen3-4b), and a 24-turn stream accumulates its token counts correctly
        # (tk_input in the hundreds of thousands).
        #
        # One thing is still unobserved and is NOT what this flag covers: every opencode run so
        # far used a local model priced at zero, so tk_cost_usd has never been non-zero on this
        # engine. The per-step accounting is exercised; the arithmetic on a paid model is not.
        "tested": True,
        # tools.txt is not translated. Its grammar is the other CLI's, opencode has no equivalent
        # allowlist on the run line, and a silent partial translation would make cfg_tools claim
        # a restriction the run did not have. An arm that ships tools.txt still records it in
        # cfg_tools -- the column says what was asked for -- but nothing is passed to the CLI.
        "tools_note": "tools.txt recorded in cfg_tools, not enforced: no allowlist flag",
    },
    "gpt": {
        # STRUCTURAL ONLY -- NEVER EXECUTED. The codex CLI is not installed on the machine this
        # was written on, so every value below is read from its documentation and none of it has
        # been observed. It is here so the third engine is a row to correct rather than a branch
        # to invent, and a first run of it should be treated as a bring-up, not as a campaign.
        "binary": "codex",
        "entry_file": "AGENTS.md",
        "prompt_via": "argv",
        "help_argv": ("exec", "--help"),
        "version_argv": ("--version",),
        "required_flags": ("--json", "--model"),
        "review_flags": (),
        "config_dir_env": "CODEX_HOME",
        "base_url_env": None,
        "fallback_keys": (),
        "model_rule": "free",
        "native_provider": "openai",
        "effort_enforced": False,
        "native_bound": "walltime",
        "allowed_tools": False,
        "launch_style": "codex",
        "result_style": "codex_stream",
        "tested": False,
        "tools_note": "UNVERIFIED: tools.txt recorded only, no allowlist flag on the run line",
    },
}


def engine_spec(cfg):
    """The registry row for this config's ENGINE. Every engine-dependent site starts here."""
    return ENGINES[cfg.get("ENGINE")]


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
    "cfg_engine", "cfg_cli_version", "cfg_model", "cfg_effort",
    "cfg_provider", "cfg_endpoint", "cfg_effort_enforced", "cfg_bound",
    "cfg_user_claude_md",
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
    # Appended, never inserted, and nothing above it renamed: 95 published rows carry the header
    # as it stands and a reader that matches by position must keep working. `cfg_user_claude_md`
    # in particular keeps its vendor-shaped name and its exact meaning -- whether a user-level
    # ~/.claude/CLAUDE.md exists -- because renaming it would silently change what those 95 rows
    # are claimed to have measured.
    #
    # cfg_entry_file is the generic companion to it: which name the methodology was actually
    # deployed under for THIS run (CLAUDE.md or AGENTS.md). It is the engine's choice made
    # visible, so a mixed-engine table can be read without inferring the entry file from
    # cfg_engine. Rows written before this column existed leave it blank, which is correct --
    # they were all CLAUDE.md, but the row itself did not record that.
    "cfg_entry_file",
    # --- how the run ended, and how much machinery it used ------------------------------------
    # Appended for the same reason as cfg_entry_file and under the same rule: never inserted,
    # nothing above renamed, rows written before them blank. Blank is the honest cell -- it says
    # this row cannot answer, not that the answer was zero.
    #
    # Why these and not the other sixty fields the payloads carry. res_subtype already says
    # whether a run succeeded; none of the columns said WHY it stopped or WHAT went wrong. A run
    # that ran out of turns, one that stopped of its own accord and one that died on a provider
    # error were all distinguishable only through res_hit_turn_cap, which is derived from a cap
    # that is often unset. On 2026-09-12 four opencode runs were workspace permission rejections
    # and one was a Vulkan OOM, and every one of them read `APIError` in the table: the
    # diagnosis had to be reconstructed by hand from stderr.txt.
    #
    # res_stop_reason and res_error_name/res_error_status are cross-engine -- claude reports
    # stop_reason/terminal_reason and api_error_status, opencode reports part.reason and
    # error.name/error.data.statusCode -- so they are comparable and worth scoring on.
    "res_stop_reason", "res_error_name", "res_error_status",
    # Tool calls are what an agent DID, as opposed to how many model calls it took (prf_turns).
    # opencode names every tool part in its stream; the claude result object does not carry a
    # count, so this stays blank there rather than being guessed from turns.
    "res_tool_calls",
    # The subagent columns already had `spawned`. A methodology that asks for delegation it never
    # gets looks identical to one that never asks, unless the refusals are visible.
    "res_subagents_failed", "res_subagents_refused",
    # claude-only, and deliberately so: these have no counterpart on a local engine and a reader
    # must not average them across engines. cfg_engine is a campaign constant, so rows are not
    # pooled across engines anyway and a column blank on every opencode row costs nothing.
    "res_web_searches", "res_context_window", "res_service_tier",
    # prf_duration_s is wall-clock for the whole run. prf_api_s is the part of it spent waiting
    # on the model, so the difference is the harness's own overhead plus tool execution -- the
    # thing to look at before blaming a model for being slow. prf_ttft_s is time to first token.
    "prf_api_s", "prf_ttft_s",
    # --- did the code even parse? -------------------------------------------------------------
    # res_score cannot tell "wrote code that fails some tests" from "wrote a file that does not
    # compile", and the difference is the whole diagnosis. On 2026-09-12 gpt-oss-20b worked 22
    # minutes on p02_python_medium, made 12 tool calls, wrote 39 lines -- and left an unterminated
    # triple-quoted string on line 69 of intervals.py. Nothing imported, pytest reported
    # `collection failure`, and the row read score=0.0000 exactly like a model that produced
    # nothing. One is a capability limit; the other is an emission defect a single retry would
    # fix, and a table that spells them the same way hides the cheapest improvement available.
    #
    # res_syntax_ok is measured directly with ast.parse over the workspace, not inferred from the
    # test result: a suite can fail to collect for reasons that are not syntax (a missing import,
    # a module-level exception), and those are a different finding again.
    "res_syntax_ok", "res_syntax_error", "res_collection_errors",
    # --- the sc_* score columns (chapter 13.1b) ------------------------------------------------
    # Derived, not measured, and recomputed over the whole table on every consolidation, so they
    # are never stale and never hand-maintained; the measured columns they come from stay
    # untouched beside them. LARGER IS BETTER in every one of them.
    #
    # Per column: the best run OF EACH PROJECT is 1.0, the worst run of the WHOLE TABLE is 0.0,
    # everything else lies between and nothing is clipped. The distance is measured in logarithms,
    # so one doubling is one distance wherever it happens; on the raw scale the slowest run in the
    # table (a factor of 1125 above the fastest) owns the whole range and 95% of rows crowd between
    # 0.9 and 1.0. The denominator is shared across projects, so a distance means the same
    # everywhere, while the anchor is local, so each project is read on its own -- and a project
    # whose arms tie stays bunched just under 1.0 rather than being stretched across the range,
    # which is what a per-project min-max would have done to it.
    #
    # No base file, no reference solution, no starting state: a constant divisor cancels in the
    # difference of two logarithms, so these need nothing but the measured column.
    #
    # sc_effort is time, turns and output tokens -- the three every engine reports. Money is NOT in
    # it and keeps sc_cost_usd: a mean over three factors here and four there is not one measure.
    # The column is filled wherever the engine reports a price and blank where none exists -- that
    # is a property of the model that ran, not of the vendor, so the name carries the currency and
    # not an engine. sc_quality is maintainability, nesting depth and longest function --
    # deliberately not cyclomatic complexity and not SLOC, which res_mi already contains, because
    # averaging a composite with its own ingredients weights size three times over. The composites
    # are arithmetic means: after the log transform these are distances on one scale, not ratios.
    #
    # Blank on a run that did not pass verification -- an effort score without a correctness gate
    # crowns the run that gave up after two turns.
    "sc_duration", "sc_turns", "sc_output", "sc_cost_usd",
    "sc_mi", "sc_max_nesting", "sc_max_func_sloc",
    "sc_effort", "sc_quality", "sc_overall_mean", "sc_overall_ratio",
    # --- the two constants nothing recorded ---------------------------------------------------
    # Appended under the same rule as everything above: never inserted, nothing renamed, rows
    # written before them blank.
    #
    # cfg_walltime_s is CLI_TIMEOUT_S as it stood for THIS run. It is named a campaign constant
    # at its definition -- a row censored at 3600 s is not comparable with one censored at
    # 14400 s, because `harness_timeout` says "we stopped it", not "it failed" -- and until now
    # no column said which side of the 2026-09-13 change a row was on. It is therefore also in
    # CAMPAIGN_CONSTANTS, which means a campaign holding rows from both sides is reported as
    # mixed. That report is the point: those rows were never poolable, the table simply could
    # not say so. Every row written before this column exists stays blank, and blank against a
    # number is itself a difference the gate will name.
    #
    # cfg_free_ram_gb is not a constant and is not in CAMPAIGN_CONSTANTS -- it is an observation,
    # read once before the implementer is launched, of memory as the model finds it. On an
    # integrated GPU it is the number that decides whether the next model loads, pages from
    # disk, or dies in the allocator: 18 GB of weights against ~8 GB free measured 0.76 tok/s,
    # which is paging and not inference, and no row said so. Blank where it cannot be read.
    "cfg_walltime_s", "cfg_free_ram_gb",
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
# the restraint columns grow with mth_chars -- res_files_added read 4 on every m02_doctypes row for
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

    The default is .llm_config.e02_claude_sonnet_5; --config selects another level, so a cheap sweep
    (.llm_config.e01_claude_haiku_4_5) and the campaign proper differ by a file rather than by an edit.
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
    # The single gate on the engine, now a membership test against the registry rather than an
    # equality test against one name. It stays a gate: an ENGINE the table does not know is a
    # config error and not a default, because every row below -- the entry file, the launch line,
    # the parser, cfg_bound -- is looked up from this value, and a lookup that silently fell back
    # to `claude` would produce a row that names an engine that never ran.
    if cfg.get("ENGINE") not in ENGINES:
        die("ABORT: ENGINE=%s (got %r)" % ("|".join(sorted(ENGINES)), cfg.get("ENGINE")), 4)
    spec = ENGINES[cfg["ENGINE"]]
    # An untested row is not a reason to refuse the run -- it is a reason the operator must know
    # they are the one testing it. Printed, not raised: the abort would make the branch
    # unreachable and a branch nobody can reach never gets corrected.
    if not spec["tested"]:
        print("NOTE: ENGINE=%s is structural only -- never executed end to end, and no value in\n"
              "its registry row has been observed. Treat this run as a bring-up." % cfg["ENGINE"])
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


def reject_alias(model, key, rule="anthropic_canonical"):
    """Abort unless `model` is a canonical id (chapter 9). What canonical means is the engine's.

    The defect being caught is the same under every engine: an alias silently re-points to a
    different model between campaigns while every column still reads as intended, which is why it
    is caught here rather than noticed in `res_model_served` afterwards. What differs is the shape
    a canonical id has, and applying one vendor's shape to another's ids would reject correct
    configurations -- which teaches the operator to stop trusting the check.

      anthropic_canonical  a digit in a dash-separated part after the first (`claude-sonnet-5`);
                           a bare `opus`, `sonnet` or `sonnet-latest` does not qualify. The rule
                           as it stood, unchanged, and the only rule ENGINE=claude ever sees.
      provider_slash_model opencode addresses a model as `provider/model`, and the provider half
                           is what says where it was served (`litellm/qwen3-coder-30b`). A bare
                           model name is the alias case here: it leaves the routing to whatever
                           the CLI's config happens to default to. The version part is NOT
                           required -- a self-hosted id legitimately carries none, and demanding
                           a digit would reject `litellm/my-local-coder` for being honest.
      free                 no rule. Used only where nobody has yet observed what the engine's ids
                           look like, and it is a gap to close, not a decision.
    """
    if rule == "provider_slash_model":
        provider, _, name = model.partition("/")
        if not provider or not name or "/" in name:
            die("ABORT: %s=%r is not a canonical opencode id -- it must be provider/model,\n"
                "e.g. litellm/qwen3-coder-30b. A bare model name leaves the routing to the CLI's\n"
                "own configuration, which re-points between campaigns exactly as an alias does."
                % (key, model), 4)
        return
    if rule == "free":
        if not model:
            die("ABORT: %s is not set" % key, 4)
        return
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
    rule = engine_spec(cfg)["model_rule"]
    reject_alias(cfg.get("MODEL", "").strip(), "MODEL", rule)
    named_fix = cfg.get("FIX_MODEL", "").strip()
    if named_fix:
        reject_alias(named_fix, "FIX_MODEL", rule)
    named_review = cfg.get("REVIEW_MODEL", "").strip()
    if named_review and cfg.get("REVIEW_PASS", "") == "same_model":
        reject_alias(named_review, "REVIEW_MODEL", rule)
    # Per engine, because the key is the vendor's: a CLI that has no fallback knob has no key to
    # forbid, and forbidding another engine's key here would only read as diligence.
    for key in engine_spec(cfg)["fallback_keys"]:
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
    spec = engine_spec(cfg)
    # A provider other than the engine's own is reached over a base URL and nowhere else: named
    # without one, the run would go to the engine's own endpoint while cfg_provider claimed
    # otherwise -- a row that misreports what served it, which is worse than a run that does not
    # start. The rule only exists where the engine HAS a base-URL knob.
    if spec["base_url_env"]:
        if cfg.get("PROVIDER", "").strip() not in ("", spec["native_provider"]) \
                and not cfg.get("BASE_URL", "").strip():
            die("ABORT: PROVIDER=%s needs BASE_URL -- without one the run reaches this vendor's own\n"
                "endpoint and cfg_provider would misreport what served it."
                % cfg["PROVIDER"].strip(), 4)
    elif cfg.get("BASE_URL", "").strip():
        # The mirror image, and the reason this is an abort rather than a shrug: cli_env() has
        # nowhere to put the value, so the run would go wherever the engine's own configuration
        # sends it while cfg_endpoint printed the URL the operator wrote down. A column that
        # confidently names the wrong endpoint is worse than no run.
        die("ABORT: BASE_URL is set but ENGINE=%s has no base-URL environment variable, so it\n"
            "cannot be applied -- cfg_endpoint would name an endpoint that never served the run.\n"
            "Address the endpoint through MODEL (provider/model) instead." % cfg["ENGINE"], 4)
    # CLAUDE_CONFIG_DIR is accepted only by the engine whose own variable it IS. Two different
    # ways of being wrong are refused here, and the second one used to pass.
    #
    # No config-dir knob at all (opencode): the value could not be applied, so the run would use
    # the engine's default account data while the config file claimed otherwise.
    #
    # A config-dir knob under a DIFFERENT name (codex's CODEX_HOME): the value could be applied,
    # and that is precisely the problem. A key named CLAUDE_CONFIG_DIR pointing codex's account
    # directory somewhere is not a knob the operator asked for -- it is this harness quietly
    # deciding that two vendors' account stores are the same thing because one config key
    # happened to be free. CODEX_HOME holds credentials and session state; repointing it on the
    # strength of a Claude-named key is how a campaign runs against an account nobody chose. The
    # config key keeps its name for the engine it belongs to (renaming it would silently unset
    # the knob in every existing .llm_config.* file); for any other engine it is an abort, and
    # the fix is an engine-appropriate key that does not exist yet rather than a reused one.
    cdir_env = spec["config_dir_env"]
    if cdir_env != "CLAUDE_CONFIG_DIR" and cfg.get("CLAUDE_CONFIG_DIR", "").strip():
        if not cdir_env:
            die("ABORT: CLAUDE_CONFIG_DIR is set but ENGINE=%s does not read it -- the run would use\n"
                "the engine's default account data while the config file claimed otherwise."
                % cfg["ENGINE"], 4)
        die("ABORT: CLAUDE_CONFIG_DIR is set but ENGINE=%s keeps its account data in %s, not in\n"
            "CLAUDE_CONFIG_DIR. Applying the value would repoint %s from a key named for another\n"
            "vendor -- an account switch nobody asked for. Leave CLAUDE_CONFIG_DIR unset for this\n"
            "engine and configure %s in the environment the campaign is launched from."
            % (cfg["ENGINE"], cdir_env, cdir_env, cdir_env), 4)


def allowed_tools(methodology, project):
    """The arm's --allowedTools list and the cfg_tools cell that records it (chapter 15).

    The default list is identical for every arm, so the tool set is not a treatment. An arm that
    ships `methodology/<M>/tools.txt` replaces it, and cfg_tools carries the deviation so chapter
    17 keeps rows with different tool sets out of one pivot.
    """
    src = ROOT / "methodology" / methodology / "tools.txt"
    if src.is_file():
        tools = read_tool_file(src, "methodology/%s/tools.txt" % methodology)
        base, cfg = ",".join(tools), ",".join(tools)
    else:
        base, cfg = DEFAULT_TOOLS, "default"

    # A project may need tools no methodology asks for -- p06_qc_ema_cross drives the
    # QuantConnect MCP server and cannot be done with the default list. That need belongs to
    # the task, not to the arm, so `projects/<P>/tools.txt` is APPENDED to whatever the arm
    # runs with: the treatment stays the arm's list, and every arm on that project gets the
    # same addition. cfg_tools records the appendix so chapter 17 can still separate rows.
    psrc = ROOT / "projects" / project / "tools.txt"
    if psrc.is_file():
        extra = read_tool_file(psrc, "projects/%s/tools.txt" % project)
        add = [t for t in extra if t not in base.split(",")]
        if add:
            base = base + "," + ",".join(add)
            cfg = cfg + "+project:" + ",".join(add)
    return base, cfg


def record_tool_enforcement(cfg, cfg_tools):
    """What cfg_tools may claim once the engine is taken into account.

    allowed_tools() answers "what tool set does this arm ask for", which is the same question on
    every engine. Whether the answer was IMPOSED is a different question, and only one engine
    currently answers yes: `--allowedTools` is on the claude launch line, and there is no
    equivalent flag on opencode's or codex's (registry: allowed_tools, tools_note).

    Left alone, the cell would say the same thing either way -- `default`, or the arm's list --
    and chapter 17 would read a row whose agent had the CLI's own unrestricted tool surface as a
    row that ran under the named restriction. That is a treatment the run did not receive,
    recorded as though it had, and the pivot that separates tool sets would put the two in one
    group. So on an engine with no allowlist flag the cell carries `unenforced:` in front of the
    value: the arm still declared a tool set and the row still says which, but it no longer
    asserts that anything applied it.

    ENGINE=claude passes through untouched, which is what keeps the cell comparable with the rows
    already published.
    """
    if engine_spec(cfg)["allowed_tools"]:
        return cfg_tools
    return "unenforced:" + cfg_tools


def read_tool_file(path, label):
    """Parse one tools.txt: non-empty lines, each a tool entry. Shared by arm and project."""
    tools = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    if not tools:
        die("ABORT: %s is empty" % label, 4)
    for line in tools:
        if not TOOL_LINE.match(line):
            die("ABORT: %s: %r is not a tool entry (Name or Name(pattern))" % (label, line), 4)
    return tools


def read_free_ram_gb():
    """Free physical memory in GB for cfg_free_ram_gb, or "" where it cannot be read.

    One decimal, which is all the figure is worth: it is a reading of a machine-wide quantity
    that moves while the run starts, not a controlled constant. The measurement itself lives in
    engine_freeram.py, which already prints it between the unload and the load of every leg, so
    the column and the console line can never report different numbers.

    Imported here rather than at module scope, and every failure swallowed: the harness runs on
    machines where that module, or GlobalMemoryStatusEx, is not there, and a diagnostic column
    must never be able to abort a run. A blank cell reads "not measured", which is true.
    """
    try:
        from engine_freeram import free_gb
        reading = free_gb()
    except Exception:
        return ""
    return "" if reading is None else round(reading[0], 1)


def engine_columns(cfg):
    """The four cells that make a row groupable when more than one provider serves a model.

    `cfg_engine` names the runtime and `cfg_model` the id requested, but one id can be served
    from several places -- the vendor's own endpoint, a gateway, a local server -- and those
    are not one population: quantisation, context window and routing differ under one model
    name. `cfg_provider` and `cfg_endpoint` are what separate them, and both are campaign
    constants (chapter 17), so a campaign that mixes them is reported as mixed.

    `cfg_effort_enforced` exists because `--effort` is a flag of this vendor's API: a provider
    without an effort knob drops it silently, and `cfg_effort=medium` would then read as a
    treatment that never happened. `cfg_bound` names the cap that actually binds the run --
    `--max-budget-usd` binds only where the endpoint reports cost, and where it does not the
    harness timeout is the only bound left, which is a censoring a row must carry rather than
    hide. Both are derived from the provider, not declared, so they cannot disagree with it.

    Blank PROVIDER is this vendor, which is what every row before these columns existed was;
    the backfill of those rows writes exactly these four values.
    """
    spec = engine_spec(cfg)
    provider = cfg.get("PROVIDER", "").strip() or spec["native_provider"]
    if not provider and spec["model_rule"] == "provider_slash_model":
        # An engine with no endpoint of its own still has to fill cfg_provider, and a blank cell
        # would say "unknown" where the answer is in fact written on the launch line: the model id
        # IS `provider/model` there. Declared PROVIDER still wins, so an operator who knows the
        # gateway behind `litellm/` can name it.
        provider = cfg.get("MODEL", "").strip().partition("/")[0]
    endpoint = cfg.get("BASE_URL", "").strip() or "native"
    native = bool(spec["native_provider"]) and provider == spec["native_provider"]
    # Two conditions, not one. The effort knob is the engine's -- an engine whose launch line
    # carries no effort flag never enforces one, whatever the provider is -- and being served
    # from somewhere else drops it even where the engine has it. So both must hold.
    effort_enforced = spec["effort_enforced"] and native
    # cfg_bound names the cap that actually stops a runaway run, which is not the same question
    # as "is a cost figure available". Under ENGINE=opencode it is deliberately `walltime` even
    # though tk_cost_usd is populated: opencode reports `cost` in every step_finish and LiteLLM
    # prices it upstream, so the number is real -- but there is no per-run budget flag to hand
    # it to, so nothing acts on it. The run ends when the agent stops or when CLI_TIMEOUT_S kills
    # it, and that is the censoring a reader of the row has to know about. Writing `usd` here
    # because the dollars are visible would say a cap existed that would never have fired.
    bound = spec["native_bound"] if native else "walltime"
    return {"cfg_provider": provider,
            "cfg_endpoint": endpoint,
            "cfg_effort_enforced": "true" if effort_enforced else "false",
            "cfg_bound": bound}


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


def step5_deploy_entry_file(cfg, run_dir, workspace):
    """Render the placeholders and deploy the entry file under the engine's name. Empty is fine.

    The target name is the registry's `entry_file` -- `CLAUDE.md` under ENGINE=claude, `AGENTS.md`
    under the other two. The source is named `agents_or_claude.md` because the text was always
    portable between them; only the destination waited, and this is where it stops waiting. The
    rendered bytes are identical either way, so mth_chars and mth_version are comparable across
    engines: what differs is which name the CLI happens to look for, not what the arm said.

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
    target = workspace / engine_spec(cfg)["entry_file"]
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


def cli_help_and_version(spec):
    """Query the installed CLI once per invocation and cache the answer.

    Cached per engine, not globally: a matrix invocation runs one engine, but the cache outliving
    a change of engine within one process would validate the second engine's launch line against
    the first engine's help text and pass it without looking.

    `spec` is required. It defaulted to the claude row while the engine registry was being
    introduced, and nothing ever called it that way -- the one call site has a spec in hand. A
    default that silently substitutes a DIFFERENT engine's registry row is not a convenience
    here: it would probe the wrong binary and cache the wrong help text under the wrong key, and
    the check that exists to catch a launch line the CLI does not accept would pass by looking at
    another CLI's help.
    """
    key = spec["binary"]
    if key not in _CLI_CACHE:
        cli = resolve_cli(spec["binary"])
        env = child_env()
        h = subprocess.run([cli] + list(spec["help_argv"]), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, env=env)
        v = subprocess.run([cli] + list(spec["version_argv"]), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, env=env)
        help_text = (h.stdout or b"").decode("utf-8", "replace")
        text = (v.stdout or b"").decode("utf-8", "replace").strip().splitlines()
        _CLI_CACHE[key] = (help_text, text[0].strip() if text else "")
    return _CLI_CACHE[key]


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
    # same_model builds its own launch line (step 7b) and that line is the claude CLI's: -p,
    # --effort, --max-budget-usd, --disallowedTools, --mcp-config. It is not routed through the
    # registry because a blind, tool-less, stdin-only reviewer is not the same thing as an
    # implementer and inventing its equivalent for an engine nobody has run it on would produce a
    # reviewer whose blindness is assumed rather than known -- and res_review_findings would then
    # be a number with no defensible meaning. So it is refused here, loudly, and REVIEW_PASS=
    # other_model remains open to every engine: that path is an external command the config names
    # in full, so it needs nothing from the registry.
    if cfg["REVIEW_PASS"] == "same_model" and engine_spec(cfg)["launch_style"] != "claude":
        die("ABORT: REVIEW_PASS=same_model is not implemented for ENGINE=%s -- the reviewer's\n"
            "launch line (no tools, no MCP, stdin only) exists for the claude CLI alone, and a\n"
            "reviewer whose blindness has not been verified would make res_review_findings\n"
            "uninterpretable. Use REVIEW_PASS=other_model with an explicit REVIEW_CMD, or none."
            % cfg["ENGINE"], 6)
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
    """Abort unless every option this engine's launch line uses is present in its own help text.

    The CLI ignores unknown options without complaint, so this is the only place a removed or
    renamed flag can be caught before tokens are spent. The help text is kept per run so a row
    stays diagnosable after a CLI upgrade. The review pass adds its own option to the set, and
    only when it is configured -- a CLI that cannot review is not a reason to fail a run that
    does not review.

    Two things are per-engine here, and neither of them is "skip the check". The first is WHICH
    help text: `claude --help` prints the run flags, `opencode --help` prints a list of
    subcommands and nothing this harness passes, so the registry names the probe (`run --help`)
    rather than the harness concluding the CLI cannot be validated. The second is WHICH flags:
    each engine is checked against the line it is actually launched with -- opencode's has no
    budget, effort, permission-mode or allowlist option to require, and demanding them would
    fail a correct configuration, which is the fastest way to get a check disabled. ENGINE=claude
    is validated against exactly the set it always was.
    """
    spec = engine_spec(cfg)
    help_text, version = cli_help_and_version(spec)
    write_record(record, help_text)
    required = tuple(spec["required_flags"]) + (tuple(spec["review_flags"])
                                                if cfg["REVIEW_PASS"] == "same_model" else ())
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


def resolve_cli(binary="claude"):
    """Resolve the named CLI to something CreateProcess can launch.

    The default is the historical one, so a call site that has no config in hand behaves exactly
    as it did; every site that knows the engine passes the registry's `binary` instead.

    shutil.which() may hand back a .cmd/.bat shim, which subprocess cannot exec directly on
    Windows; prefer a sibling .exe when one exists, and abort when there is none rather than
    hand back a path CreateProcess cannot launch -- returning the shim only moved the failure to
    step 7, where it arrived as `WinError 193: %1 is not a valid Win32 application` after a run
    directory and a venv had already been built.

    A CLI that is not there, a CLI that cannot be launched and a CLI missing a flag are the same
    class of failure -- the launch line cannot be trusted -- so all three exit 6.
    """
    found = shutil.which(binary)
    if found is None:
        die("ABORT: %r not found on PATH (shutil.which)" % binary, 6)
    p = Path(found)
    if IS_WIN and p.suffix.lower() in (".cmd", ".bat", ""):
        exe = p.with_suffix(".exe")
        if exe.is_file():
            return str(exe)
        die("ABORT: %r on PATH is %s, which CreateProcess cannot launch directly, and no\n"
            "sibling %s exists. Install the native Windows executable (or put its directory\n"
            "ahead of the shim on PATH) so the harness can start the CLI as a subprocess."
            % (binary, p, exe.name), 6)
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
    # Both variables are the engine's own names, from the registry. The config KEYS keep the names
    # they always had (CLAUDE_CONFIG_DIR, BASE_URL) -- renaming a config key would silently turn
    # every existing .llm_config.* file into one with an unset knob, which is the exact failure
    # mode this file spends its aborts guarding against. An engine that offers no such variable
    # gets neither set nor cleared here; check_config_keys has already refused the config that
    # tries to use one, so there is nothing to apply and nothing to misreport.
    spec = engine_spec(cfg)
    # Only the engine whose own variable is literally CLAUDE_CONFIG_DIR reads the config key of
    # that name. An engine with a differently-named config dir (codex's CODEX_HOME) is left
    # alone: check_config_keys has already refused a config that sets the key for such an engine,
    # and the value is not carried across to another vendor's account store here either. An
    # inherited CODEX_HOME is likewise neither set nor cleared -- the harness has no opinion it
    # is entitled to about a variable no config key of its own controls.
    cdir_env = spec["config_dir_env"]
    if cdir_env == "CLAUDE_CONFIG_DIR":
        ccd = cfg.get("CLAUDE_CONFIG_DIR", "").strip()
        if ccd:
            env[cdir_env] = str((ROOT / ccd) if not os.path.isabs(ccd) else Path(ccd))
        else:
            env.pop(cdir_env, None)
    # BASE_URL is the endpoint cfg_endpoint claims served the run, so it must reach the CLI here and
    # nowhere else: recorded without being applied, the column would misreport what served the row.
    # Blank means this vendor's own endpoint, and any inherited override is dropped for the same
    # reason -- the config file, not the user's shell, decides where a campaign is served from.
    url_env = spec["base_url_env"]
    if url_env:
        base_url = cfg.get("BASE_URL", "").strip()
        if base_url:
            env[url_env] = base_url
        else:
            env.pop(url_env, None)
    return env


def write_mcp_config(project, run_dir):
    """The --mcp-config file the implementer launches with, and the empty one beside it.

    The CLI validates --mcp-config against a schema: a bare "{}" is rejected with
    'mcpServers: expected record, received undefined'. Written as a file, so no shell quoting
    of JSON is involved and the run directory records what was actually passed.

    Default is no server at all -- the tool surface is a campaign constant and an MCP server
    reachable from one machine and not another would be an uncontrolled one. A project that
    cannot be done without an external system says so by shipping `projects/<P>/mcp.json`,
    which is copied verbatim into the run directory and passed instead; --strict-mcp-config
    still means nothing else can reach the run. `mcp_empty.json` is written either way,
    because the reviewer (step 7b) is stdin-only and always launches without servers.
    """
    empty = run_dir / "mcp_empty.json"
    empty.write_text('{"mcpServers": {}}\n', encoding="utf-8")
    src = ROOT / "projects" / project / "mcp.json"
    if not src.is_file():
        return empty
    try:
        json.loads(src.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        die("ABORT: projects/%s/mcp.json is not valid JSON: %s" % (project, exc), 4)
    mcp = run_dir / "mcp.json"
    shutil.copy2(src, mcp)
    return mcp


def implementer_argv(cfg, project, run_dir, tools, model=None, prompt=""):
    """The step-7 launch line for whichever engine is configured -- one of the two dispatch points.

    An argv list is not data, so this is a function rather than another registry field; what makes
    it one dispatch point and not thirteen is that no other site in the file builds a launch line.
    `prompt` is ignored by every engine that takes the task on stdin and is the task itself for
    those that take it as a positional argument (registry: prompt_via).

    ENGINE=claude returns exactly the list it always returned, in the same order, with the same
    literals -- see claude_implementer_argv, which is the old body moved and otherwise untouched.
    """
    style = engine_spec(cfg)["launch_style"]
    if style == "claude":
        return claude_implementer_argv(cfg, project, run_dir, tools, model)
    if style == "opencode":
        return opencode_implementer_argv(cfg, run_dir, model, prompt)
    return codex_implementer_argv(cfg, run_dir, model, prompt)


def opencode_implementer_argv(cfg, run_dir, model, prompt):
    """`opencode run "<prompt>" --format json -m <provider/model>`, and nothing else.

    Deliberately short, and every absence is a measurement that this engine cannot make rather
    than a flag someone forgot. There is no budget flag, so MAX_BUDGET_USD does not bind and
    cfg_bound says `walltime`. There is no effort flag, so EFFORT does not reach the model and
    cfg_effort_enforced says false. There is no tool allowlist on the run line, so tools.txt is
    recorded in cfg_tools and not enforced (registry: tools_note) -- the honest reading of such a
    row is that its tool surface was the CLI's default, not the arm's list. And there is no
    --add-dir: the methodology snapshot beside the workspace is not reachable, so an arm whose
    entry file points at files under methodology/ is not comparable here.

    The model id goes through unaltered: it is `provider/model` and the provider half is the
    routing, which is why reject_alias insists on both halves.
    """
    return [resolve_cli(engine_spec(cfg)["binary"]), "run", prompt,
            "--format", "json", "-m", (model or cfg["MODEL"])]


def codex_implementer_argv(cfg, run_dir, model, prompt):
    """STRUCTURAL ONLY -- never executed, never observed. `codex exec --json --model <m> <prompt>`.

    Written from documentation on a machine where the codex CLI is not installed, so the flag
    names, the subcommand and the position of the prompt are all unverified. It exists so the
    third engine is one function to correct against a real CLI rather than a shape to invent
    later, and it must not be read as support for OpenAI's runtime.
    """
    return [resolve_cli(engine_spec(cfg)["binary"]), "exec", "--json",
            "--model", (model or cfg["MODEL"]), prompt]


def claude_implementer_argv(cfg, project, run_dir, tools, model=None):
    """The step-7 launch line. Every implementer invocation uses it, the fix call included.

    No --max-turns: Claude Code 2.1.251 has no such flag (it is an SDK option) and the CLI
    accepts unknown options silently, so passing it would be an invisible no-op. The run is
    bounded by --max-budget-usd; MAX_TURNS is a reporting threshold only (see res_hit_turn_cap).

    `model` overrides MODEL for one invocation and is used by the step-7c fix call alone
    (FIX_MODEL, chapter 9). Nothing else on the line moves with it: applying named issues is a
    different job from writing the code, and the tier it deserves is the open question.
    """
    mcp = write_mcp_config(project, run_dir)
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


def exit_code_path(out_path):
    """Where the exit code of the process that wrote `out_path` is kept: `<out_path>.exit`.

    Derived from the stdout path rather than named separately so the two cannot be paired up
    wrongly under BEST_OF_N, where result_1.json .. result_N.json all live in one run directory
    and the fix call adds fix.json beside them.
    """
    return Path(str(out_path) + ".exit")


def write_exit_code(out_path, rc):
    """Record a launched CLI's exit status beside its stdout. `timeout` when the harness killed it."""
    exit_code_path(out_path).write_text("" if rc is None else str(rc), encoding="utf-8")


def read_exit_code(out_path):
    """The recorded exit code as an int, or None when there is no usable answer.

    None is returned for a missing file (an engine that writes none, or stdout kept from an older
    run), for an empty one, and for `timeout` -- and None is not the same claim as a non-zero
    code. A non-zero code is the process saying it failed; None is the harness saying it does not
    know, and stream_result_record has to treat "unknown" as "cannot certify this run finished"
    rather than as either verdict.
    """
    p = exit_code_path(out_path)
    if not p.is_file():
        return None
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def launch_implementer(cfg, project, run_dir, workspace, stdin, tools, out_path, err_path,
                       model=None, argv_name="cli_argv.txt"):
    """One implementer invocation with cwd = workspace and stdin piped in.

    Used by step 7, by each best-of-N candidate and by the feedback fix call, so those three
    cannot drift onto different flags, a different tool set or a different budget. The fix call
    passes its own `model` and its own `argv_name`: under FIX_MODEL the two launch lines really
    differ, and one file overwriting the other would leave the run directory unable to say which.
    """
    # `stdin` is the task text. Under an engine that takes the task as a positional argument it
    # goes onto the launch line instead and the pipe is closed empty -- leaving the same text on
    # both would hand the agent its instructions twice, and leaving the pipe open would hold the
    # CLI waiting on a stream nobody is going to write to.
    args = implementer_argv(cfg, project, run_dir, tools, model, prompt=stdin)
    argv_on_line = engine_spec(cfg)["prompt_via"] == "argv"
    if argv_on_line:
        stdin = ""
    # The file exists so a run can be reproduced from its own directory, which means it has to
    # round-trip. Newline-joined argv does that only while no argument contains a newline -- true
    # of every launch line whose prompt arrives on stdin, and false the moment the task itself is
    # an argv element, because prompt.md is many lines long and the join then produces a file
    # that cannot be split back into the arguments that were run. So the engines that put the
    # prompt on the line get a JSON array, which survives embedded newlines, quotes and empty
    # strings and is read back with one json.loads.
    #
    # The stdin engines keep the newline-joined form they have always had. Two formats is the
    # smaller cost: 95 published runs have a cli_argv.txt in the old shape, the run directory is
    # the record those rows are audited against, and reformatting it would make every one of them
    # differ from a re-run for a reason that has nothing to do with the run. Which shape a file is
    # in is decided by its first byte -- `[` is the JSON form.
    if argv_on_line:
        (run_dir / argv_name).write_text(json.dumps(args, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    else:
        (run_dir / argv_name).write_text("\n".join(args), encoding="utf-8")
    started = time.time()
    timed_out = False
    rc = None
    try:
        p = subprocess.run(args, cwd=str(workspace), input=stdin, text=True, encoding="utf-8",
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           env=cli_env(cfg, run_dir), timeout=CLI_TIMEOUT_S)
        out, err = p.stdout or "", p.stderr or ""
        rc = p.returncode
    except subprocess.TimeoutExpired as e:
        timed_out = True
        out = e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        err = e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace")
    wall = time.time() - started
    out_path.write_text(out, encoding="utf-8")
    err_path.write_text(err, encoding="utf-8")
    # The process's own verdict on itself, kept beside its stdout -- for the stream engines only.
    #
    # A stream engine has no other end-of-run marker. opencode writes no terminal event: a run
    # that stopped after three of ten steps is byte-for-byte a PREFIX of a run that finished, and
    # nothing inside the stream distinguishes them. The exit code is the one remaining signal, and
    # on opencode 1.18.30 it was observed to carry the answer -- 0 on a clean finish, 1 on a
    # failure, both when the failure came before any step (unknown model) and when it came after
    # steps that had already been billed. Written as a file rather than returned because three
    # call sites and three readers would otherwise have to thread a fourth value between them.
    #
    # ENGINE=claude gets no such file, and not merely because it would be redundant: its `result`
    # object is self-describing, a truncated stdout fails to parse and is recorded `unparsable`
    # already, and its run directory is the audit record behind 95 published rows. An extra file
    # appearing in it would be a change to that record for no measurement gained.
    if engine_spec(cfg)["result_style"] != "claude":
        write_exit_code(out_path, "timeout" if timed_out else rc)
    return wall, timed_out


def step7_launch_cli(cfg, project, run_dir, workspace, tools):
    """Launch the CLI in the workspace with the project's prompt on stdin."""
    prompt = (ROOT / "projects" / project / "prompt.md").read_text(encoding="utf-8")
    return launch_implementer(cfg, project, run_dir, workspace, prompt, tools,
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
        step5_deploy_entry_file(cfg, run_dir, ws)
        wall, timed_out = launch_implementer(cfg, project, run_dir, ws, prompt, tools,
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
        cand_out = run_dir / ("result_%d.json" % i)
        data = engine_result_record(cfg, cand_out.read_text(encoding="utf-8"),
                                    read_exit_code(cand_out))
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
    # The exit code travels with the stdout it belongs to. Under a stream engine it is the only
    # thing that says whether the winning candidate finished, and step 9 reads it beside
    # result.json: left behind, every best-of-N row would fall back to "no exit code recorded"
    # and report incomplete_stream on a candidate that ran cleanly. Engines that write no sidecar
    # (claude) leave nothing to copy and nothing changes.
    won = exit_code_path(run_dir / ("result_%d.json" % best["i"]))
    if won.is_file():
        shutil.copy2(won, exit_code_path(run_dir / "result.json"))
    scored = [c["score"] for c in cands if c["score"] >= 0]
    row = {"res_bestof_n": n,
           "res_bestof_min": ("%.4f" % min(scored)) if scored else "",
           "res_bestof_max": ("%.4f" % max(scored)) if scored else "",
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
    wall, _ = launch_implementer(cfg, project, run_dir, workspace, stdin, tools,
                                 run_dir / "fix.json", run_dir / "fix_stderr.txt",
                                 model=fix_model(cfg), argv_name="fix_argv.txt")
    row["prf_fix_s"] = round(wall, 1)
    row["res_review_fixed"] = 1
    data = engine_result_record(cfg, (run_dir / "fix.json").read_text(encoding="utf-8"),
                                read_exit_code(run_dir / "fix.json"))
    if data is not None:
        usage = data.get("usage") or {}
        row["tk_fix_input"] = usage.get("input_tokens", "")
        row["tk_fix_output"] = usage.get("output_tokens", "")
        row["tk_fix_cache_write"] = usage.get("cache_creation_input_tokens", "")
        row["tk_fix_cache_read"] = usage.get("cache_read_input_tokens", "")
        row["tk_fix_cost_usd"] = data.get("total_cost_usd", "")
    print("feedback: issues=%d fixed=1 dur=%ss" % (len(issues), row["prf_fix_s"]))
    return row


def engine_result_record(cfg, raw, exit_code=None):
    """The run's outcome record, from whatever this engine writes on stdout -- dispatch point two.

    Every engine produces the same SHAPE here, and the shape is the one ENGINE=claude already
    emits: `usage`, `total_cost_usd`, `num_turns`, `subtype`, `model`, `duration_ms`,
    `permission_denials`, `modelUsage`, `subagent_stats`. Normalising at the boundary is what
    keeps step9_parse_and_write, step7a's cost tie-break and the fix call's token columns free of
    engine tests: they read a record, not a CLI. The alternative -- teaching each of those three
    every format -- is how a harness ends up with a column that means one thing per engine.

    A field an engine does not report stays ABSENT rather than being filled with a zero. A blank
    cell says the engine could not answer; a zero says it answered nothing, and a campaign that
    averages the second is quietly wrong.

    ENGINE=claude goes to result_record unchanged -- same input, same output, same None on
    unparsable stdout.
    """
    style = engine_spec(cfg)["result_style"]
    if style == "claude":
        return result_record(raw)
    return stream_result_record(raw, exit_code)


def stream_events(raw):
    """Every JSON object in a stream engine's stdout, whatever shape the stdout turned out to be.

    opencode 1.18.30 writes newline-delimited JSON -- one complete object per line, no wrapping
    array, no terminal event. That was observed, not assumed, and it is the shape this reads
    first: each line on its own, a line that will not parse skipped rather than failing the whole
    stdout, because a half-written last line is the normal shape of a killed process and the
    steps before it are real spend that has to reach the row.

    But "one object per line" is a property of a CLI, not a law, and the harness has already been
    wrong once about what a CLI emits. A stdout that parses whole -- one JSON document, either an
    array of events or a single object -- is therefore also accepted, and only if the per-line
    pass found nothing. Trying it in that order matters: NDJSON with more than one line never
    parses whole, so the fallback cannot misread a stream it should have read line by line, while
    a pretty-printed array (which has no parsable individual lines) is picked up correctly. A
    codex stream nobody has run yet is the case this is really holding open.
    """
    events = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(ev, dict):
            events.append(ev)
    if events:
        return events
    try:
        whole = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if isinstance(whole, dict):
        return [whole]
    if isinstance(whole, list):
        return [e for e in whole if isinstance(e, dict)]
    return []


def _num(value):
    """A JSON number as a number, or None when the field was absent or not one.

    None rather than 0 on purpose, all the way up: it is what lets the caller tell a field the
    engine reported as zero from a field the engine did not report, which is the difference
    between a true zero and a fabricated one in the row.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _tidy(value):
    """A summed token count as the integer it is, without truncating one that is not.

    Token counts arrive as JSON integers, so the sum is normally integral and is written as an
    int. A provider that reports a fractional count is not silently floored to a smaller number
    -- int() on a float is truncation, and a count that quietly rounds down is the kind of error
    that only shows up as a campaign whose totals do not add.
    """
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def stream_result_record(raw, exit_code=None):
    """Fold a line-per-event JSON stream (opencode, and codex as written) into a result record.

    WHAT WAS OBSERVED. opencode 1.18.30, `run --format json`, driven against a controlled
    OpenAI-compatible endpoint so that the token counts and the step boundaries were known in
    advance. Every claim below is from that capture; the notes it replaces were written from
    documentation and were wrong in two places that mattered.

    Shape: newline-delimited JSON. Event `type` values seen: `step_start`, `tool_use`, `text`,
    `step_finish`, `error`. There is no terminal or summary event of any kind.

    Where the accounting lives: inside `part`, NOT at the top level of the event. A step_finish
    reads

        {"type":"step_finish", ..., "part":{"type":"step-finish","reason":"stop",
         "tokens":{"total":330,"input":300,"output":30,"reasoning":0,
                   "cache":{"write":0,"read":0}}, "cost":0.00036}}

    so a parser reading ev["cost"] and ev["tokens"] -- as this one did -- finds nothing and
    silently totals a run at $0.00 with no tokens. That is the defect this rewrite exists for.

    Per-step or cumulative: PER-STEP. This was the question worth an experiment, because summing
    a running total inflates an N-step run by roughly N**2/2. The endpoint was made to report
    usage of (200 in, 20 out) on the first model call and (300 in, 30 out) on the second. The two
    step_finish events carried exactly those numbers -- input 200 then input 300, not 200 then
    500 -- and cost 0.00024 then 0.00036 at a configured $1/$2 per million, which is each step's
    own tokens priced alone and not a running total. Summing across step_finish is therefore
    correct. (What the sum means is a separate thing a reader should know: each step's `input` is
    that call's whole prompt, so the total counts re-sent context once per step. That is what the
    provider bills and what tk_input has always meant on the claude path too, so the columns
    remain comparable.)

    Turns: the number of step_start events. Two in the captured multi-step run, matching the two
    model calls the endpoint saw from the main agent. The session-title call opencode makes on
    its small model produced no step events at all, so it does not inflate the count.

    Model served: NOT REPORTED. No event in the capture -- of any type -- carries a model id. The
    old loop scanned every event for any key called `modelID`, `model` or `model_id` and kept the
    LAST match, which is exactly the failure step 9 spends a paragraph guarding against on the
    claude path: an auxiliary model winning a field that is supposed to name the model that did
    the work. There is no authoritative field to read instead, so `model` is left ABSENT and
    res_model_served goes blank. Blank is the honest cell: it says this row cannot tell you what
    served it. (The id is in the CLI's own stderr log, `modelID=`, but that is a log line whose
    format is not a contract, and it names what was requested rather than what answered.)

    HOW A RUN IS KNOWN TO HAVE FINISHED, which nothing in the stream can tell you. Because there
    is no terminal event, a run cut off after three of ten steps is byte-for-byte a prefix of a
    run that finished: same event types, same well-formed last line, just fewer of them. Treating
    any step_finish as proof of success -- as this did -- turns a killed run into a `success` row
    carrying a fraction of the real cost, and --gate, which only asks whether res_subtype is
    `success`, passes it. The signal is the process exit code, captured beside the stdout by
    launch_implementer. Observed: 0 on a clean finish; 1 on a failure before any step (unknown
    model) and 1 on a provider error that arrived after a step had already been billed.

    So the verdict is:
      - an `error` event names the subtype, whatever the exit code says. It is the most specific
        thing anyone knows about how the run ended, and the steps already paid for stay in the row.
      - exit 0 with no error event is `success`.
      - anything else -- non-zero, or no exit code recorded at all -- is `incomplete_stream`.
        Unknown is not success. A missing exit code means the harness killed the process or the
        stdout came from somewhere that recorded none, and neither is evidence the run completed.

    ABSENT, NOT ZERO. Only fields the stream actually reported are put in the record. A stream
    with recognisable events but no step_finish yields no token counts, no cost and -- if it had
    no step_start either -- no turn count, so those cells are blank rather than a $0.00 0-turn
    run that a campaign would average as real. The record's shape is otherwise the claude one, so
    step9_parse_and_write, step7a's cost tie-break and the fix call's token columns are unchanged.

    Returns None only when the stdout contained no recognisable event at all, which is the same
    thing `unparsable` has always meant in res_subtype.
    """
    steps = 0
    finishes = 0
    tool_calls = 0
    stop_reason = ""
    error_name = ""
    error_status = None
    cost = None
    # None until an event reports the field, so a count that stays None is one the engine never
    # gave rather than one it gave as zero.
    tk = {"input_tokens": None, "output_tokens": None, "thinking": None,
          "cache_write": None, "cache_read": None}
    error = ""
    events = stream_events(raw)
    if not events:
        return None
    for ev in events:
        kind = ev.get("type") or ev.get("event") or ""
        if kind == "step_start":
            steps += 1
        elif kind == "tool_use":
            # What the agent DID, as against how many model calls it took. Counted from the
            # stream because the run record has no such total anywhere.
            tool_calls += 1
        elif kind == "step_finish":
            finishes += 1
            # `part` is where opencode puts it; the event itself is the fallback so a stream that
            # is flatter -- codex, or a later opencode -- still accounts rather than silently
            # totalling nothing, which is the exact way this failed before.
            part = ev.get("part")
            part = part if isinstance(part, dict) else ev
            # The LAST step's reason is how the run ended. "stop" is a model that chose to stop;
            # anything else -- a length cap, a tool limit -- is the run being cut short, which
            # res_subtype cannot distinguish because both reach exit 0.
            reason = part.get("reason") or ev.get("reason")
            if isinstance(reason, str) and reason.strip():
                stop_reason = reason.strip()[:40]
            c = _num(part.get("cost"))
            if c is None:
                c = _num(ev.get("cost"))
            if c is not None:
                cost = c if cost is None else cost + c
            tokens = part.get("tokens")
            if not isinstance(tokens, dict):
                tokens = ev.get("tokens")
            if isinstance(tokens, dict):
                cache = tokens.get("cache")
                cache = cache if isinstance(cache, dict) else {}
                for key, src in (("input_tokens", tokens.get("input")),
                                 ("output_tokens", tokens.get("output")),
                                 ("thinking", tokens.get("reasoning")),
                                 ("cache_write", cache.get("write")),
                                 ("cache_read", cache.get("read"))):
                    n = _num(src)
                    if n is None:
                        continue
                    tk[key] = n if tk[key] is None else tk[key] + n
        elif kind == "error":
            # Kept as the subtype rather than raised: an error event is how the run ended, and a
            # row that records it is worth more than an exception that discards the tokens spent.
            # The detail is nested -- {"error":{"name":"APIError","data":{"message":...}}} was
            # what the CLI actually wrote -- so the top-level lookup this used to do found neither
            # and recorded every failure as the bare word "error".
            err = ev.get("error")
            err = err if isinstance(err, dict) else {}
            data = err.get("data")
            data = data if isinstance(data, dict) else {}
            name = (err.get("name") or ev.get("name") or data.get("message")
                    or err.get("message") or ev.get("message") or "error")
            error = str(name)[:80]
            # Kept separately from the subtype as well. res_subtype carries whatever this
            # resolved to and is what --gate reads, but it collapses every failure into one
            # string: four workspace permission rejections and a Vulkan OOM all read APIError
            # on 2026-09-12. The class and the HTTP status are what separate them.
            error_name = str(err.get("name") or name)[:60]
            status = _num(data.get("statusCode"))
            if status is None:
                status = _num(err.get("statusCode") or ev.get("statusCode"))
            if status is not None:
                error_status = status

    if error:
        subtype = error
    elif exit_code == 0:
        subtype = "success"
    else:
        subtype = "incomplete_stream"

    usage = {}
    if tk["input_tokens"] is not None:
        usage["input_tokens"] = _tidy(tk["input_tokens"])
    if tk["output_tokens"] is not None:
        usage["output_tokens"] = _tidy(tk["output_tokens"])
    if tk["thinking"] is not None:
        usage["output_tokens_details"] = {"thinking_tokens": _tidy(tk["thinking"])}
    if tk["cache_write"] is not None:
        usage["cache_creation_input_tokens"] = _tidy(tk["cache_write"])
    if tk["cache_read"] is not None:
        usage["cache_read_input_tokens"] = _tidy(tk["cache_read"])

    rec = {"usage": usage, "subtype": subtype}
    if cost is not None:
        rec["total_cost_usd"] = round(cost, 6)
    # Absent, not zero, on the same rule as the token counts above: a stream that named no
    # reason, no error class and no tool use leaves those cells blank rather than asserting
    # "stopped normally, no errors, did nothing".
    if stop_reason:
        rec["stop_reason"] = stop_reason
    if error_name:
        rec["error_name"] = error_name
    if error_status is not None:
        rec["error_status"] = error_status
    if tool_calls:
        rec["tool_calls"] = tool_calls
    if steps or finishes:
        # A stream that produced step events can answer how many; one that produced none cannot,
        # and 0 turns would read as a run that did nothing rather than a run that did not say.
        rec["num_turns"] = steps
    return rec


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

    A name the project itself ships (p04_python_xlarge's TASK_BACKLOG.md) is not evidence of anything:
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

    A project whose format is defined by a fixture (p04_python_xlarge) is otherwise passable by
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
    # (p05_python_refactor_large's strict reduction) can be fully green on the tests and still not
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
    # Read from the workspace as the agent left it, in the same step that scores it, so the two
    # always describe the same bytes.
    ok, err = workspace_syntax(workspace)
    out["res_syntax_ok"] = ok
    out["res_syntax_error"] = err
    out["res_collection_errors"] = collection_errors(run_dir)
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


def workspace_syntax(workspace):
    """(ok, first_error) for every .py the agent left behind, by parsing them.

    ast.parse rather than importing: importing runs module-level code, which is the agent's code
    and must not execute inside the harness. Parsing answers exactly the question asked -- is
    this a Python file at all -- and answers it for the tests the agent may have broken as well
    as for the source it wrote.

    .venv and __pycache__ are skipped: they are not the agent's work, and a vendored package with
    a deliberate syntax error for a version guard would otherwise fail a run that is fine.
    """
    skip = {".venv", "__pycache__", ".git", ".pytest_cache"}
    worst = ""
    seen = 0
    for path in sorted(Path(workspace).rglob("*.py")):
        if any(part in skip for part in path.parts):
            continue
        seen += 1
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            if not worst:
                worst = "%s:%s %s" % (path.name, exc.lineno, (exc.msg or "")[:60])
        except (OSError, ValueError) as exc:
            if not worst:
                worst = "%s: %s" % (path.name, str(exc)[:60])
    if not seen:
        return "", ""
    return str(not worst).lower(), worst


def collection_errors(run_dir):
    """How many test files pytest could not even collect, from its own junit.xml.

    Distinct from a failing test: a collection error means the file never ran. Counted rather
    than flagged, because one unimportable module among ten is a different state from all ten.
    """
    path = Path(run_dir) / "junit.xml"
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return len(re.findall(r"<error\b", text))


def step9_parse_and_write(cfg, run_dir, row):
    """Parse result.json, print the row and write results_run.csv."""
    blank = {c: "" for c in COLUMNS}
    blank.update(row)
    row = blank
    raw = (run_dir / "result.json").read_text(encoding="utf-8") if (run_dir / "result.json").is_file() else ""
    data = engine_result_record(cfg, raw, read_exit_code(run_dir / "result.json"))

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
            # From the same winning entry, so it describes the model that did the work rather
            # than the auxiliary one. It is what tk_input has to be read against: 277k tokens
            # means one thing in a 200k window and another in a 1M one.
            if isinstance(entry, dict):
                row["res_context_window"] = entry.get("contextWindow", "")
        else:
            # An endpoint that is not this vendor's own may report no modelUsage at all
            # (cfg_provider, chapter 9): the block is absent, or every costUSD in it is zero and
            # the outputTokens tie-break above is what carries it. The guard against a silently
            # substituted model must not go blank exactly where substitution is likeliest -- a
            # gateway that auto-routes, a local tag such as `:latest` -- so the served id falls
            # back to the result record's own `model` field where the engine offers one. Blank
            # still means the row cannot answer what served it, which is what a reader comparing
            # it with cfg_model has to know.
            served = data.get("model")
            row["res_model_served"] = served.strip() if isinstance(served, str) else ""
        ms = data.get("duration_ms")
        if isinstance(ms, (int, float)):
            row["prf_duration_s"] = round(ms / 1000.0, 1)

        # --- how it ended ----------------------------------------------------------------
        # Both engines answer, under different names: claude writes stop_reason (and
        # terminal_reason when the CLI itself ended the run), opencode's last step carries
        # `reason`, normalised to stop_reason by stream_result_record.
        stop = data.get("stop_reason") or data.get("terminal_reason")
        row["res_stop_reason"] = str(stop).strip()[:40] if isinstance(stop, str) and stop.strip() else ""

        # claude signals an error with is_error plus api_error_status; opencode names the class
        # and the HTTP status. res_subtype keeps carrying whichever string --gate reads, and
        # these two say what it actually was.
        err_name = data.get("error_name")
        if not err_name and data.get("is_error"):
            err_name = data.get("api_error_status") or "error"
        row["res_error_name"] = str(err_name).strip()[:60] if err_name else ""
        status = data.get("error_status")
        if status is None:
            status = data.get("api_error_status")
        row["res_error_status"] = status if isinstance(status, (int, float)) else ""

        # --- how much machinery ----------------------------------------------------------
        row["res_tool_calls"] = data.get("tool_calls", "")
        if isinstance(stats, dict) and stats:
            row["res_subagents_failed"] = stats.get("failed", "")
            refused = stats.get("refused")
            # A dict of reasons (budget, concurrency_limit, depth_limit): the total is what says
            # a methodology asked for delegation it did not get.
            row["res_subagents_refused"] = (
                sum(v for v in refused.values() if isinstance(v, (int, float)))
                if isinstance(refused, dict) else (refused if isinstance(refused, (int, float)) else ""))

        server_tools = usage.get("server_tool_use")
        if isinstance(server_tools, dict):
            row["res_web_searches"] = server_tools.get("web_search_requests", "")
        row["res_service_tier"] = usage.get("service_tier", "")

        api_ms = data.get("duration_api_ms")
        if isinstance(api_ms, (int, float)):
            row["prf_api_s"] = round(api_ms / 1000.0, 1)
        ttft = data.get("ttft_ms")
        if isinstance(ttft, (int, float)):
            row["prf_ttft_s"] = round(ttft / 1000.0, 2)

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
    mth = step5_deploy_entry_file(cfg, run_dir, workspace)
    _, user_md, cli_version = step6_environment_and_preflight(cfg, project, template, workspace,
                                                              run_dir)
    baseline = read_triple(run_dir / "verification_baseline.txt")
    tools, cfg_tools = allowed_tools(methodology, project)
    cfg_tools = record_tool_enforcement(cfg, cfg_tools)
    # Read here and nowhere else: after the workspace is built and the preflight has run, before
    # a single token is spent, so the figure is memory as the model finds it. Reading it after
    # the run would record what the run left behind, which answers a different question.
    free_ram = read_free_ram_gb()
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
           "cfg_entry_file": engine_spec(cfg)["entry_file"],
           "cfg_review_pass": cfg["REVIEW_PASS"], "cfg_review_model": review_model(cfg),
           "cfg_fix_model": fix_model(cfg),
           "cfg_review_prompt": ("" if cfg["REVIEW_PASS"] == "none"
                                 else review_prompt_path(cfg).name),
           "cfg_review_weight": ("" if cfg["REVIEW_PASS"] == "none" else review_weight(cfg)),
           "cfg_tools": cfg_tools,
           "cfg_walltime_s": CLI_TIMEOUT_S,
           "cfg_free_ram_gb": free_ram,
           "res_score_baseline": baseline["score"],
           "prf_duration_s": round(wall, 1)}
    row.update(engine_columns(cfg))
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


# --- the sc_* score columns (chapter 13.1b) -------------------------------------------------
# (column, direction, group). down = smaller is better, up = larger is better.
SCORE_COLUMNS = [
    ("prf_duration_s", "sc_duration", "down", "effort"),
    ("prf_turns", "sc_turns", "down", "effort"),
    ("tk_output", "sc_output", "down", "effort"),
    ("tk_cost_usd", "sc_cost_usd", "down", ""),
    ("res_mi", "sc_mi", "up", "quality"),
    ("res_max_nesting", "sc_max_nesting", "down", "quality"),
    ("res_max_func_sloc", "sc_max_func_sloc", "down", "quality"),
]
SCORE_COMPOSITES = [("sc_effort", "effort"), ("sc_quality", "quality")]

# sc_overall_ratio = sc_quality / (RATIO_MID - RATIO_HALF * sc_effort).
#
# The divisor maps sc_effort's 0..1 onto a short band centred on 1.0: 1.25 for the most expensive
# run in the table, 1.00 at median effort, 0.75 for the cheapest run of a project. Note the minus
# sign -- sc_effort is an effort SCORE, 1.0 meaning little was spent, so a rising score must lower
# the divisor. Dividing by sc_effort itself would reward waste.
#
# Read as: above sc_quality means effort paid for itself, below means it did not; at median effort
# the ratio IS sc_quality. Bounded away from zero by construction, so no clamp and no special case,
# and the half-width keeps quality the dominant term -- effort can move a run by at most a third.
# Range is 0..1.333, not 0..1: this is a ratio, not another normalised column.
RATIO_MID = 1.25
RATIO_HALF = 0.5

# Columns retired from the schema, dropped from every row on consolidation. `sc_cost` is the
# pre-rename spelling of `sc_cost_usd` and `sc_overall` of `sc_overall_mean`; the `idx_*` block is
# the index generation the `sc_*`
# columns replaced. Both are recomputed from the raw metrics, so nothing is lost by dropping them.
RETIRED_COLUMNS = frozenset([
    "sc_cost", "sc_overall",
    "idx_duration", "idx_turns", "idx_output", "idx_cost", "idx_mi",
    "idx_max_nesting", "idx_max_func_sloc", "idx_complexity", "idx_sloc",
    "idx_effort", "idx_effort_n", "idx_quality", "idx_quality_n",
])


def log_lag(value, best, direction):
    """How far behind its project's leader a run is, in logarithms -- 0 for the leader itself.

    Logarithms because these quantities spread multiplicatively: duration runs from 21 seconds to
    over twenty minutes, a factor of 1125. On the raw scale that one run owns the whole range and
    every realistic difference is squeezed into the last two percent -- measured on this table, 95%
    of all rows then sit between 0.9 and 1.0, and 48 arms of p04 are separated in the third decimal.
    In logarithms one doubling is one distance, wherever it happens: twice as slow costs the same
    from 20 to 40 seconds as from 600 to 1200.
    """
    ratio = (value / best) if direction == "down" else (best / value)
    return math.log(ratio) if ratio > 0 else None


def apply_score_columns(records):
    """Write sc_* into every record, in place. Derived, deterministic, recomputed every time.

    Per column: the best run OF EACH PROJECT scores 1.0, the worst run of the WHOLE TABLE scores
    0.0, everything else sits between, nothing is clipped. One shared denominator -- the largest
    lag anywhere -- so a distance means the same in every project, while the anchor stays local so
    each project is read on its own. A project whose arms tie therefore stays bunched just under
    1.0 instead of being stretched across the full range, which is what a per-project min-max would
    have done: saturation keeps looking like saturation.

    No base file, no reference solution, no starting state: a constant divisor cancels in the
    difference of two logarithms, so the raw measured column is all this needs.

    Gated on res_verification_passed -- without it the effort columns crown the run that gave up
    after two turns, the fastest and cheapest row of its project.

    What it does NOT say: whether one project's leader is better than another's. Every project's
    best is 1.0 by construction. That comparison lives in the measured columns.
    """
    names = [n for _, n, _, _ in SCORE_COLUMNS] + [n for n, _ in SCORE_COMPOSITES] + \
        ["sc_overall_mean", "sc_overall_ratio"]
    for rec in records:
        for name in names:
            rec.setdefault(name, "")
    scored = [r for r in records
              if str(r.get("res_verification_passed", "")).strip().lower() == "true"]
    if not scored:
        return records

    for source, name, direction, _group in SCORE_COLUMNS:
        by_project = {}
        for rec in scored:
            value = as_float(rec.get(source))
            if value is None or value <= 0:
                continue
            by_project.setdefault(rec.get("prj_name", ""), []).append((rec, value))
        lags = []
        for _project, entries in by_project.items():
            values = [v for _, v in entries]
            best = min(values) if direction == "down" else max(values)
            for rec, value in entries:
                lag = log_lag(value, best, direction)
                if lag is not None:
                    lags.append((rec, lag))
        if not lags:
            continue
        worst = max(lag for _, lag in lags)
        for rec, lag in lags:
            rec[name] = "%.5f" % (1.0 - lag / worst) if worst > 0 else "1.00000"

    # The composites are means, not products: after the transform these are distances on one
    # scale, not ratios, so they add. A factor a row is missing drops out of its own mean.
    for rec in scored:
        parts = {}
        for _source, name, _direction, group in SCORE_COLUMNS:
            value = as_float(rec.get(name))
            if group and value is not None:
                parts.setdefault(group, []).append(value)
        for name, group in SCORE_COMPOSITES:
            values = parts.get(group) or []
            if values:
                rec[name] = "%.5f" % (sum(values) / len(values))
        both = [as_float(rec.get(n)) for n, _ in SCORE_COMPOSITES]
        both = [v for v in both if v is not None]
        if both:
            rec["sc_overall_mean"] = "%.5f" % (sum(both) / len(both))
        quality = as_float(rec.get("sc_quality"))
        effort = as_float(rec.get("sc_effort"))
        if quality is not None and effort is not None:
            rec["sc_overall_ratio"] = "%.5f" % (quality / (RATIO_MID - RATIO_HALF * effort))
    return records


def score_anchor_report(records):
    """One line per sc_ column: which run set the 0.0 end, and how large the whole lag was."""
    lines = []
    scored = [r for r in records
              if str(r.get("res_verification_passed", "")).strip().lower() == "true"]
    for source, name, direction, _group in SCORE_COLUMNS:
        worst, span = None, 0.0
        by_project = {}
        for rec in scored:
            value = as_float(rec.get(source))
            if value is not None and value > 0:
                by_project.setdefault(rec.get("prj_name", ""), []).append((rec, value))
        for _project, entries in by_project.items():
            values = [v for _, v in entries]
            best = min(values) if direction == "down" else max(values)
            for rec, value in entries:
                lag = log_lag(value, best, direction)
                if lag is not None and lag > span:
                    worst, span = rec, lag
        if worst is not None:
            lines.append("%-18s span=%.3f (0.0 set by %s / %s / %s)"
                         % (name, span, worst.get("prj_name", ""), worst.get("mth_name", ""),
                            worst.get("cfg_campaign", "").replace(".llm_config.", "")))
    return lines


def score_spread_report(records):
    """One descriptive line per campaign and project: arms, score range, distinct values.

    Deliberately descriptive and not a verdict. Whether a project still discriminates is read off
    the spread, and a threshold that decided it for the reader would be a constant nobody measured
    -- on top of rows that are usually one run per arm, where a spread of zero can be saturation or
    can be sampling. So the line states what is there and leaves the judgement to chapter 16 and to
    the reader: `1 distinct value` across every arm is the whole finding.
    """
    groups = {}
    for r in records:
        campaign, project = r.get("cfg_campaign", ""), r.get("prj_name", "")
        score = as_float(r.get("res_score"))
        if not project or score is None:
            continue
        groups.setdefault((campaign, project), []).append((r.get("mth_name", ""), score))
    lines = []
    for (campaign, project), arms in sorted(groups.items()):
        scores = [s for _, s in arms]
        distinct = len({round(s, 4) for s in scores})
        lines.append("%s / %s: %d arm(s), res_score %.3f-%.3f, %d distinct value(s)"
                     % (campaign, project, len(arms), min(scores), max(scores), distinct))
    return lines


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
    # Derived last, over the merged rows, so the whole table is recomputed from the frozen bases
    # on every consolidation -- an index is never carried over from an earlier write.
    apply_score_columns(records)
    # Retired columns. The carry-over above keeps any key an older row wrote, which is what a
    # reader wants for a column that was merely renamed away from -- but a retired generation of
    # score columns would then outlive every row that produced it. These are dropped on read, so
    # one consolidation is enough to clear them from the published table for good.
    for rec in records:
        for dead in RETIRED_COLUMNS:
            rec.pop(dead, None)
    extra = [k for rec in records for k in rec if k not in COLUMNS and k not in seen]
    columns = list(COLUMNS) + [c for c in seen if c not in COLUMNS and c not in RETIRED_COLUMNS] + \
        sorted(set(extra), key=extra.index)
    out = RESULTS_TABLE
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(str(out), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow([csv_name(c) for c in columns])
        for rec in records:
            w.writerow([rec.get(c, "") for c in columns])
    # Read off the rows as written, not off `seen`: the derived columns are added after the merge,
    # so a check against the input keys reported every idx_* column as blank while it was filled.
    carried = {c for rec in records for c, v in rec.items() if str(v).strip()}
    missing = [c for c in COLUMNS if c not in carried]
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
    for line in score_spread_report(records):
        print("  %s" % line)
    for line in score_anchor_report(records):
        print("  %s" % line)
    # The chart is written from the rows just written, never from a second read of the file: the
    # two artifacts then cannot disagree about what was consolidated.
    chart = ROOT / "results_pareto.svg"
    panels, points = write_pareto_svg(records, chart)
    print("wrote %s (%d panel(s), %d point(s))" % (chart, panels, points))


# Panel geometry in px. The plot area is the same size in every panel so two panels of one chart
# are read against each other by eye; only the axis maximum differs, and it is labelled.
CHART_PLOT_W, CHART_PLOT_H = 720, 360
CHART_PAD_L, CHART_PAD_R, CHART_PAD_T, CHART_PAD_B = 58, 22, 34, 46
CHART_HEADER_H, CHART_GAP = 46, 26


def svg_num(value):
    """A coordinate as short, stable text -- 2 decimals, trailing zeros and a signed zero dropped.

    Every number in the file goes through this. `%r` on a float writes the platform's shortest
    repr, which is one more thing that can differ between two machines rebuilding the same rows;
    a fixed two decimals cannot, and the chart is read at a pixel, not at a micron.
    """
    text = "%.2f" % value
    if text.endswith(".00"):
        text = text[:-3]
    elif text.endswith("0"):
        text = text[:-1]
    return "0" if text in ("-0", "-0.0") else text


def svg_text(value):
    """XML-escape a label: campaign and project names reach the file as text and must escape."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pareto_front(points):
    """The front of `(cost, score, ...)` tuples: a point no cheaper point beats on score.

    Sorted by cost, a point is on the front when its score is strictly above every *strictly
    cheaper* point's. Equal costs are settled as a group rather than one after the other, so two
    arms that cost the same both survive if they beat everything below them -- resolving them in
    list order would have kept whichever happened to be first.
    """
    out, best_below, i = [], None, 0
    ordered = sorted(points)
    while i < len(ordered):
        j = i
        while j < len(ordered) and ordered[j][0] == ordered[i][0]:
            j += 1
        group = ordered[i:j]
        for p in group:
            if best_below is None or p[1] > best_below:
                out.append(p)
        top = max(p[1] for p in group)
        best_below = top if best_below is None else max(best_below, top)
        i = j
    return out


def write_pareto_svg(records, out_path):
    """Write the cost/score Pareto chart of these rows to `out_path`; return (panels, points).

    A hand-written SVG rather than a plotting library: the harness is stdlib only (chapter 8), and
    the chart is a *derived* file living beside `results_repository.csv` in the repository, so it
    is regenerated on every consolidation and must be byte-identical for identical rows or every
    rebuild would show up as a diff nobody made.

    One panel per (`cfg_campaign`, `prj_name`) pair, never pooled: chapter 17 forbids reading rows
    whose constants differ as one set, and a cost axis shared between two models would say exactly
    the thing that chapter denies. Points are labelled with the arm's number, `*_outdated` arms are
    drawn hollow so they stay visible without competing, and the front joins the live points no
    cheaper point beats -- the one line the eye is meant to follow.
    """
    groups = {}
    for rec in records:
        cost = as_float((rec.get("tk_cost_usd") or "").strip())
        score = as_float((rec.get("res_score") or "").strip())
        if cost is None or score is None:
            continue
        name = (rec.get("mth_name") or "").strip()
        key = ((rec.get("cfg_campaign") or "").strip(), (rec.get("prj_name") or "").strip())
        # The arm's number: what stands before the first `_`, minus the kind letter the naming
        # standard puts in front of it (m29_... -> 29), cut to two characters. Without the strip
        # every methodology on the chart would read "m2", "m3", "m4". A name that is not numbered
        # still gets its first two characters, so no point on the chart is unlabelled.
        head = name.split("_")[0]
        if head[:1] in ("p", "m", "e") and head[1:3].isdigit():
            head = head[1:]
        label = head[:2] or name[:2]
        groups.setdefault(key, []).append((cost, score, label, name.endswith("_outdated")))

    body, panels, total = [], sorted(groups), 0
    width = CHART_PAD_L + CHART_PLOT_W + CHART_PAD_R
    panel_h = CHART_PAD_T + CHART_PLOT_H + CHART_PAD_B
    height = CHART_HEADER_H + max(1, len(panels)) * (panel_h + CHART_GAP)
    for n, key in enumerate(panels):
        top = CHART_HEADER_H + n * (panel_h + CHART_GAP)
        total += len(groups[key])
        body.extend(pareto_panel(key, sorted(groups[key]), top))

    lines = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%s" height="%s">'
             % (svg_num(width), svg_num(height), svg_num(width), svg_num(height)),
             "<style>",
             "text{font-family:'Segoe UI',system-ui,-apple-system,'DejaVu Sans',sans-serif;"
             "fill:#1f2933}",
             ".ttl{font-size:13px;font-weight:600} .hd{font-size:12px} .lg{font-size:10px;"
             "fill:#6b7280} .ax{font-size:10px;fill:#4b5563} .lb{font-size:9px} "
             ".lbo{font-size:9px;fill:#9aa3ad}",
             ".grid{stroke:#e5e7eb;stroke-width:1} .axis{stroke:#9aa3ad;stroke-width:1}",
             ".pt{fill:#1f2933} .pto{fill:none;stroke:#9aa3ad;stroke-width:1.2}",
             ".front{fill:none;stroke:#1f2933;stroke-width:1.2;opacity:0.55}",
             "</style>",
             '<rect x="0" y="0" width="%s" height="%s" fill="#ffffff"/>'
             % (svg_num(width), svg_num(height))]
    if not panels:
        # Still a valid SVG: a consolidation that produced no plottable row must leave a file that
        # opens and says so, not a stale chart of the previous rows and not a parse error.
        lines.append('<text class="hd" x="%s" y="%s">no rows</text>'
                     % (svg_num(CHART_PAD_L), svg_num(CHART_HEADER_H)))
    else:
        lines.append('<text class="hd" x="%s" y="20">score against cost, one panel per campaign '
                     "and project</text>" % svg_num(CHART_PAD_L))
        lines.append('<text class="lg" x="%s" y="36">filled = live arm, hollow = *_outdated; the '
                     "line is the Pareto front of the live arms</text>" % svg_num(CHART_PAD_L))
    lines.extend(body)
    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(out_path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return len(panels), total


def pareto_panel(key, points, top):
    """The SVG lines of one panel: frame, grid, axes, front, points and labels, offset by `top`."""
    campaign, project = key
    left, base = CHART_PAD_L, top + CHART_PAD_T + CHART_PLOT_H
    # A "nice" maximum -- the next half dollar above the dearest arm -- so the axis of a panel does
    # not move by a cent when one run is added, and two rebuilds a run apart stay comparable.
    steps = int(max(p[0] for p in points) / 0.5) + 1
    x_max = max(0.5, steps * 0.5)
    x_step = 1.0 if x_max > 5 else 0.5
    # The score axis is adaptive: 1.0 down to the tenth below the worst arm. A fixed 0..1 axis put
    # every point of a working campaign in the top sixth of the panel -- arms differ by hundredths
    # where the axis counts in tenths -- so the differences the chart exists for were invisible.
    # Held in hundredths so the ticks land where the labels say and not a rounding error away.
    # Capped at 0.9 so a panel whose arms all score 1.00 still has an axis with a span.
    y_min_h = min(90, max(0, int(min(p[1] for p in points) * 10) * 10))
    span_h = 100 - y_min_h
    y_step_h = 10 if span_h >= 50 else (5 if span_h >= 25 else 2)
    y_fmt = "%.1f" if y_step_h == 10 else "%.2f"

    def px(cost):
        return left + CHART_PLOT_W * (cost / x_max)

    def py(score):
        share = (min(max(score, y_min_h / 100.0), 1.0) - y_min_h / 100.0) / (span_h / 100.0)
        return base - CHART_PLOT_H * share

    out = ['<text class="ttl" x="%s" y="%s">%s  &#8212;  %s</text>'
           % (svg_num(left), svg_num(top + 20), svg_text(project), svg_text(campaign)),
           '<rect x="%s" y="%s" width="%s" height="%s" fill="#fbfbfc" stroke="#e5e7eb"/>'
           % (svg_num(left), svg_num(top + CHART_PAD_T), svg_num(CHART_PLOT_W),
              svg_num(CHART_PLOT_H))]
    for tick_h in range(y_min_h, 101, y_step_h):
        value = tick_h / 100.0
        y = py(value)
        out.append('<line class="grid" x1="%s" y1="%s" x2="%s" y2="%s"/>'
                   % (svg_num(left), svg_num(y), svg_num(left + CHART_PLOT_W), svg_num(y)))
        out.append(('<text class="ax" x="%s" y="%s" text-anchor="end">' + y_fmt + "</text>")
                   % (svg_num(left - 8), svg_num(y + 3), value))
    i = 0
    while i * x_step <= x_max + 1e-9:
        value = i * x_step
        x = px(value)
        out.append('<line class="grid" x1="%s" y1="%s" x2="%s" y2="%s"/>'
                   % (svg_num(x), svg_num(top + CHART_PAD_T), svg_num(x), svg_num(base)))
        out.append('<text class="ax" x="%s" y="%s" text-anchor="middle">%.1f</text>'
                   % (svg_num(x), svg_num(base + 15), value))
        i += 1
    out.append('<line class="axis" x1="%s" y1="%s" x2="%s" y2="%s"/>'
               % (svg_num(left), svg_num(base), svg_num(left + CHART_PLOT_W), svg_num(base)))
    out.append('<line class="axis" x1="%s" y1="%s" x2="%s" y2="%s"/>'
               % (svg_num(left), svg_num(top + CHART_PAD_T), svg_num(left), svg_num(base)))
    out.append('<text class="ax" x="%s" y="%s" text-anchor="middle">cost (USD)</text>'
               % (svg_num(left + CHART_PLOT_W / 2.0), svg_num(base + 33)))
    mid_x, mid_y = svg_num(left - 38), svg_num(top + CHART_PAD_T + CHART_PLOT_H / 2.0)
    out.append('<text class="ax" x="%s" y="%s" text-anchor="middle" transform="rotate(-90 %s %s)">'
               "score</text>" % (mid_x, mid_y, mid_x, mid_y))

    front = pareto_front([p for p in points if not p[3]])
    if len(front) > 1:
        out.append('<polyline class="front" points="%s"/>'
                   % " ".join("%s,%s" % (svg_num(px(p[0])), svg_num(py(p[1]))) for p in front))
    # Labels are placed greedily in cost order: the first offset from the point that does not hit a
    # label already placed, nearest offset first, right before left. Every arm of a project sits in
    # one dense cluster -- scores differ by hundredths where costs differ by a factor of twenty --
    # and one label per point above it made that cluster a single illegible smear. Alternating
    # around the point and then stepping away from it keeps almost all of them readable; the cost
    # is a label a row further from its own circle, which is the cheaper of the two confusions.
    # Points sitting at the top of the plot are offered the room below them first, so a label of a
    # score-1.0 arm does not climb out of the panel and into the title.
    placed = []

    def free(box):
        return not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3]
                       for b in placed)

    for cost, score, label, outdated in points:
        x, y = px(cost), py(score)
        out.append('<circle class="%s" cx="%s" cy="%s" r="3.2"/>'
                   % ("pto" if outdated else "pt", svg_num(x), svg_num(y)))
        w = len(label) * 5.4
        rungs = (9, -4, 18, -13, 27, -22, 36, -31, 45, -40) if y - (top + CHART_PAD_T) < 16 else \
                (-4, 9, -13, 18, -22, 27, -31, 36, -40, 45)
        boxes = [(dx, dy, (x + dx, y + dy - 8, x + dx + w, y + dy + 1))
                 for dy in rungs for dx in (5, -5 - w, 8 + w, -8 - 2 * w)]
        # Inside the plot rectangle first: a label pushed out of it lands on the panel title or on
        # the axis, which reads as a caption of the chart rather than the name of a point.
        inside = [c for c in boxes
                  if c[2][1] >= top + CHART_PAD_T and c[2][3] <= base] or boxes[:1]
        dx, dy, box = ([c for c in inside if free(c[2])] or inside)[0]
        placed.append(box)
        out.append('<text class="%s" x="%s" y="%s">%s</text>'
                   % ("lbo" if outdated else "lb", svg_num(x + dx), svg_num(y + dy),
                      svg_text(label)))
    return out


GATE_ANCHOR_MTH = "m47_sabotage"
# The incumbent is the arm the sabotage anchor must lose to (chapter 16). It was the four-feature
# stack m08_process_doctypes_roles_guardrails until the level-3 screen of 8 Sep put that arm last on
# the ranking project; since 9 Sep it is the composition that led the screen at the lowest cost,
# provisionally until repeats confirm it. The legacy name lets rows of the previous incumbent still
# be found by campaigns that predate the change -- they are read only when no current rows exist.
GATE_INCUMBENT_MTH = "m29_invariants_test_first_relative_stop"
GATE_INCUMBENT_LEGACY = "m08_process_doctypes_roles_guardrails"
GATE_ANCHOR_PRJ = "p00_fail"


# Chapter 17 forbids pooling rows whose constants differ, and cfg_campaign is only the config
# file's base name: two different files of the same name, or one edited between two runs, share the
# label. These are the columns one campaign must agree on for the label to mean anything.
CAMPAIGN_CONSTANTS = ("cfg_model", "cfg_provider", "cfg_endpoint", "cfg_effort",
                      "cfg_review_pass", "cfg_review_model",
                      "cfg_fix_model", "cfg_review_weight", "cfg_tools",
                      # The harness bound the run was censored at. See the column's own note in
                      # COLUMNS: rows on either side of the 2026-09-13 change to CLI_TIMEOUT_S
                      # were never poolable, and this is what finally lets the gate say so.
                      "cfg_walltime_s")


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
            # Current incumbent first; the previous one only where a campaign has none of its rows
            # (chapter 16) -- pooling two different arms under one name would be a third arm.
            good = scores(GATE_INCUMBENT_MTH) or scores(GATE_INCUMBENT_LEGACY)
            if not bad and not good:
                # Not a ranking project of this campaign at all -- the smoke run on
                # p01_python_small carries neither anchor and is not a gap in the gate.
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
    # A directory named *_outdated is an arm kept only for its rows (chapter 19.5): it stays on
    # disk, its rows stay in the table, and no matrix runs it again.
    names = sorted(p.name for p in (ROOT / kind).iterdir()
                   if p.is_dir() and not p.name.startswith("_")
                   and not p.name.endswith("_outdated"))
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

    One implementation of the matrix, which `run_all_e04.bat` and `run_turbo_e01.bat` both call: two nested
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
