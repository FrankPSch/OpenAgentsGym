# Naming standard

`<kind><nn>_<words>` — lowercase `a-z0-9_` only, `nn` two digits, numbers permanent.

| kind | prefix | example |
|---|---|---|
| project | `p` | `p03_python_large` |
| methodology | `m` | `m29_invariants_test_first_relative_stop` |
| engine | `e` | `e06_local_gptoss_20b` |

Rules, in full:

1. **Lowercase only.** Git is case-sensitive and NTFS is not, so a name whose
   capitalisation carries meaning is a name that resolves differently on two
   machines and is wrong on neither. Lowercase-only means a name can never be
   *almost* right.
2. **Two digits, zero-padded.** `p01`, not `p1`, so names sort as numbers.
3. **Numbers are permanent.** Never renumbered, never reused. A retired item
   leaves a gap — `projects/` skips 08 and 09 and that is correct. A number in
   a published row must keep pointing at the same thing forever.
4. **One number, one thing.** `00_empty` and `00_sabotage` both claimed 00
   before this standard; sabotage moved to `m47_sabotage`. A number that
   identifies two things identifies neither.
5. **Words are descriptive, joined by `_`.** No dots, no dashes, no camelCase.

## The engine family token

An engine name carries the ENGINE the registry in `run_master.py` dispatches
on, spelled as a word:

| token | ENGINE | what it is |
|---|---|---|
| `claude` | `claude` | the Claude Code CLI against Anthropic |
| `gpt` | `gpt` | the codex CLI against OpenAI |
| `local` | `opencode` | the opencode CLI against LiteLLM against Ollama |

`local` and `opencode` are the same thing under two names: the word says where
the weights are, the ENGINE says which binary is driven. Two of the three
tokens match their ENGINE exactly; this is the one that does not, and it is
deliberate — the axis an operator cares about when reading a row is local
versus billed.

## The register

| engine | ENGINE | model | state |
|---|---|---|---|
| `e01_claude_haiku_4_5` | claude | claude-haiku-4-5 | active |
| `e02_claude_sonnet_5` | claude | claude-sonnet-5 | active |
| `e03_claude_opus_5` | claude | claude-opus-5 | active |
| `e04_claude_fable_5_1` | claude | claude-fable-5-1 | active |
| `e05_gpt_5_codex` | gpt | gpt-5-codex | active |
| `e06_local_gptoss_20b` | opencode | litellm/gpt-oss-20b | active |
| `e07_local_qwen3_4b` | opencode | litellm/qwen3-4b | active |
| `e08_local_qwen3coder_30b` | opencode | litellm/qwen3-coder-30b | active |
| `e09_claude_gptoss_20b` | claude | gpt-oss-20b | retired |
| `e10_claude_qwen3_4b` | claude | qwen3-4b | retired |

`e09` and `e10` are the Claude CLI pointed at local models through LiteLLM,
reversed on 2026-09-11 after four independent blockers (see `REVERT.md`). They
have no config file. They keep numbers because they name rows that exist, and a
row whose engine has no name is a row nobody can interpret later.

## Where the names appear

Directory names under `projects/` and `methodology/`; config files
`.llm_config.<engine>`; batch filenames (`run_engine_matrix.p03.bat`,
`run_smoke_e02.bat`); the `cfg_campaign`, `mth_name`, `prj_name` and `id_run`
columns of `results_repository.csv`; and run directories, which are
`run_<methodology>_<project>_<stamp>_r<nn>`.

A batch named after an engine is renamed when that engine is renamed. Leaving
`run_all_model_03.bat` driving `e03_claude_opus_5` is exactly the drift this
standard exists to prevent.

## Migration

`migrate_naming.py` performed the one-time rename and is kept as the evidence
for a commit that rewrites recorded history: the rows in
`results_repository.csv` and the run directories they point at were renamed by
that script and by nothing else. It is idempotent — a second run is a no-op.
