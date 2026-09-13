# oam_install — bringing a machine up to run OpenAgentsGym

Written for an agent executing it. Every step has a verification command; run it
and read the output before continuing. A step that "looks installed" but fails
its check is not installed.

Target: Windows. The harness runs elsewhere, but the interpreter pin behaves
differently and a non-Windows run is a smoke test of the plumbing, not a
measurement.

Nothing here is optional-by-taste: each item exists because a run aborts without
it, and the abort code is named.

---

## 0. Read this first: do not clone into a synced folder

**The repository must not live inside OneDrive, Dropbox, or any other syncing
folder.** Clone it somewhere plain — `C:\Users\<you>\GitHub\OpenAgentsGym` is
what this machine uses. `local/` alone reaches six figures of files (one
virtualenv per run), and a sync client will both fight you for them and change
what paths resolve to.

Measured on 2026-09-12, with the repository under
`C:\Users\<you>\OneDrive\Dokumente\GitHub\OpenAgentsGym`:

- **opencode refused to edit its own workspace.** `stderr.txt` recorded
  `permission requested: external_directory (C:\Users\<you>\OneDrive\GitHub\
  OpenAgentsGym\local\runs\...\project_workspace\*); auto-rejecting` — note the
  missing `Dokumente`. OneDrive redirects the localized Documents known folder,
  the workspace canonicalised to a path that does not exist, opencode compared
  it against the session root, decided its own working directory was foreign,
  and denied every write. The agent then ran its turns, edited nothing, and
  scored 0.0000 with `diff_lines=0` — a run that looks like a model failure and
  is not. It hit 4 of 20 opencode runs; the other 16 had empty stderr.
- **A batch file being edited was truncated to zero bytes**, then disappeared,
  while OneDrive held it open.
- **A run directory could not be renamed** for as long as the sync client had
  it.

If `git status` is clean and the remote is up to date, moving is one command —
`robocopy <old> <new> /E /MOVE /XJ`. A plain rename out of the sync root is
refused by the OneDrive filter; robocopy copies and deletes instead. Nothing in
the harness stores an absolute path, so nothing needs repointing afterwards.

---

## 0.1 Read this too: where you are installing to

**If you are an agent running inside a packaged/sandboxed host application, your
`%APPDATA%` writes may be virtualized.** A global npm or uv install then lands in
something like
`…\AppData\Local\Packages\<AppId>\LocalCache\Roaming\` while *appearing* at the
normal path to you. The user's own shell cannot see it, and every batch that
looks for the binary reports "not installed" on a machine where you just
installed it.

Check before installing anything global:

```powershell
Test-Path "$env:LOCALAPPDATA\Packages\*\LocalCache\Roaming"
```

If a package container exists for your host app, **the user must run the npm and
uv installs themselves in their own terminal.** You can still install Ollama and
Python (real system installers, not affected), write config files, and verify.

This cost an afternoon on 2026-09-11. Do not skip it.

---

## 0.5 Prerequisites and the repository

Assumed present, and used without being installed anywhere below. Check each
before starting; a missing one surfaces three sections later as something that
looks unrelated.

```powershell
git --version          # the repository, and the harness records the CLI version
node --version         # opencode ships as an npm package
npm.cmd --version      # note .cmd - see 4.1
uv --version           # optional; LiteLLM can be a uv tool or a pip install
```

| Missing | Install |
|---|---|
| git | `winget install --id Git.Git --silent` |
| node + npm | `winget install --id OpenJS.NodeJS.LTS --silent` |
| uv | `winget install --id astral-sh.uv --silent` |

Open a **new** terminal afterwards: winget updates PATH for future processes,
not the one you are typing in. That alone explains most "it says it is not
installed but I just installed it" reports.

### The repository

```powershell
git clone https://github.com/FrankPSch/OpenAgentsGym.git
cd OpenAgentsGym
```

**Do not put it under a folder that syncs to the cloud.** `local/` is
git-ignored but not sync-ignored, and every run builds its own virtual
environment inside it — a campaign then uploads tens of thousands of small
files. If it must live in a synced folder, exclude `local/` in the sync client.

**No `CLAUDE.md` or `AGENTS.md` may exist in any parent directory** of the
clone. Both CLIs walk upwards and would load it into every run; the pre-flight
aborts rather than measure it (chapter 15).

### Disk

| | |
|---|---|
| three local models | ~35 GB in `%USERPROFILE%\.ollama` |
| opencode binary | ~180 MB |
| Python 3.10 + uv tools | ~1 GB |
| each run's venv | ~50 MB, under `local/runs/`, kept until deleted |

A 43-arm campaign leaves a couple of GB of run directories behind. They are the
evidence for the rows, so do not delete them casually — but they are also why
`local/` must not sync.

---

## 1. Python 3.10 — required, not optional

Projects pin their interpreter (`.environment` → `python=3.10`) and
`interpreter_cmd()` looks for `py -3.10`. Without it **every run exits 3**
(SKIPPED: interpreter not available) before any model is contacted.

```powershell
winget install --id Python.Python.3.10 --silent --accept-source-agreements --accept-package-agreements
```

Verify — the launcher must know it, not just the filesystem:

```powershell
py -0p          # expect a -V:3.10 line
py -3.10 -V
```

A uv- or conda-managed 3.10 does **not** satisfy this: it is not registered with
the `py` launcher.

---

## 2. Ollama — local model server

```powershell
winget install --id Ollama.Ollama --silent --accept-source-agreements --accept-package-agreements
```

### 2.1 Two environment variables that change everything

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_IGPU_ENABLE","1","User")
[Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH","32768","User")
```

