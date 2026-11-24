# Copyright (c) 2026 unlimitedera. All Rights Reserved.
import sys, time
from cliptastic import jobs
j = jobs.create(sys.argv[1], {"count": int(sys.argv[2]) if len(sys.argv) > 2 else 3})
while True:
    j = jobs.load(j["id"])
    print(j["state"], j["stage"], j["progress"], j["log"][-1] if j["log"] else "", flush=True)
    if j["state"] in ("done", "error"): break
    time.sleep(5)
print(j["error"]); print(j["id"])
for c in j["clips"]: print(c["id"], c["score"], c["start"], c["end"], c["status"], c.get("layout_used"), c["title"][:50])
