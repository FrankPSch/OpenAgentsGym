"""Print the directory holding a launchable opencode binary, or NONE.

Why a probe rather than one hardcoded path: npm installs a .cmd shim that
CreateProcess cannot launch and resolve_cli() correctly refuses, so the real
binary under node_modules has to be on PATH instead. But that location is
derived from %APPDATA%, and %APPDATA% is not stable across the ways a .bat gets
started - an elevated console resolves it to a different profile, where the
package is not installed. A batch that tests one literal path therefore reports
"not installed" on a machine where it is installed, which is exactly what
happened on 2026-09-11.

So: collect every plausible location, keep the ones that really contain a
launchable binary, and let the caller put the first on PATH. Printing NONE means
no launchable binary exists anywhere we looked - a real install problem.
"""
import os
import shutil
import subprocess
import sys

candidates = []

appdata = os.environ.get("APPDATA")
if appdata:
    candidates.append(os.path.join(appdata, "npm", "node_modules", "opencode-ai", "bin"))

# The npm global prefix, asked of npm itself rather than assumed. This is what
# survives an elevated shell or a non-default prefix.
try:
    out = subprocess.run(["npm", "prefix", "-g"], capture_output=True, text=True,
                         timeout=30, shell=True)
    prefix = (out.stdout or "").strip()
    if prefix:
        candidates.append(os.path.join(prefix, "node_modules", "opencode-ai", "bin"))
except Exception:
    pass

# Whatever is already on PATH, including a shim: its sibling tree may hold the exe.
shim = shutil.which("opencode")
if shim:
    base = os.path.dirname(shim)
    candidates.append(os.path.join(base, "node_modules", "opencode-ai", "bin"))
    candidates.append(base)

# Per-user install outside npm's global prefix.
home = os.path.expanduser("~")
candidates.append(os.path.join(home, "AppData", "Roaming", "npm",
                               "node_modules", "opencode-ai", "bin"))
candidates.append(os.path.join(home, ".opencode", "bin"))

seen = set()
for d in candidates:
    if not d or d.lower() in seen:
        continue
    seen.add(d.lower())
    exe = os.path.join(d, "opencode.exe")
    if os.path.isfile(exe):
        print(d)
        sys.exit(0)

sys.stderr.write("---- opencode probe failed, here is what it looked at ----\n")
sys.stderr.write("python      : %s\n" % sys.executable)
sys.stderr.write("APPDATA     : %s\n" % os.environ.get("APPDATA"))
sys.stderr.write("USERPROFILE : %s\n" % os.environ.get("USERPROFILE"))
sys.stderr.write("which       : %s\n" % shutil.which("opencode"))
for d in seen:
    sys.stderr.write("  %-5s %s\n"
                     % ("dir" if os.path.isdir(d) else "-", d))
sys.stderr.write("---------------------------------------------------------\n")
print("NONE")
sys.exit(1)
