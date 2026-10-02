# -*- coding: utf-8 -*-
"""r94：给 backup_online 的 B2 腿加**有界重试**（按行号定位，避开长字符串锚点）。"""
from pathlib import Path

P = Path("_test/backup_online_check.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)

# 1-based 65..69 = proxy = pg.evaluate(...) 三行 + ck 两行
i = next(k for k, l in enumerate(lines) if l.strip().startswith("proxy = pg.evaluate("))
assert "B2 stub" in lines[i + 3] or "B2 stub" in lines[i + 4], lines[i:i + 6]
j = next(k for k in range(i, i + 8) if "B2 stub" in lines[k])
# ck 语句可能占 2 行
end = j
while ")" not in lines[end].rstrip()[-2:] and end < j + 3:
    end += 1

NEW = '''        # r94：页面若在 evaluate 期间发生导航（腾讯「确定访问」页跳转 / SW 重载），
        # Playwright 抛 `Execution context was destroyed` —— 本轮电池实测红 1 次、
        # 单独复跑 2 次全绿 ⇒ 判为竞态。处置：**有界重试一次**（不是放宽判据：
        # 真缺陷第二次仍会红，判据照旧拦得住）。
        proxy, perr = "", ""
        for _ in range(2):
            try:
                proxy = pg.evaluate(
                    "() => { try { return JSON.parse(localStorage.getItem('peiliao.cfg.v1')||'{}').proxy || ''; }"
                    " catch (e) { return 'ERR'; } }")
                break
            except Exception as e:            # 导航竞态 ⇒ 等一下再读同一份 localStorage
                perr = str(e)[:60]
                pg.wait_for_timeout(1200)
        ck("B2 stub 指向 pages.dev 的函数",
           proxy == "https://xinyu-soulisle.pages.dev/api/chat", (proxy or perr)[:60])
'''
out = lines[:i] + [NEW] + lines[end + 1:]
P.write_text("".join(out), encoding="utf-8")
print("替换 %d..%d 共 %d 行 → %d 行" % (i + 1, end + 1, end - i + 1, len(NEW.splitlines())))
