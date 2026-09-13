"""Wait for the gateway to answer, then reconcile what it serves with Ollama.

Two separate facts, and only the second one is worth much:

  1. The gateway answers. A *stale* gateway also answers -- on the same port,
     with the model list it booted from days ago.
  2. Every name it serves resolves to a tag Ollama actually holds. LiteLLM
     serves the NAME from config.yaml whether or not Ollama has the TAG. When
     it does not, the leg dies in about a second with UnknownError, which
     reads like a model failure and is not one. That cost e11 its first
     campaign cell on 2026-09-12.

So this prints the mapping, not a health tick.

Exit codes:
  0  gateway answered, and every served name maps to a tag Ollama holds
  1  gateway did not answer within the timeout
  2  gateway answered but serves no models (bad or empty config)
  3  a served name has no matching Ollama tag -- run build_models.bat
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.yaml")

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
KEY = sys.argv[2] if len(sys.argv) > 2 else "sk-oag-local"
TIMEOUT_S = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0

URL = "http://127.0.0.1:%d/v1/models" % PORT
DEADLINE = time.time() + TIMEOUT_S


def served_names():
    req = urllib.request.Request(URL, headers={"Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=3) as resp:
        payload = json.loads(resp.read().decode("utf-8", "replace"))
    return [entry["id"] for entry in payload.get("data", [])]


def config_mapping():
    """model_name -> ollama tag, read straight from config.yaml.

    Deliberately a regex and not a YAML parse: this must not acquire a
    dependency that a fresh machine might lack, and the file's shape is fixed
    by oam_install.md section 3.5. A name this misses is reported as unknown,
    never as ok.
    """
    try:
        text = open(CONFIG, encoding="utf-8").read()
    except OSError:
        return {}
    mapping = {}
    name = None
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


def ollama_tags():
    """Tags Ollama holds. An empty set means Ollama could not be asked."""
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=20
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    tags = set()
    for line in out.splitlines()[1:]:
        parts = line.split()
        if parts:
            tags.add(parts[0])
    return tags


while True:
    try:
        names = served_names()
        break
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        if time.time() >= DEADLINE:
            print("  gateway: NO ANSWER on port %d after %.0fs" % (PORT, TIMEOUT_S))
            print("  see gateway\\gateway.log - the proxy exits on a config error,")
            print("  and on a cp1252 console it dies printing its own banner.")
            sys.exit(1)
        time.sleep(1.0)

if not names:
    print("  gateway: up on port %d but serving NO models - check gateway\\config.yaml" % PORT)
    sys.exit(2)

mapping = config_mapping()
tags = ollama_tags()

print("  gateway: up on port %d, serving %d model(s):" % (PORT, len(names)))
missing = []
width = max(len(n) for n in names)
for name in names:
    tag = mapping.get(name)
    if tag is None:
        state = "not an ollama model (cloud, or unreadable config)"
    elif not tags:
        state = "-> %s   (ollama could not be asked)" % tag
    elif tag in tags:
        state = "-> %s   ok" % tag
    else:
        state = "-> %s   MISSING" % tag
        missing.append(tag)
    print("             %-*s  %s" % (width, name, state))

if missing:
    print()
    print("  %d served name(s) resolve to a tag Ollama does not hold." % len(missing))
    print("  The leg would fail in about a second with UnknownError and look")
    print("  like a model failure. Build the tag(s) first:")
    print()
    print("      build_models.bat")
    print()
    sys.exit(3)

sys.exit(0)
