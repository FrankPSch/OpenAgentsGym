"""Can this leg's model actually answer? Asked before the leg runs, not after.

A local leg addresses `litellm/<name>`, and three separate things must line up
for that to resolve:

  * the gateway is listening on 4000 -- and is not a stale instance still
    serving the config it booted from days ago;
  * <name> is in what the gateway serves;
  * the Ollama tag behind <name> exists.

When any of them is wrong the leg still starts, burns its setup, and writes a
row saying UnknownError or APIError with score 0.0000 -- indistinguishable, in
the published table, from a model that tried and failed. On 2026-09-12 e11 wrote
exactly such a row in 1.6 seconds because the tuned tag had never been built.
A row like that is worse than no row: it is a measurement of nothing wearing
the name of a measurement.

Usage:  py -3 _check_model.py litellm/qwen3-coder-30b-tuned [port] [key]

Exit codes:
  0  resolvable, or not a gateway model at all (cloud legs are not our business)
  4  not resolvable -- caller should skip the leg
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.yaml")

RAW = sys.argv[1] if len(sys.argv) > 1 else ""
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
KEY = sys.argv[3] if len(sys.argv) > 3 else "sk-oag-local"

# Only gateway-routed models are checkable here. A claude or gpt leg runs on
# someone else's hardware and fails with its own diagnostics.
if "/" not in RAW:
    sys.exit(0)
provider, _, NAME = RAW.partition("/")
if provider.lower() != "litellm":
    sys.exit(0)


def fail(*lines):
    print("  PREFLIGHT: this leg cannot resolve its model - skipping it.")
    for line in lines:
        print("             " + line)
    sys.exit(4)


# --- is the gateway there, and what does it serve? --------------------------
req = urllib.request.Request(
    "http://127.0.0.1:%d/v1/models" % PORT, headers={"Authorization": "Bearer " + KEY}
)
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        served = [e["id"] for e in json.loads(resp.read().decode("utf-8", "replace")).get("data", [])]
except (urllib.error.URLError, OSError, ValueError, KeyError):
    fail(
        "no gateway answering on port %d." % PORT,
        "Start it with 02_start_gateway.bat and wait for its model list.",
    )

if NAME not in served:
    fail(
        "the gateway does not serve %r." % NAME,
        "It serves: " + (", ".join(served) if served else "(nothing)"),
        "A gateway started before this model was added keeps port 4000 and",
        "answers with its old list. Restart it: 02_start_gateway.bat",
    )


# --- does Ollama hold the tag behind it? ------------------------------------
def config_mapping():
    try:
        text = open(CONFIG, encoding="utf-8").read()
    except OSError:
        return {}
    mapping, name = {}, None
    for line in text.splitlines():
        hit = re.match(r"\s*-\s*model_name:\s*(\S+)", line)
        if hit:
            name = hit.group(1).strip("\"'")
            continue
        hit = re.match(r"\s*model:\s*ollama_chat/(\S+)", line)
        if hit and name:
            mapping[name] = hit.group(1).strip("\"'")
            name = None
    return mapping


tag = config_mapping().get(NAME)
if tag:
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=20).stdout
        tags = {line.split()[0] for line in out.splitlines()[1:] if line.split()}
    except (OSError, subprocess.SubprocessError):
        tags = set()  # cannot ask; do not block the leg on our own blindness
    if tags and tag not in tags:
        fail(
            "the gateway serves %r but Ollama has no tag %r." % (NAME, tag),
            "Build it:  01_build_models.bat",
        )

sys.exit(0)
