"""Keep the machine awake for the length of a campaign, and put the setting back.

WHY THIS EXISTS. On 2026-09-13 an unattended sweep killed the machine outright:
bugcheck 0x19C, WIN32K_POWER_WATCHDOG_TIMEOUT. The power plan had
standby-after-60-minutes on mains; an hour into a leg Windows began the
transition into standby with 18 GB of model weights resident and layers pinned
on the integrated GPU, and the transition could not complete inside the
watchdog. The leg left a START with no DONE in _master.log and no row at all --
the third failure mode in two days that produces no evidence rather than bad
evidence.

The power plan is a machine setting: it does not travel with the clone, and a
Windows update or a plan change silently restores it. A campaign that runs for
hours unattended should therefore not depend on someone having remembered.

WHAT IT DOES NOT DO. It does not touch the monitor timeout (the screen may
sleep; only system standby breaks a run), the DC (battery) setting, or
hibernate. It changes exactly one value and restores exactly what it found.

Usage:
    py -3 engine_nosleep.py save       -> prints the current AC standby value in
                                          seconds, or "unknown"
    py -3 engine_nosleep.py off        -> sets AC standby to never
    py -3 engine_nosleep.py restore N  -> sets AC standby back to N seconds

Never fails a campaign: every path exits 0, because a run that cannot read a
power setting should still run.
"""

import re
import subprocess
import sys

# Subgroup "Sleep" and setting "Sleep after". GUIDs rather than display names,
# which are localised -- on this machine powercfg prints "Energie sparen" and
# "Deaktivierung nach", and matching those would break on any other language.
SUB_SLEEP = "238c9fa8-0aad-41ed-83f4-97be242c8f20"
STANDBYIDLE = "29f6c1db-86da-48c5-9fdb-f2b67b1f44da"


def run(args):
    try:
        return subprocess.run(
            ["powercfg"] + args, capture_output=True, text=True, timeout=20
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def current_ac_seconds():
    """The AC 'sleep after' value, in seconds, or None.

    powercfg prints two hex values at the end of the block, AC then DC. The
    labels around them are localised; the order and the hex are not.
    """
    out = run(["/query", "SCHEME_CURRENT", SUB_SLEEP, STANDBYIDLE])
    hexes = re.findall(r":\s*(0x[0-9a-fA-F]{8})", out)
    if len(hexes) < 2:
        return None
    # ...possible settings first (min/max/step/units), then current AC, then DC.
    return int(hexes[-2], 16)


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "save":
        cur = current_ac_seconds()
        print("unknown" if cur is None else str(cur))
        return 0
    if what == "off":
        cur = current_ac_seconds()
        if cur == 0:
            print("  sleep: already never on mains")
            return 0
        run(["/change", "standby-timeout-ac", "0"])
        now = current_ac_seconds()
        if now == 0:
            print("  sleep: disabled on mains for this campaign (was %s min)"
                  % ("?" if cur is None else cur // 60))
        else:
            print("  sleep: COULD NOT be disabled - the machine may standby mid-run")
            print("         and a standby with a model resident has bugchecked before")
        return 0
    if what == "restore":
        val = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        if val == "unknown" or not val.isdigit():
            print("  sleep: previous value unknown, left disabled")
            return 0
        run(["/change", "standby-timeout-ac", str(int(val) // 60)])
        print("  sleep: restored to %s min on mains" % (int(val) // 60))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
