# Installing OpenAgentsGym on Windows

The shortest path from a fresh Windows PC to a first campaign. Work top to
bottom: **Requirements**, then **Repository**, then whichever of the three
engine chapters you intend to run. Every section ends with a check — run it and
read the output before moving on.

You do not need all three engines. Claude alone is enough to produce rows; the
local chapter is the one that needs the most setup.

---

## 1. Requirements

Install these first, in this order. Each `winget` line is silent and
non-interactive.

| # | Component | Needed for | Install |
|---|---|---|---|
| 1 | Git | cloning the repository | `winget install --id Git.Git --silent` |
| 2 | Python 3.10 | every run builds its venv from it | `winget install --id Python.Python.3.10 --silent` |
| 3 | Python 3.12 or newer | the harness itself and the gateway | `winget install --id Python.Python.3.12 --silent` |
| 4 | Node.js LTS | the opencode and codex CLIs ship as npm packages | `winget install --id OpenJS.NodeJS.LTS --silent` |
| 5 | Ollama | local engine only — holds the models | `winget install --id Ollama.Ollama --silent` |
| 6 | LiteLLM | local engine only — the gateway every local call goes through | `py -3.12 -m pip install --upgrade "litellm[proxy]"` |
| 7 | opencode | local engine only — the CLI that drives the local models | `npm.cmd install -g --allow-scripts=opencode-ai opencode-ai` |

Add `--accept-source-agreements --accept-package-agreements` to each winget line
on a machine that has never used winget. Rows 6 and 7 need row 4 (Node) and row
3 (Python 3.12) already installed, and both need configuration before they work —
chapters 5.4 and 5.5.

**Open a new terminal afterwards.** PATH changes reach new processes only.

### Check

```powershell
git --version
py -0p              # a -V:3.10 line must appear
node --version
npm.cmd --version
ollama --version                 # local engine only
py -3.12 -c "from importlib.metadata import version; print(version('litellm'))"
opencode --version
```

The last two are local-engine only. LiteLLM is checked through
`importlib.metadata` because the package exposes no `__version__` attribute and
`py -3.12 -m litellm` cannot run it either — it has no `__main__`. The proxy's
entry point is `litellm.proxy.proxy_cli:run_server`, which is what
`02_start_gateway.bat` calls.

`py -0p` must list 3.10 explicitly. A Python 3.10 installed through conda or uv
is not registered with the `py` launcher and does not count.

### Disk and memory

| | |
|---|---|
| repository and run directories | a few GB per campaign |
| local models | ~35 GB for all four |
| opencode binary | ~180 MB |

A local 30B model needs roughly 20 GB of free memory while it runs. Claude and
GPT engines need neither.

---

## 2. The repository

Clone it into a plain local folder — **not** into OneDrive, Dropbox or any other
syncing folder:

```powershell
cd $env:USERPROFILE
mkdir GitHub -Force
cd GitHub
git clone https://github.com/FrankPSch/OpenAgentsGym.git
cd OpenAgentsGym
```

Two conditions the harness checks before every run:

- No `CLAUDE.md` and no `AGENTS.md` in any folder **above** the clone.
- `local/` stays out of any sync client. Every run builds its own virtual
  environment there.

### Check

```powershell
py -3 run_master.py --consolidate
```

It prints the table it wrote. On a fresh clone that is the published rows and
nothing else, which is the correct starting point.

---

## 3. Claude engine

The reference engine, and the least work to set up.

### 3.1 Install and sign in

```powershell
irm https://claude.ai/install.ps1 | iex
```

Open a new terminal, then start `claude` once and complete the sign-in.

### 3.2 Choose one authentication mode per campaign

| | subscription login | API key |
|---|---|---|
| `tk_cost_usd` in the table | blank | filled |
| `cfg_bound` | `walltime` | `usd` |
| `MAX_BUDGET_USD` | has no effect | binds |

Pick one and keep it for the whole campaign — the two are not poolable.

### 3.3 Check

```powershell
(Get-Command claude).Source     # must end in claude.exe
claude --version
```

The path must be an `.exe`. A `.cmd` shim on PATH is not launchable by the
harness.

### 3.4 First run

```powershell
.\run.bat p01_python_small m00_empty
```

---

## 4. GPT engine

Structural in the harness and not yet exercised: the registry entry for it is
written from documentation, not from an observed run. Set it up only if you
intend to bring it up and correct the entry afterwards.

### 4.1 Install and sign in

```cmd
npm.cmd install -g @openai/codex
```

Use `npm.cmd`, not `npm`. Check the package name against OpenAI's current
documentation first.

Then either `codex login` for a plan, or set an API key in the environment. The
same rule as for Claude applies: subscription login leaves `tk_cost_usd` blank
and degrades `cfg_bound` to `walltime`; an API key fills both. One mode per
campaign.

### 4.2 Check