- **`OLLAMA_IGPU_ENABLE=1`** — without it Ollama logs
  `dropping integrated GPU; to enable, set OLLAMA_IGPU_ENABLE=1` and runs
  **CPU-only**. On a laptop with an integrated GPU this is the difference between
  usable and not.
- **`OLLAMA_CONTEXT_LENGTH`** — the default is **4096 tokens**, far too small for
  an agent loop that re-sends a system prompt plus tool schemas every turn.

Restart the server after setting them, then confirm it answers:

```powershell
Get-Process ollama* | Stop-Process -Force
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
Start-Sleep 10
(Invoke-RestMethod "http://127.0.0.1:11434/api/version").version
```

### 2.2 Models

Pull **one at a time**. Concurrent pulls stall each other.

```powershell
ollama pull qwen3:4b            #  2.5 GB
ollama pull gpt-oss:20b         #   13 GB
ollama pull qwen3-coder:30b     #   18 GB
```

Progress note: Ollama **preallocates** the blob to full size, so file size is
useless as a progress indicator — a 13 GB file appears instantly and does not
grow. Watch `ollama pull`'s own output, or poll `ollama list` for completion.

```powershell
ollama list     # all three must appear with plausible sizes
```

**Memory:** an 18 GB model needs ~20 GB free or it spills to CPU / fails to
load. Check `FreePhysicalMemory` before expecting the 30B to work, and do not run
two models at once (`/api/ps` shows what is resident; models expire after a few
minutes of disuse).

---

## 3. LiteLLM — the protocol gateway

It is **not a router here and not an agent**. It exists because clients speak
different wire formats: the Claude CLI wants Anthropic `/v1/messages`, opencode
and everything else want OpenAI `/v1/chat/completions`, and Ollama serves only
the latter. LiteLLM translates, and prices every provider so `tk_cost_usd` works.

The config and the Modelfile live in `gateway/` in this repository. **That
folder is deliberately not called `litellm/`** — see 3.2.

### 3.1 Install

Either of these works; pick one and remember which interpreter you used, because
3.3 needs it.

```
py -3 -m pip install "litellm[proxy]"
```

```
uv tool install "litellm[proxy]"
```

