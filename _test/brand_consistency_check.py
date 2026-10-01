# -*- coding: utf-8 -*-
"""作品名一致性守卫（r89）：门面文本 = 品牌决定，改一次要能一直对。

为什么做（一手起因，2026-10-01 r89 实测）：r86 提交 `b363e6c` 声称「作品更名 心屿 MindIsle **全线执行**」，
而本轮 `git grep -l SoulIsle` 现读出 **16 处显示名仍挂旧作品名**，全在门面面上
（README/README.en/CONTRIBUTING/ROADMAP/LICENSE/.env.example/docs 三手册+NOTICES+openapi title/deploy jar 部署包与启动脚本/AGENTS 与 memory 01）。
应用界面（`src/index.html`）当时确实改了 ⇒ "全线"是**存在性**结论（改了几处主要面），不是**行为**结论（所有门面都改了）。
同族第三次（前两次：r52 记忆落库、r70 向量能力位），所以这条上电池而不是靠人记。

判据：
  B1 门面不挂旧名：`FACES` 内剥掉技术标识白名单后，出现 `SoulIsle` 即红
  B2 品牌位在场：`src/index.html` 与 `deploy/xinyu/index.html` 必须含 `MindIsle`
                  （缺 B2 时 B1 可以靠"整页没品牌"骗绿 ⇒ 反向腿）
  B3 白名单必须是**技术标识**（域名/Java 包/类名/artifactId/留档文件名），不得用 `file:line` 形式豁免
退出码：0=BRAND-PASS 1=任一判据失败 2=面不可读（缺文件不等于通过，禁把"量不到"折算成"达标"）
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

# 门面面：现状描述面，人一眼看到的作品名从这里出去
FACES = [
    "README.md", "README.en.md", "CONTRIBUTING.md", "ROADMAP.md", "SECURITY.md", "LICENSE",
    ".env.example", "AGENTS.md",
    "docs/README.md", "docs/API.md", "docs/EXTENSIONS.md", "docs/PERF-BASELINE.md",
    "docs/quality-gates.md", "docs/data-and-privacy.md", "docs/THIRD-PARTY-NOTICES.md",
    "docs/openapi.yaml",
    "src/index.html", "src/manifest.webmanifest",
    "deploy/xinyu/index.html", "deploy/xinyu/manifest.webmanifest",
    "deploy/jar/README-部署.md", "deploy/jar/start.ps1", "deploy/jar/start.sh",
    "memory/01-goal.md",
]
# 历史留痕面**不**进门面：CHANGELOG / memory 分卷 / 交付物留档 里的旧名是当时为真的记录，
# 改写它们等于伪造历史（GM 铁律），也等于把判据的分母做成被检对象可写的量。
TECH_OK = [
    r"xinyu-soulisle\.pages\.dev",      # CF Pages 域名（技术标识，r86 明确不随品牌改）
    r"com\.xinyu\.soulisle",            # Java 包名
    r"SoulIsleApplication",             # 启动类类名
    r"soulisle-server",                 # Maven artifactId / jar 名
    r"心屿SoulIsle-[^\s`)]*",           # 已提交留档的产物文件名（PDF/视频/zip）
    r"已提交留档-SoulIsle[^\s`)/]*",
]
TECH_RE = re.compile("|".join(TECH_OK))
OLD_RE = re.compile(r"SoulIsle")
NEW_TOKEN = "MindIsle"


def old_hits(text):
    """返回剥掉技术标识后的旧名命中上下文列表（纯函数，供 selftest 直接喂合成样本）。"""
    return [m.group(0) for m in OLD_RE.finditer(TECH_RE.sub("", text))]


def selftest():
    bad = []
    demo = "版权 © 2026 心屿 SoulIsle 团队 —— 仅自研代码"
    if not old_hits(demo):
        bad.append("反例①（门面挂旧显示名）不被 B1 抓到 ⇒ 恒真判据")
    tech = ("包 `com.xinyu.soulisle/SoulIsleApplication.java`；产物 `soulisle-server.jar`；"
            "线上 `https://xinyu-soulisle.pages.dev`；留档 `心屿SoulIsle-应用方案.pdf`")
    if old_hits(tech):
        bad.append(f"反例②（纯技术标识）被误判为旧名 {old_hits(tech)} ⇒ 判据会逼人虚报")
    # 白名单不得吞掉真违规：旧名与技术标识同句混排时仍须报红
    mixed = tech + " 与 心屿 SoulIsle 并列"
    if not old_hits(mixed):
        bad.append("反例③（技术标识+旧名混排）不被抓到 ⇒ 白名单过宽")
    print("BRAND-SELFTEST-PASS: 旧名被抓/技术标识不误伤/混排不放过"
          if not bad else "BRAND-SELFTEST-FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    missing, fails = [], []
    checked = 0
    for rel in FACES:
        p = ROOT / rel
        if not p.exists():
            missing.append(rel)
            continue
        text = p.read_text("utf-8", errors="replace")
        checked += 1
        hits = old_hits(text)
        if hits:
            fails.append(f"{rel}: 门面仍挂旧作品名（{len(hits)} 处）")
    for rel in ("src/index.html", "deploy/xinyu/index.html"):
        p = ROOT / rel
        if not p.exists():
            missing.append(rel)
        elif NEW_TOKEN not in p.read_text("utf-8", errors="replace"):
            fails.append(f"{rel}: 品牌位缺 MindIsle（B2 反向腿：门面没品牌时 B1 会假绿）")
    if checked == 0:
        print("BRAND-UNVERIFIED: 一个门面面都读不到 ⇒ 不得据此判绿")
        return 2
    if missing:
        print(f"BRAND-UNVERIFIED: 门面清单里有 {len(missing)} 个面缺失 {missing[:6]}"
              "（缺文件不是通过；请核对 FACES 或补齐该面）")
        return 2
    if fails:
        print(f"BRAND-FAIL: {len(fails)} 项")
        for f in fails:
            print("  🔴", f)
        return 1
    print(f"BRAND-PASS: {checked} 个门面面零旧作品名 + 品牌位在场（技术标识豁免 {len(TECH_OK)} 类）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
