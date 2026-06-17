import re
from pathlib import Path

auth = Path(r"d:\Financial Project\Hunter Radar\hunter-radar\backend\app\core\auth.py").read_text(encoding="utf-8")

# t01 current regex
m = re.search(r"VALID_ROLES\s*[:=]\s*(\([^)]+\)|\[[^\]]+\])", auth)
print("match:", bool(m))
if m:
    print("group(1):", m.group(1))
    print("user in:", "user" in m.group(1))
    print("admin in:", "admin" in m.group(1))