The `uv` form is tidier but installs a generated `litellm.exe` shim into
`%USERPROFILE%\.local\bin`, and that shim is what corporate Device Guard /
WDAC policy blocks (3.3, trap A). The `pip` form into the system Python 3.12 has
no such shim in the path you will actually use.

Confirm the package is real and not a shadow (3.2):

```
py -3 -P -c "import litellm; print(litellm.__file__)"
```

A path ending in `site-packages\litellm\__init__.py` is correct. `None` means
you imported a directory, not the package.

### 3.2 Never name a directory `litellm` in the repository root

Python puts the current directory on `sys.path`, and a directory with no
`__init__.py` is still importable as a namespace package. A folder named
`litellm\` next to the batch files therefore *shadows the installed package*:
`import litellm` succeeds, `litellm.__file__` is `None`, and
`litellm.proxy` does not exist, so the proxy cannot start. The symptom looks
like a broken install and is not one.

This is why the config lives in `gateway/`. The same applies to any future
directory: do not name one after a package the harness imports.

### 3.3 Starting it — three traps

**Trap A — the `.exe` shim may be blocked.** On a managed machine
`litellm --config ...` can die with *"wurde durch die Device Guard-Richtlinie
Ihrer Organisation blockiert"* / "blocked by your organization's Device Guard
policy". The policy blocks the generated launcher `.exe`, not Python and not the
package. Call the entry point directly instead — no shim is involved:

```
py -3 -P -c "from litellm.proxy.proxy_cli import run_server; run_server()" --config .\gateway\config.yaml --port 4000
```

Notes on that line, each earned:

- `-P` keeps the current directory off `sys.path`, so 3.2 cannot recur.
- The callable is `run_server`, **not** `cli`. It was `cli` in older releases;
  on 1.100 `from litellm.proxy.proxy_cli import cli` raises `ImportError`. If a
  future release renames it again, list what is there:
  `py -3 -P -c "import litellm.proxy.proxy_cli as m; print(dir(m))"`.
- `py -3 -m litellm` does **not** work: `litellm` is a package with no
  `__main__`.
- Everything after `-c "..."` is passed through to click unchanged, so the flags
  are identical to the blocked command's.

**Trap B — UTF-8.** LiteLLM prints an ASCII-art banner that cannot be encoded in
Windows cp1252: `UnicodeEncodeError: 'charmap' codec can't encode characters`
inside `click.echo`, and the proxy exits before serving anything. Force UTF-8 in
the same window first:

```
cd /d C:\Users\<you>\GitHub\OpenAgentsGym
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
```

**Trap C — a stale proxy silently keeps port 4000, and the new one moves.**
LiteLLM does not fail when the port is taken. It binds a random free port and
says so only in the last line:

```
Uvicorn running on http://0.0.0.0:47675 (Press CTRL+C to quit)
```

Read that line every time. A proxy on 47675 serves nobody: the engines address
4000, and the *old* instance — still running with the *old* config — answers
them. That is a whole campaign measured against the wrong model list, with no
error anywhere. Clear it:

```
netstat -ano | findstr :4000
taskkill /PID <pid> /F
```

**LiteLLM reads its config once, at startup.** Adding a model to the file does
nothing to a running proxy; the leg then fails at the gateway, which reads like
a model failure and is not one. After any change to `gateway/config.yaml`,
restart it and check what is actually served — not that it is up, but *which
names* it has:

```
curl http://127.0.0.1:4000/v1/models -H "Authorization: Bearer sk-oag-local"
```

Four names must come back. Three means you are talking to the stale instance.

### 3.4 The whole start sequence, copy-paste

```
cd /d C:\Users\<you>\GitHub\OpenAgentsGym
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
py -3 -P -c "from litellm.proxy.proxy_cli import run_server; run_server()" --config .\gateway\config.yaml --port 4000
```

Success looks like the four model names listed under
`LiteLLM: Proxy initialized with Config, Set models:` and a final
`Uvicorn running on http://0.0.0.0:4000`. Leave the window open; it is the
gateway. The `register_model: ... has custom pricing but not in built-in cost
map` warnings are expected for every Ollama model and are harmless — the costs
are zero on purpose.

