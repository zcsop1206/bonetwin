"""MOCK of bonetwin/compute/bt_compute.py (no Brev): echoes the call and the per-run cap from the environment."""
import json
import os
import sys

print(json.dumps({"mock": True, "args": sys.argv[1:], "run": os.environ.get("BT_COMPUTE_RUN"),
                  "cap_usd": os.environ.get("BT_COMPUTE_CAP_USD")}))