```powershell
(Get-Command codex).Source
codex --version
```

### 4.3 Before publishing any row from it

Capture one real run and correct `ENGINES["gpt"]` in `run_master.py` against
what you see:

```cmd
codex exec --json "reply with the single word OK" > codex_probe.txt 2>&1
```

Six questions to answer from that file: one JSON document or a stream of them;
the event `type` values; usage fields top-level or nested; cost and tokens
per-step or cumulative (a multi-step run is needed to tell); which field names
the model served; the exit codes on success and on failure.

Then set that engine's `tested` flag to true. Until it is true the pre-flight
prints a bring-up note on every run.

---

## 5. Local engine

Four parts, in this order: **Ollama** holds the models, the **tuned model** is
built from a versioned file here, the **gateway** presents them all under one
endpoint, and **opencode** drives them.

### 5.1 Ollama

Set two user variables, then restart the server:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_IGPU_ENABLE","1","User")
[Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH","32768","User")
```

```powershell
Get-Process ollama* | Stop-Process -Force
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
Start-Sleep 10
(Invoke-RestMethod "http://127.0.0.1:11434/api/version").version
```

The context length matters: an agent loop re-sends its system prompt and tool
schemas every turn, and the default is far below that.

### 5.2 Models

Pull one at a time:

```powershell
ollama pull qwen3:4b            #  2.5 GB
ollama pull gpt-oss:20b         #   13 GB
ollama pull qwen3-coder:30b     #   18 GB
ollama pull devstral:24b        #   14 GB
```

Watch `ollama pull`'s own output for progress — the blob is preallocated to full
size, so the file size on disk says nothing.

### 5.3 The tuned model

`e11_local_qwen3coder_30b_tuned` runs on a tag defined here. It differs from the
plain 30B only in context and GPU settings, and those settings are what its
published rows mean.

Setting up from scratch, run this instead of 5.2 and this section separately: it
pulls every published tag, builds every versioned Modelfile, and confirms each
tag advertises `tools` — without which a model is unusable here, since opencode
performs every edit through a function call.

```cmd
01_build_models.bat
```

The tuned tag alone, if you need to rebuild just it:

```powershell
ollama create qwen3-coder:30b-tuned -f .\gateway\Modelfile.qwen3-coder-30b-tuned
```

### Check

```powershell
ollama list     # every tag above must appear
```

### 5.4 The gateway

LiteLLM (requirement 6) presents every Ollama tag on `127.0.0.1:4000` under one
OpenAI-compatible endpoint. Its model list, `gateway\config.yaml`, is part of the
repository. Start it from the repository root:

```cmd
02_start_gateway.bat
```

It keeps its own window open; leave it running for the whole campaign.

#### Check

```powershell
(Invoke-RestMethod "http://127.0.0.1:4000/v1/models").data.id
```

Every tag from `ollama list` must appear here, `qwen3-coder-30b-tuned`
included. The gateway names use hyphens where the Ollama tags use a colon.

### 5.5 opencode

opencode (requirement 7) drives the local models. Resolve its real executable —
the npm `.cmd` shim on PATH cannot be launched by the harness:

```powershell
py -3 engine_find_opencode.py
```

#### Provider configuration

opencode reads its providers from a user-level file, **outside** the repository,
so it is not under version control and does not travel with a clone:

```
%USERPROFILE%\.config\opencode\opencode.jsonc
```

It must declare the gateway as an OpenAI-compatible provider and list every
model the campaign uses:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "gym": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "OpenAgentsGym gateway",
      "options": {
        "baseURL": "http://127.0.0.1:4000/v1",
        "apiKey": "sk-local"
      },
      "models": {
        "qwen3-4b":                {},
        "gpt-oss-20b":             {},
        "qwen3-coder-30b":         {},
        "qwen3-coder-30b-tuned":   {},
        "devstral-24b":            {}
      }
    }
  }
}
```

A model missing from this list is invisible to opencode even when the gateway
serves it.

#### Check

```cmd
opencode run --model gym/qwen3-4b "reply with the single word ready"
```

---

## 6. Verification

With the gateway running, check all three engine families at once from the
repository root:

```cmd
check_engine_matrix.bat
```

It reports one line per engine: the binary it found, the model it reached and
whether a tool call succeeded. Set an engine's `tested` flag in `run_master.py`'s
`ENGINES` registry only after its line is clean.

---

## 7. First campaign

```cmd
run_engine_matrix.bat
rebuild_results_table.bat
```

The first runs **one project against one methodology across every local engine**
— `p02_python_medium` and `m00_empty` unless you name others, with the billed
engines opt-in behind `/billed`. The second merges the run directories into
`results_repository.csv`, recomputes the `sc_*` columns over the whole table and
prints the validity gate.

Confirm the new rows carry a `res_verification_passed` value and a non-empty
`sc_overall_mean`.