### 3.5 Config

`gateway/config.yaml` is the live file, not an example of one — it is versioned
here because it decides what `cfg_model` means in a published row.
`gateway/Modelfile.qwen3-coder-30b-tuned` sits beside it for the same reason: it
defines the `qwen3-coder:30b-tuned` tag that `e11` runs on, and a row naming a
model built from a file nobody kept is a row nobody can reproduce. Build it
with:

```
ollama create qwen3-coder:30b-tuned -f .\gateway\Modelfile.qwen3-coder-30b-tuned
```

`master_key: sk-oag-local` is in this file and therefore in git history. Treat it
as public: it is a local-only shared secret for a proxy bound to this machine.
Never put a real vendor key in `config.yaml` — use environment variables for
those.

Minimal, honest, no fallbacks. A fallback would silently substitute one model
for another — precisely what `check_model()` forbids for `--fallback-model`,
because it corrupts a comparison with no visible error.

```yaml
model_list:
  - model_name: qwen3-4b
    litellm_params:
      model: ollama_chat/qwen3:4b
      api_base: http://127.0.0.1:11434
      timeout: 3600
    model_info: {mode: chat, input_cost_per_token: 0.0, output_cost_per_token: 0.0, supports_function_calling: true}

  - model_name: gpt-oss-20b
    litellm_params:
      model: ollama_chat/gpt-oss:20b
      api_base: http://127.0.0.1:11434
      timeout: 3600
    model_info: {mode: chat, input_cost_per_token: 0.0, output_cost_per_token: 0.0, supports_function_calling: true}

  - model_name: qwen3-coder-30b
    litellm_params:
      model: ollama_chat/qwen3-coder:30b
      api_base: http://127.0.0.1:11434
      timeout: 3600
    model_info: {mode: chat, input_cost_per_token: 0.0, output_cost_per_token: 0.0, supports_function_calling: true}

  - model_name: qwen3-coder-30b-tuned
    litellm_params:
      model: ollama_chat/qwen3-coder:30b-tuned
      api_base: http://127.0.0.1:11434
      timeout: 3600
    model_info: {mode: chat, input_cost_per_token: 0.0, output_cost_per_token: 0.0, supports_function_calling: true}

router_settings:
  num_retries: 0          # a retry that succeeds hides an instability the campaign should record

litellm_settings:
  drop_params: true       # strip params a local backend rejects
  request_timeout: 3600
  json_logs: true

general_settings:
  master_key: sk-oag-local
  store_model_in_db: false
```

Add a cloud model later by adding an entry — `anthropic/claude-opus-5`,
`openai/gpt-5`, `groq/...` — plus its API key. The client never learns which
vendor answered.

Verify both the health endpoint and that every model name resolves:

```
curl http://127.0.0.1:4000/health/liveliness
curl http://127.0.0.1:4000/v1/models -H "Authorization: Bearer sk-oag-local"
```

---

## 4. opencode — the model-agnostic engine (`ENGINE=opencode`)

### 4.1 Install — three traps in one command

```cmd
npm.cmd install -g --allow-scripts=opencode-ai opencode-ai
```

- **`npm.cmd`, not `npm`** — in PowerShell, `npm` resolves to `npm.ps1`, which the
  default execution policy refuses: *"Die Datei npm.ps1 kann nicht geladen
  werden"* / *"cannot be loaded because running scripts is disabled"*. Using
  `npm.cmd` (or running from `cmd`) avoids changing the policy.
- **`--allow-scripts=opencode-ai`** — the postinstall script is what downloads the
  ~180 MB binary. Without it npm prints `npm warn allow-scripts` and you get a
  package with no executable.
- **Not elevated** — an elevated shell resolves `%APPDATA%` to a different
  profile.

### 4.2 The binary the harness needs is NOT the one on PATH

