# -*- coding: utf-8 -*-
"""服务端硬化常驻棘轮（r128 新增）：成本面 / 内存面 / 记忆面三道新能力不许悄悄退化

为什么做这条判据（**不是**"新功能需要测试"这种泛理由）：
本仓最贵的一类事故形态是「**改了没尺**」——r127 §8 的 S5/S8/S9/S10/S11 全是同一族：
先有了能力主张，几轮之后才发现没有常驻尺，于是"降回去了"没人拦。本轮三项改造
（限流闸 / 访问日志 / BM25 长期记忆）如果只有 JUnit 保护，JUNIT 会被后人整体删掉或
改宽松，而仓库层面看不出任何异常。

所以这里做的是**仓库面的结构断言**，与 JUnit 正交：
  JUnit 答"行为对不对"，本脚本答"**这套能力还在不在**"。

四条断言（每条都必须有反例腿，见 --selftest）：
  H1 限流闸在位：ApiGuardFilter 类存在 + 429/rate-limited 语义在源码里 + 有 Retry-After
  H2 体上限在位：max-body-bytes 配置项在 application.yml 且默认值 > 0
  H3 访问日志在位：AccessLogFilter 在位，且**不记请求体/密钥**（密钥零落盘红线）
  H4 长期记忆检索在位：MemorySearchService + /api/memory/search 三处同时在
     （控制器路由、openapi 声明、docs/API.md 人读手册）—— 少一处就是文档漂移

⚠️ 自检纪律（照本仓 r127 §8 的教训）：
  - 判据不许读**没量到的东西**当零：每个断言先证「输入面非空」，输入为空 ⇒ rc=2 环境未验
  - 不许有恒真腿：--selftest 注入变异必须把每条断言**单独**打翻，否则这条腿是装饰

退出码：0=SERVER-HARDENING-PASS 1=任一断言红 2=环境未验（源码面缺失，不得声称已验）
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
JAVA_SRC = ROOT / "server" / "src" / "main" / "java" / "com" / "xinyu" / "soulisle"
YML = ROOT / "server" / "src" / "main" / "resources" / "application.yml"
SPEC = ROOT / "docs" / "openapi.yaml"
MANUAL = ROOT / "docs" / "API.md"

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))


def java_file(rel):
    """按相对路径读 Java 源；不存在返回 None（由调用方区分「缺失」与「无该词」）。"""
    p = JAVA_SRC / rel
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def strip_comments(src):
    """去掉 // 行注释与 /* */ 块注释。

    为什么必须去：H3 要扫全文找密钥字面量，而本仓的 javadoc 里**正当地写着**
    「绝不记请求体、响应体、Authorization 头与任何密钥」—— 散文里出现被禁词，
    恰恰说明这条红线被写清楚了。拿注释当代码判红，就是把说明文档判成缺陷
    （第二版 H3 就是这么假红的）。
    """
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"//[^\n]*", " ", src)


def h1_rate_limit_present():
    src = java_file(Path("config") / "ApiGuardFilter.java")
    if src is None:
        return False, "ApiGuardFilter.java 不在磁盘上"
    need = {
        "429": "429",
        "rate-limited 错误体": "rate-limited",
        "Retry-After 响应头": "Retry-After",
        "令牌桶类": "class Bucket",
    }
    miss = [k for k, v in need.items() if v not in src]
    return (not miss), ("" if not miss else f"缺：{miss}")


def h2_body_cap_present():
    if not YML.exists():
        return False, "application.yml 不在磁盘上"
    text = YML.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"max-body-bytes:\s*\$\{[^:]+:(\d+)\}", text)
    if not m:
        return False, "application.yml 里找不到带默认值的 max-body-bytes"
    default = int(m.group(1))
    if default <= 0:
        return False, f"max-body-bytes 默认值 = {default}，配 0 等于关掉这道闸"
    return True, f"max-body-bytes 默认 {default} B"


def h3_access_log_present():
    src = java_file(Path("config") / "AccessLogFilter.java")
    if src is None:
        return False, "AccessLogFilter.java 不在磁盘上"
    if "access" not in src:
        return False, "没有 access 日志输出"
    # 红线：整个文件里不得出现「把载荷或密钥读出来」的写法。
    # ⚠️ 第一版只扫含 LOGGER. 的行 —— 但载荷是先拼进 line 变量、再交给 logger 的，
    # 拼接那行并不含 LOGGER.，于是注入了 getContentAsString 照样判绿（装饰腿）。
    # 正解：在一个专职日志过滤器里，任何 getContentAsString/Authorization/密钥字段
    # 的出现本身就是可疑的，不必要求它与 LOGGER. 同行。
    bad = []
    code_only = strip_comments(src).lower()
    for token in ("getcontentasstring", "authorization", "apikey",
                  "this.key", "llm.key", "xinyu-token"):
        if token in code_only:
            bad.append(token)
    return (not bad), ("" if not bad else f"疑似把载荷/密钥送进日志：{bad}")


def h4_memory_search_present():
    svc = java_file(Path("service") / "MemorySearchService.java")
    ctl = java_file(Path("api") / "MemoryController.java")
    if svc is None:
        return False, "MemorySearchService.java 不在磁盘上"
    if ctl is None or "/api/memory/search" not in ctl:
        return False, "MemoryController 里没有 /api/memory/search 路由"
    if not SPEC.exists():
        return False, "docs/openapi.yaml 不在磁盘上"
    if "/api/memory/search" not in SPEC.read_text(encoding="utf-8", errors="replace"):
        return False, "openapi.yaml 没有声明 /api/memory/search"
    if not MANUAL.exists():
        return False, "docs/API.md 不在磁盘上"
    if "/api/memory/search" not in MANUAL.read_text(encoding="utf-8", errors="replace"):
        return False, "docs/API.md 人读手册没有这条接口"
    return True, "控制器 + openapi + 人读手册 三处齐备"


CHECKS = [
    ("H1 限流闸在位（429 + Retry-After + 令牌桶）", h1_rate_limit_present),
    ("H2 请求体上限在位且默认值非零", h2_body_cap_present),
    ("H3 结构化访问日志在位且不记载荷/密钥", h3_access_log_present),
    ("H4 BM25 长期记忆检索三处齐备", h4_memory_search_present),
]


def run_checks():
    for name, fn in CHECKS:
        ok, detail = fn()
        check(name, ok, detail)
    return results


def selftest():
    """变异腿：每条断言单独打翻一次，证明它有牙。

    ⚠️ 第一版三条腿全是**空操作**（变异串写错 ⇒ replace/re.sub 什么也没替 ⇒ 断言照绿），
    判据却报「恒真」。教训与本仓 r127 §8 同族：**变异腿必须先断言"变异真的落盘了"**，
    否则测的是「变异前的原样」。这里统一走 `mutate()`，它在替换未命中时直接炸。
    """
    bad = []
    guard = java_file(Path("config") / "ApiGuardFilter.java")
    yml_backup = YML.read_text(encoding="utf-8") if YML.exists() else None
    log_backup = java_file(Path("config") / "AccessLogFilter.java")
    manual_backup = MANUAL.read_text(encoding="utf-8") if MANUAL.exists() else None

    def mutate(path, old, new):
        """替换并**当场验证**命中；未命中就抛 —— 空操作变异腿不许静默通过。"""
        text = path.read_text(encoding="utf-8")
        if old not in text:
            raise AssertionError(f"变异腿空操作：{path.name} 里找不到 {old!r}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    try:
        # H1：抹掉「被限流时返回的那个错误体」语义，必须翻红。
        # ⚠️ 不能拿 429 当变异锚点：它在 javadoc 里也出现，count=1 只替掉注释那处，
        # 真正的业务那处原封不动 ⇒ 断言照绿（第一版就是这么白跑的）。
        # 锚点必须选**只出现一次**的判别串。
        mutate(JAVA_SRC / "config" / "ApiGuardFilter.java", "rate-limited", "teapot")
        if h1_rate_limit_present()[0]:
            bad.append("H1 变异腿：抹掉限流错误体后仍判绿 ⇒ H1 恒真")

        # H2：把默认值改成 0（等于关掉这道闸），必须翻红。
        # ⚠️ yml 里是 `max-body-bytes: ${...}`，冒号后有空格，正则里必须留 \s*。
        yml_text = YML.read_text(encoding="utf-8")
        pat = re.compile(r"(max-body-bytes:\s*\$\{[^:}]+:)\s*\d+")
        if not pat.search(yml_text):
            raise AssertionError("变异腿空操作：yml 里匹配不到 max-body-bytes 默认值")
        YML.write_text(pat.sub(r"\g<1>0", yml_text, count=1), encoding="utf-8")
        if h2_body_cap_present()[0]:
            bad.append("H2 变异腿：默认值改 0 后仍判绿 ⇒ H2 恒真")

        # H3：往日志行里塞请求体，必须翻红
        mutate(JAVA_SRC / "config" / "AccessLogFilter.java",
               '",\\"ms\\":" + millis',
               '",\\"body\\":\\"" + request.getContentAsString() + "\\",\\"ms\\":" + millis')
        if h3_access_log_present()[0]:
            bad.append("H3 变异腿：日志塞入请求体后仍判绿 ⇒ H3 恒真")

        # H4：从人读手册里删掉这条接口，必须翻红
        mutate(MANUAL, "/api/memory/search", "/api/removed")
        if h4_memory_search_present()[0]:
            bad.append("H4 变异腿：手册删掉接口后仍判绿 ⇒ H4 恒真")
    except AssertionError as e:
        bad.append(str(e))
    finally:
        # 还原必须放在 finally：任一腿崩了也不能把源码/文档留在变异态。
        # ⚠️ 第一版漏还原 MANUAL，直接把 docs/API.md 的接口名写成 /api/removed。
        if yml_backup is not None:
            YML.write_text(yml_backup, encoding="utf-8")
        if log_backup is not None:
            (JAVA_SRC / "config" / "AccessLogFilter.java").write_text(log_backup, encoding="utf-8")
        if guard is not None:
            (JAVA_SRC / "config" / "ApiGuardFilter.java").write_text(guard, encoding="utf-8")
        if manual_backup is not None:
            MANUAL.write_text(manual_backup, encoding="utf-8")

    # 还原后再跑一遍原样：必须全绿，否则上面的"绿"是变异残留
    still_ok = [n for n, fn in CHECKS if not fn()[0]]
    if still_ok:
        bad.append(f"还原后仍判红（变异没被完全撤销）：{still_ok}")

    print("SELFTEST-PASS: H1/H2/H3/H4 四条变异腿均把对应断言打翻、还原后原样零红"
          if not bad else "SELFTEST-FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())

    if not JAVA_SRC.is_dir():
        print("SERVER-HARDENING-ENV-UNVERIFIED: 服务端源码面不在预期位置，不得声称已验")
        return 2

    run_checks()
    red = [n for n, ok, _ in results if not ok]
    total = len(results)
    if red:
        print(f"合计 {total} 项，红 {len(red)}")
        for n in red:
            print(f"  🔴 {n}")
        print("SERVER-HARDENING-FAIL")
        return 1
    print(f"合计 {total} 项，红 0")
    print("SERVER-HARDENING-PASS 限流闸/体上限/访问日志/BM25 检索 四道能力均仍在位")
    return 0


if __name__ == "__main__":
    sys.exit(main())