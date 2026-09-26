# -*- coding: utf-8 -*-
"""远端树洁净度审计（r37）：评委看得见的是 **远端 main 的文件树**，不是本机工作树。
补的是哪一类洞：
  1) `.gitignore` 只挡"以后再 add"，**不会把已推上去的东西从远端拿掉** ⇒ 本机 ignore 到位 ≠ 远端没有；
  2) 仓库名带 "private" 而 visibility 实为 PUBLIC（本仓实测如此），
     这类名字会诱导后续会话把本机工件当"反正没人看见"往里塞；
  3) 既有的 `tracked_secret_scan.py` 扫的是**本机 `git ls-files`**（内容与密钥形态），
     本判据扫的是**远端路径集合**（工件该不该出现在公网仓库），两者不重叠。
禁用路径（deny-list）与理由逐条写死；误报侧同样固定：`.env.example` 与零密钥代理版
`deploy/xinyu/js/demo-config.js` **必须放行**（前者是模板，后者是公网要用的正确形态）。
退出码：0=CLEAN 1=发现禁用路径 2=取不到远端树/无鉴权（未验，不得当通过）
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (正则, 人读的"为什么禁")——正则匹配的是仓库内相对路径
DENY = [
    (r"^src/js/demo-config\.js$", "本机演示配置（含真实 Key），只准存在于工作树"),
    (r"^_test/cors_probe\.py$", "一次性探针，历史上有密钥字面量"),
    (r"^server/data/.*\.(mv\.db|trace\.db|lob)$", "H2 本地库（含真实对话数据）"),
    (r"(^|/)\.env(\.prod(uction)?)?$", "受保护 env 文件（R196 红线）"),
    (r"\.jar$", "构建产物，走 Release 资产而不是入库"),
    (r"(^|/)_shots/", "脚本生成的截图产物"),
    (r"(^|/)(\.codebuddy|\.wrangler/cache)/", "工具会话/缓存目录"),
]
ALLOW = [
    r"^\.env\.example$",                      # 模板：明确要入库
    r"^deploy/xinyu/js/demo-config\.js$",      # 零密钥代理版：公网就靠它
]
ALLOW_RULES = [(re.compile(p), "模板/公网正确形态") for p in ALLOW]


def deny_hit(path):
    """纯函数：单个路径是否命中禁用清单（先过放行清单，再过禁用清单）。"""
    for rx, _ in ALLOW_RULES:
        if rx.match(path):
            return None
    for rx, why in DENY:
        if re.search(rx, path):
            return why
    return None


def audit(paths):
    hits = []
    for p in sorted(paths):
        why = deny_hit(p)
        if why:
            hits.append((p, why))
    return hits


def _token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if t:
        return t
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def remote_tree():
    """返回 (paths, branch, err)。err 非空即取数失败 ⇒ 上层判 rc=2，禁止当通过。"""
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT,
                             capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as e:
        return None, "", "git remote 取失败 %s" % e
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
    if not m:
        return None, "", "origin 不是 GitHub 仓库：%s" % url
    slug = "%s/%s" % (m.group(1), m.group(2))
    br = subprocess.run(["git", "ls-remote", "--symref", "origin", "HEAD"], cwd=ROOT,
                        capture_output=True, text=True, timeout=60).stdout
    mb = re.search(r"refs/heads/(\S+)", br)
    branch = mb.group(1) if mb else "main"
    req = urllib.request.Request(
        "https://api.github.com/repos/%s/git/trees/%s?recursive=1" % (slug, branch),
        headers={"User-Agent": "xinyu-remote-tree-audit", "Accept": "application/vnd.github+json"})
    tok = _token()
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return None, branch, "http=%s（%s/%s）" % (e.code, slug, branch)
    except Exception as e:
        return None, branch, "%s（%s/%s）" % (type(e).__name__, slug, branch)
    if "tree" not in data:
        return None, branch, "响应无 tree 字段"
    if data.get("truncated"):
        # 分母被截断时"零命中"没有意义（M5⑦）：宁可报未验
        return None, branch, "tree 被 API 截断（truncated=true）⇒ 分母不完整"
    return [t["path"] for t in data["tree"] if t.get("type") == "blob"], branch, ""


def selftest():
    """双向自证：禁用侧必须命中，误报侧必须放行，空分母/截断必须算未验。"""
    bad = []
    clean = ["src/index.html", "src/js/app.js", ".env.example", "deploy/xinyu/js/demo-config.js",
             "docs/openapi.yaml", "_test/run_all_suites.py"]
    if audit(clean):
        bad.append("①正常仓库被判脏 ⇒ 误报（会把每次提交都拦下来）")
    dirty = ["src/js/demo-config.js", "_test/cors_probe.py", "server/data/xinyu.mv.db",
             ".env", ".env.production", "build/app.jar", "_test/_shots/lit_single.png",
             ".codebuddy/session.json"]
    got = {p for p, _ in audit(dirty)}
    miss = [p for p in dirty if p not in got]
    if miss:
        bad.append("②禁用样本漏判：%s" % miss)
    if audit([]):
        bad.append("③空分母竟判出命中 ⇒ 逻辑异常")
    # 放行清单必须真的被放行（不是"整表恒放行"的假自证）
    if deny_hit("src/js/demo-config.js") is None:
        bad.append("④含密钥版本被放行 ⇒ 放行清单过宽（真实缺陷被当成模板）")
    if deny_hit("deploy/xinyu/js/demo-config.js") is not None:
        bad.append("⑤零密钥代理版被拦 ⇒ 会把公网正确形态判死")
    print("SELFTEST-%s" % ("PASS: 禁用 8 类全命中、放行 2 类不误伤、空分母不判脏"
                           if not bad else "FAIL: " + "; ".join(bad)))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    paths, branch, err = remote_tree()
    if err or not paths:
        print("REMOTE-TREE-AUDIT-ENV: 取不到远端树（%s）⇒ 记为未验证，不判绿" % (err or "空树"))
        return 2
    hits = audit(paths)
    if hits:
        for p, why in hits:
            print("  禁用路径 %s  ->  %s" % (p, why))
        print("REMOTE-TREE-AUDIT-FAIL: %d 条本机工件出现在远端 %s（%d 个 blob）"
              % (len(hits), branch, len(paths)))
        return 1
    print("REMOTE-TREE-AUDIT-PASS（远端 %s：%d 个 blob，deny-list %d 条零命中；"
          "放行侧 .env.example 与零密钥 demo-config 不误伤）" % (branch, len(paths), len(DENY)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