npm puts `opencode.cmd` (a shim) on PATH. `resolve_cli()` **correctly refuses
it** — `CreateProcess` cannot launch a `.cmd` directly — and the run aborts with
**exit 6**: `'opencode' not found on PATH (shutil.which)`.

The real binary is at `<npm-global>\node_modules\opencode-ai\bin\opencode.exe`
and that directory must be **prepended to PATH** before running the harness.
`run_engine_matrix.bat` does this via `engine_find_opencode.py`, which probes several
locations rather than trusting `%APPDATA%`.

```powershell
py -3 engine_find_opencode.py      # prints the directory, or NONE plus a diagnosis
```

### 4.3 Provider config — user level, not per-run

The harness runs the CLI with cwd set to each run's `project_workspace/`, so a
cwd-level config would have to be planted into every run directory. Put it at
`%USERPROFILE%\.config\opencode\opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "litellm": {
      "npm": "@ai-sdk/openai-compatible",
      "options": { "baseURL": "http://127.0.0.1:4000/v1", "apiKey": "sk-oag-local" },
      "models": {
        "qwen3-4b": {}, "gpt-oss-20b": {}, "qwen3-coder-30b": {}
      }
    }
  },
  "model": "litellm/gpt-oss-20b",
  "small_model": "litellm/gpt-oss-20b",
  "autoupdate": false,
  "share": "disabled"
}
```

- Models must be **listed explicitly** — opencode does not discover them from the
  gateway. A name in LiteLLM but missing here will not resolve.
- Set `small_model` too, or opencode's session-title call goes to an
  unconfigured provider.

Verify end to end before trusting the harness:

```cmd
opencode run "reply with the single word OK" --format json -m litellm/gpt-oss-20b
```

Expect newline-delimited JSON: `step_start`, `tool_use`, `text`, `step_finish`.
Accounting is nested under `part` (`part.cost`, `part.tokens.*`) and is
**per-step**, not cumulative. Exit 0 clean, 1 on failure. No event carries a
model id, which is why `res_model_served` is blank on this engine.

---

## 5. Claude Code CLI — the reference engine (`ENGINE=claude`)

The engine every published row was produced with. Install per Anthropic's own
instructions and sign in; the harness only needs `claude` launchable on PATH.

```powershell
(Get-Command claude).Source
claude --version        # recorded as cfg_cli_version
```

**Auth mode changes two columns**, and the choice is a campaign decision:

| | subscription login | API key |
|---|---|---|
| `tk_cost_usd` | blank — no cost reported | populated |
| `cfg_bound` | `walltime` | `usd` |
| `MAX_BUDGET_USD` | does not bind | binds |

Do not mix modes inside a campaign.

**Pre-flight requirement (chapter 15):** no `CLAUDE.md` or `AGENTS.md` may exist
in any parent directory of the repository. The CLI walks upwards and would load
it into every run; the harness aborts rather than measure it.

**Do not point this CLI at a gateway serving non-Claude models.** It is
unsupported by Anthropic, and it does not work: `HEAD /api/hello` returning 404
stalls it indefinitely, unknown model ids are refused before any network call
(`[claude-code:unrecognized_model]`), and `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1`
does not widen the accepted set. Use `ENGINE=opencode` to reach other models.

---

## 6. Codex CLI — the third engine (`ENGINE=gpt`)

**Not installed and never executed.** Everything about this engine's row in the
registry is documentation-derived: subcommand, flag names, prompt position and
stdout shape are all unverified. A run aborts in pre-flight with **exit 6**
(`'codex' not found on PATH`) — which is the expected result today, and is itself
worth recording, since it proves engine dispatch reaches the binary check.

### 6.1 Install and authenticate

```cmd
npm.cmd install -g @openai/codex
```

`npm.cmd`, not `npm`, for the execution-policy reason in §4.1. Check the package
name against OpenAI's current docs before running it — this line is documented,
not observed, like everything else in this section.

```powershell
(Get-Command codex).Source
codex --version
```

