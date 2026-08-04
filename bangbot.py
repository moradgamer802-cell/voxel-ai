#!/usr/bin/env python3
"""Compatibility shim — VOXEL AI now lives in voxel.py.

Kept so existing `alias voxel='python3 ~/voxel-ai/bangbot.py'` lines and old
installs keep working. Re-run install.sh to update the alias.
"""
import os
import runpy
import sys

here = os.path.dirname(os.path.abspath(__file__))
target = os.path.join(here, "voxel.py")

if not os.path.isfile(target):
    sys.stderr.write(
        "voxel.py not found next to bangbot.py.\n"
        "Reinstall:  curl -fsSL https://raw.githubusercontent.com/"
        "moradgamer802-cell/voxel-ai/main/install.sh | bash\n")
    sys.exit(1)

sys.argv[0] = target
runpy.run_path(target, run_name="__main__")
