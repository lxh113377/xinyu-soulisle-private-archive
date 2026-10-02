import re
lines = open("_test/a11y_check.py", encoding="utf-8").read().splitlines()
print("-- results 定义处 --")
for i, l in enumerate(lines):
    if re.match(r"\s*results\s*=", l):
        print("  %d: %s" % (i + 1, l.strip()[:60]))
print("-- with 体内对共享容器的重新绑定（= 而非 append/[..]=）--")
for i in range(252, 403):
    l = lines[i]
    for v in ("inc", "live", "names", "deltas", "viol_total", "passes_min", "states_red"):
        if re.match(r"\s*%s\s*=[^=]" % v, l):
            print("  %d: %s" % (i + 1, l.strip()[:70]))