Then authenticate — `codex login` for a ChatGPT plan, or an API key in the
environment. **The choice changes two columns**, exactly as it does for claude
in §5: a subscription login reports no per-run cost, so `tk_cost_usd` is blank
and `cfg_bound` degrades to `walltime`; an API key populates both. Pick one per
campaign and do not mix.

### 6.2 What to verify before trusting a single number

Installing it is not bringing it up. The registry row asserts things nobody has
watched happen, and for `opencode` every one of these answers turned out to
matter — the documented shape was wrong about where the accounting lives, and
reading it wrong would have totalled every run at $0.00.

Run one trivial prompt and capture raw stdout:

```cmd
codex exec --json "reply with the single word OK" > codex_probe.txt 2>&1
```

Then answer, from the file rather than from documentation:

1. **Is stdout newline-delimited JSON, or one document?** `--json` means one
   object in many CLIs and a stream in others. The parser branches on this.
2. **What are the real event `type` values?** The registry assumes a shape; the
   names decide whether the turn count is right or zero.
3. **Do the usage fields sit at the top level or nested?** opencode nests them
   under `part`. A parser reading the wrong level finds nothing and reports a
   free run.
4. **Are cost and tokens per-step increments or cumulative running totals?**
   This needs a *multi-step* run to answer. Summing cumulative values inflates an
   N-step run by roughly N²/2.
5. **Which field carries the model actually served?** If none does,
   `res_model_served` is blank and the guard against silent model substitution
   does not exist on this engine — which is the case for opencode.
6. **What is the exit code on success, and on a failure** such as a bad model
   name? It is the only reliable signal that a stream was truncated.

Correct `ENGINES["gpt"]` against the answers, then flip its `tested` flag. Until
that flag is true the pre-flight prints a bring-up NOTE on every run, and rows
from this engine should not be published.

### 6.3 Known gap

Its `model_rule` is `free`: no alias check is applied, so a bare alias that
silently re-points between campaigns would **not** be caught — unlike
`anthropic_canonical`, which rejects `opus` in favour of `claude-opus-5`. That is
a gap, not a decision. Give it a real rule once the id format is observed.

---

## 7. Verification — run this, not a mental checklist

```cmd
check_engine_matrix.bat
```

**What it does not cover:** for `gpt` it only asks whether `codex` is on PATH.
Once it is, the check says OK and `RESULT: READY` — while the registry row is
still unverified. A green pre-flight is therefore *not* permission to trust a
gpt row; §6.2 is. The pre-flight checks that a binary can be launched, not that
the harness understands what comes back from it.

It verifies, and prints FAIL with a reason for each: opencode resolves to a
launchable `.exe`; `claude` present; `py -3.10` present; Ollama and LiteLLM
answering; all three model names served by the gateway; the opencode provider
config present; every `.llm_config.*` readable.

`RESULT: READY` means a run will reach a model — not that a run will produce a
usable row. Fix every FAIL before going further; a leg that starts without its
model reaching memory still writes a row, and that row scores 0.0000.

---

## 7.5 The first campaign

Do this in order. Each step answers a question the next one assumes.

### Step 1 — the pre-flight (free, runs nothing)

```cmd
check_engine_matrix.bat
```

Expect `RESULT: READY`. What it proves: opencode resolves to a launchable
`.exe`, `py -3.10` is registered, Ollama and LiteLLM answer, the gateway serves
every model the configs name, and every `.llm_config.*` is readable.

What it does **not** prove is in §7 above — for `gpt` it only checks that
`codex` is on PATH.

### Step 2 — the smallest matrix

```cmd
run_engine_matrix.bat
```

`p01_python_small` × `m00_empty` — the smallest project with the no-methodology
anchor — across the local models, plus the `gpt` leg. The claude leg is opt-in
behind `/billed`, because it costs money and the question here is whether the
apparatus works.

Budget roughly an hour: a 20B model on an integrated GPU takes minutes per leg,
and an unproven one is bounded only by `CLI_TIMEOUT_S`.

