"""Does the local gateway serve the three model names the configs address?

A separate file rather than an inline one-liner: the cmd quoting needed to pass
a dict literal and a list comprehension through `py -3 -c` inside a .bat is what
made the first version of this check fail against a gateway that was working
perfectly. Exit 0 = all present, 1 = something missing or unreachable.
"""
import json
import sys
import urllib.request

GATEWAY = "http://127.0.0.1:4000/v1/models"
KEY = "sk-oag-local"
WANTED = ("gpt-oss-20b", "qwen3-4b", "qwen3-coder-30b")

req = urllib.request.Request(GATEWAY, headers={"Authorization": "Bearer " + KEY})
try:
    data = json.load(urllib.request.urlopen(req, timeout=15))
except Exception as exc:
    print("   FAIL gateway unreachable: %s: %s" % (type(exc).__name__, exc))
    sys.exit(1)

served = [m.get("id") for m in data.get("data", [])]
missing = [n for n in WANTED if n not in served]
for name in WANTED:
    print("   %s %s" % ("OK  " if name in served else "FAIL", name))
if missing:
    print("   gateway serves: %s" % ", ".join(served))
sys.exit(1 if missing else 0)