Read the summary, not the exit codes. Each leg prints `PASS` or `FAIL` derived
from its row — score, subtype, diff lines, verification flag — because
`run_master` exits 0 for any run that reached a row, **including one that says
APIError and scores 0.0000**.

Expected on a correctly set-up machine:

```
e06_local_gptoss_20b  exit=0  PASS   gpt-oss-20b
e07_local_qwen3_4b  exit=0  PASS   qwen3-4b
e08_local_qwen3coder_30b  exit=0  ?      qwen3-coder-30b   - see below
e02_claude_sonnet_5     skipped        (billed, not requested)
e05_gpt_5_codex       exit=6  ABORT  codex not installed - expected
```

`e08_local_qwen3coder_30b` fails with `APIError` on a machine whose integrated GPU cannot
hold 18 GB of weights: `llama-server reported out-of-memory during startup`.
It fails identically at every context from 32768 down to 4096, so it is the
weights, not the KV cache, and no smaller quantisation of that model exists.
Raise the Intel Shared GPU Memory Override (§2.1 territory, needs a reboot) or
accept two local models.

### Step 3 — publish the rows

**Rows are not in the results table until this runs.** The matrix writes one
`results_run.csv` per run directory; the published table is separate.

```cmd
rebuild_results_table.bat
```

or equivalently `py -3 run_master.py --consolidate`. It merges every
`local/runs/*/results_run.csv` into `results_repository.csv`, rewrites
`results_pareto.svg`, and prints the chapter 16 validity gate.

Two things about it that surprise people:

- **The published table is an input, not only an output.** A row whose run
  directory no longer exists is kept as it stands — otherwise a fresh clone,
  which has no run directories, would empty the table on its first
  consolidation. Consequence: **moving or deleting a run directory does not
  remove its row.** To drop a row, remove it from `results_repository.csv`.
- A repeat that aborted has no `results_run.csv` and contributes no row, which
  is correct but invisible — so the count is printed. A campaign that expected
  42 rows and got 40 should notice from that line.

### Step 4 — know what you have

One repeat, one project, the no-methodology anchor. That is a bring-up, not a
measurement: it answers "does this machine produce rows", not "which methodology
is better". Chapter 17 wants **≥3 repeats** before any arm is compared with
another, and the validity gate — sabotage below every real methodology — is a
property of an engine and model pair, not of the repository, so it must be
re-established for each.

Rows from different engines are not poolable. `cfg_engine` is a campaign
constant for that reason.

---

## 8. Failure codes

| Exit | Meaning | Usual cause |
|---|---|---|
| 3 | interpreter missing | `py -3.10` not registered — §1 |
| 4 | config rejected | a key set that this engine cannot apply (`BASE_URL` or `CLAUDE_CONFIG_DIR` on opencode), a model id failing the engine's alias rule, an unparseable number |
| 6 | binary missing/unlaunchable | npm `.cmd` shim on PATH instead of the `.exe` — §4.2; or `codex` not installed — §6 |
| 9 | batch pre-flight | opencode not found anywhere, or `py` not on PATH in that window |

Two symptoms with non-obvious causes, both cost real time:

- **A double-clicked window vanishes instantly.** The batch hit a FATAL guard and
  `exit /b` closed the console. Both batches now `pause` at every exit.
- **`for /f` returns nothing from a quoted path.** `for /f ... in ('py -3 "%~dp0x.py"')`
  silently yields no output; it needs backquotes: `for /f "usebackq" ... in (`py -3 "%~dp0x.py"`)`.
  The symptom is a guard that reports "not found" for something that exists.

---

## 9. What is NOT required

- **A GPU.** Everything runs on CPU, slower. The iGPU switch in §2.1 matters only
  if one is present.
- **Docker.** LiteLLM runs fine as a `uv` tool.
- **API keys**, for local-only campaigns. Only the claude and gpt engines, and
  cloud models behind LiteLLM, need them.
- **An internet connection at run time**, once models are pulled — local
  campaigns are fully offline.
