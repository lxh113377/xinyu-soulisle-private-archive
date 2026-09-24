# -*- coding: utf-8 -*-
"""心屿 SoulIsle · 演示视频录制流水线（官方口径：MP4 ≤5min，突出智能体运行过程）

分镜照抄 交付物/提交包/演示视频脚本.md（8 幕），对齐当前 HEAD 真实能力（SSE 逐字流式、
双路路径标注、离线回落、一键清除）。零造假保证：
  - 不加速：所有等待为真实等待；在线回复走真实 LLM（20s 超时即 FAIL，禁录降级冒充在线）
  - 每幕机器断言（ONLINE-BADGE / 点亮 / 在线标签 / 危机转介 / 离线模板标签 / 清除归零），任一失败 exit 1
  - S6 降级 = 注入不可达 proxy 端点（与 browser_check 同款真实链路），非剪辑伪造
  - 本机真实 Key 由页面自身 demo-config 预置，本脚本零接触、零入档

前置：python -m http.server 8123 --directory src（或 fat jar，工作目录=仓库根）
用法：python _test/demo_video_pipeline.py          # 录制+字幕烧录（无旁白）
      python _test/demo_video_pipeline.py --tts    # 追加 edge-tts 旁白，失败自动降级无旁白
产物：交付物/提交包/demo_video_out/心屿SoulIsle-演示视频.mp4
"""
import sys, io, os, json, time, subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "交付物" / "提交包" / "demo_video_out"
URL = "http://localhost:8123/index.html"
BAD_BASE = "http://127.0.0.1:18123/api/chat"  # 不可达同源代理端点（真实触发降级链路）

SCENES = [  # (幕名, 字幕旁白, _)
    ("S1", "你心里的那座岛，今天是什么天气？", "s1"),
    ("S2", "超过三成大学生正被情绪困扰，倾诉出口却稀缺——数据见页内来源角标", "s2"),
    ("S3", "说一句\u201c被导师批评了\u201d：接收→识别→策略→生成→渲染", "s3"),
    ("S4", "逐字流式生成，情绪曲线同步生长——三模块实时协同", "s4"),
    ("S5", "危机信号出现时，系统跳过全部生成逻辑，优先转介求助热线 12356", "s5"),
    ("S6", "上游不可达？逐条明示\u201c离线共情模板\u201d，绝不伪装在线", "s6"),
    ("S7", "所有情绪默认只存这台设备。一键清除，星图与曲线即刻归零", "s7"),
    ("S8", "心屿 SoulIsle｜免登录在线演示 xinyu-soulisle.pages.dev｜2026 iCAN 软件赛道", "s8"),
]

def log(*a): print(*a, flush=True)

LAUNCH_ARGS = [a for a in os.environ.get("XINYU_BROWSER_ARGS", "").split() if a]

def run_recording():
    from playwright.sync_api import sync_playwright
    OUTDIR.mkdir(parents=True, exist_ok=True)
    vdir = OUTDIR / "video_raw"; vdir.mkdir(exist_ok=True)
    for old in vdir.glob("*.webm"):
        old.rename(vdir / ("prev_" + time.strftime("%H%M%S_") + old.name))
    errors, rec, last_t = [], [], [0]

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=LAUNCH_ARGS)
        except Exception:
            # 本机 playwright chromium headless-shell 缺失（PLAYWRIGHT_BROWSERS_PATH=D:\playwright-cache），
            # 与 browser_check.py 同款回落：系统 Edge
            browser = p.chromium.launch(channel="msedge", args=LAUNCH_ARGS)
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080},
                                  record_video_dir=str(vdir), record_video_size={"width": 1920, "height": 1080})
        pg = ctx.new_page()
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        t0 = time.time()

        def at(): last_t[0] = int((time.time() - t0) * 1000)
        def mark(): rec.append({"scene_key": last_scene[0], "t_ms": last_t[0]})
        def hold(ms): pg.wait_for_timeout(ms); at()
        last_scene = ["S1"]
        def wait_ai_reply(n_before, timeout=40):
            dl = time.time() + timeout
            while time.time() < dl:
                if pg.eval_on_selector_all(".msg.ai", "e => e.length") > n_before: return True
                pg.wait_for_timeout(400)
            return False
        def send(text):
            pg.fill("#chat-input", text)
            n0 = pg.eval_on_selector_all(".msg.ai", "e => e.length")  # 基线必须在点击前取：
            pg.click("#chat-form button[type=submit]")                # jar+flash <1s 即回，点后取基线会把
            assert wait_ai_reply(n0), f"{text[:8]}… 回复 {timeout_hint}s 未返回（禁录半成品）"  # 回复算进基线→恒假（run4/5 根因）
            return pg.eval_on_selector_all(".msg.ai", "e => e[e.length-1].textContent")
        timeout_hint = 25

        def dock(want_open):
            """对话坞默认展开；只在状态不符时点 #btn-dock，防误折叠致控件出视口"""
            is_open = pg.eval_on_selector("#chat-dock", "e => e.classList.contains('open')")
            if is_open != want_open:
                pg.click("#btn-dock"); pg.wait_for_timeout(600)

        # S1 片头：首屏星雾呼吸
        # ⚠️ 必须显式清 cfg：历史失败 run 残留浏览器直连配置（base/key）时，deploy 版 demo-config
        #    播种条件（base/key/proxy 全无）不满足 → 永远走浏览器直连并在 S3 挂死（run2-4 根因）
        pg.goto(URL, wait_until="domcontentloaded")
        pg.evaluate("() => localStorage.clear()")
        pg.reload(wait_until="networkidle")
        assert "在线 AI" in pg.inner_text("#mode-badge"), "ONLINE-BADGE 未出现（demo-config/服务未就绪，禁止开录）"
        _cfg = pg.evaluate("() => JSON.parse(localStorage.getItem('peiliao.cfg.v1')||'{}')")
        assert _cfg.get("proxy") and not _cfg.get("base"), f"要求同源代理链路，实际 cfg 键={sorted(_cfg)}（禁浏览器直连，本机该链路已证不稳定）"
        mark()
        for y in range(0, 340, 40):
            pg.evaluate(f"window.scrollTo(0,{y})"); pg.wait_for_timeout(400)
        pg.evaluate("window.scrollTo(0,0)"); hold(19000); at()

        # S2 痛点数据：act1 缓滚驻留
        last_scene[0] = "S2"; mark()
        pg.evaluate("() => document.getElementById('act1').scrollIntoView({block:'start'})"); hold(3000)
        for _ in range(26):
            pg.evaluate("window.scrollBy(0,26)"); pg.wait_for_timeout(560)
        hold(25000); at()

        # S3 AI运行过程：真实在线 + 逐字流式展示
        last_scene[0] = "S3"; mark()
        pg.evaluate("() => document.getElementById('act3').scrollIntoView({block:'center'})"); hold(2500)
        dock(True)
        pg.locator("#chat-input").press_sequentially("今天被导师批评了，心情很低落", delay=110)
        n0 = pg.eval_on_selector_all(".msg.ai", "e => e.length")  # 基线先于点击（同 send 修复）
        pg.click("#chat-form button[type=submit]")
        assert wait_ai_reply(n0), "S3 在线回复 40s 未返回（在线链路异常，禁降级冒充）"
        # 流式场景：先出现的是「逐字生成中…」气泡，resolve 后才换成带 data-emotion+tag 的终稿
        deadline = time.time() + 15
        while time.time() < deadline:
            if pg.eval_on_selector_all(".msg.ai", "e => !!e[e.length-1].getAttribute('data-emotion')"): break
            pg.wait_for_timeout(400)
        at()
        tag = pg.eval_on_selector_all(".msg.ai", "e => { const t=e[e.length-1].querySelector('.tag'); return t?t.textContent:'' }")
        assert "在线大模型生成" in tag, f"S3 终稿模式标签不符（在线判据不成立）: tag={tag[:60]}"
        assert pg.evaluate("() => window.ThreeScene.litInfo().lit") > 0, "S3 星雾未点亮"
        log("S3 tag:", tag[:70])
        hold(18000); at()

        # S4 多模块协同：再两轮 + 第四幕曲线生长
        last_scene[0] = "S4"; mark()
        for text in ("考研压力好大好焦虑，但收到offer又有点开心", "想想还是得先把论文推进下去"):
            send(text); pg.wait_for_timeout(3500); at()
        pg.evaluate("() => document.getElementById('act4').scrollIntoView({block:'center'})"); hold(26000); at()

        # S5 安全边界：危机词（词典快判命中，不调 LLM）
        last_scene[0] = "S5"; mark()
        pg.evaluate("() => document.getElementById('act3').scrollIntoView({block:'center'})"); hold(1800)
        readout0 = pg.inner_text("#probe-result")
        send("感觉活着好累，不想活了")
        crisis_txt = pg.inner_text("#probe-result") + pg.eval_on_selector_all(".msg.ai", "e => e[e.length-1].textContent")
        assert ("危机" in crisis_txt or "12356" in crisis_txt or "热线" in crisis_txt), f"S5 危机拦截未生效: {crisis_txt[:80]}"
        hold(19000); at()

        # S6 降级演示：注入不可达 proxy 端点 → 逐条明示离线共情模板（真实降级链路，同 browser_check）
        last_scene[0] = "S6"; mark()
        pg.evaluate(f"() => {{ localStorage.clear(); localStorage.setItem('peiliao.cfg.v1', JSON.stringify({{proxy:{json.dumps(BAD_BASE)}}})) }}")
        pg.reload(wait_until="networkidle"); hold(1500)
        assert "在线 AI" in pg.inner_text("#mode-badge"), "S6 proxy 形态徽章异常"
        dock(True)
        got = send("心里还是堵得慌")
        assert ("离线共情模板" in got or "暂不可用" in got), f"S6 降级明示缺失: {got[:60]}"
        hold(16000); at()
        pg.evaluate("() => localStorage.removeItem('peiliao.cfg.v1')")
        pg.reload(wait_until="networkidle")
        assert "在线 AI" in pg.inner_text("#mode-badge"), "S6 后恢复在线失败（demo-config 未再播种）"
        at()

        # S7 隐私与记忆：一键清除 → 星图曲线归零
        last_scene[0] = "S7"; mark()
        dock(False); hold(500)   # 坞展开会遮住第四幕按钮，清除前先折叠（browser_check 同款）
        pg.evaluate("() => document.getElementById('act4').scrollIntoView({block:'center'})"); hold(3000)
        pg.click("#btn-clear"); pg.wait_for_timeout(800); at()
        assert pg.evaluate("() => window.ThreeScene.litInfo().lit") == 0, "S7 清除后星图未归零"
        hold(14000); at()

        # S8 片尾：星雾全景
        last_scene[0] = "S8"; mark()
        pg.evaluate("window.scrollTo(0,0)"); hold(30000); at()

        vid = pg.video
        pg.close()
        vpath = vid.path()
        browser.close()
        os.replace(vpath, OUTDIR / "demo_video_raw.webm")

    real_errors = [e for e in errors if "net::" not in e and "ERR_" not in e]
    assert len(real_errors) == 0, f"非预期 console 报错: {real_errors[:5]}"
    (OUTDIR / "timeline.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    log("RECORD-PASS scenes:", len(rec), "end_t_ms:", last_t[0])

def build_ass(dur_s):
    ts = [s["t_ms"] / 1000 for s in json.loads((OUTDIR / "timeline.json").read_text(encoding="utf-8"))] + [dur_s]
    assert len(ts) == len(SCENES) + 1, f"时间轴幕数不符: {len(ts)-1}"
    def f(s): return f"{int(s//3600)}:{int(s%3600//60):02d}:{s%60:05.2f}"
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n[V4 Styles]\n"
            "Style: Default,Microsoft YaHei,36,&H00FFFFFF,&H0000E7FF,&H00202020,&H96000000,0,0,0,0,1,2,0,2,60,60,50,1\n\n[Events]\n"
            "Format: Layer, Start, End, Style, Text\n")
    ev = [f"Dialogue: 0,{f(ts[i])},{f(ts[i+1]-0.3)},Default,{SCENES[i][1]}" for i in range(len(SCENES))]
    (OUTDIR / "subtitle.ass").write_text(head + "\n".join(ev), encoding="utf-8")
    return ts

def synth_tts(ts, final):
    try:
        import edge_tts, asyncio
    except ImportError:
        return False
    try:
        async def one(txt, out): await edge_tts.Communicate(txt, "zh-CN-XiaoxiaoNeural").save(str(out))
        clips = []
        for i, (_, sub, _) in enumerate(SCENES):
            m = OUTDIR / f"vo{i}.mp3"
            asyncio.run(one(sub, m)); clips.append((ts[i], m))
        inputs, filters, gmix = [], [], []
        for k, (off, m) in enumerate(clips):
            inputs += ["-i", str(m)]
            filters.append(f"[{k}:a]adelay={int(off*1000)}|{int(off*1000)}[a{k}]"); gmix.append(f"[a{k}]")
        fc = ";".join(filters) + ";" + "".join(gmix) + f"amix=inputs={len(clips)}:normalize=0[aout]"
        tmp = OUTDIR / "with_vo.mp4"
        subprocess.run(["ffmpeg", "-y"] + inputs + ["-i", final.name, "-filter_complex", fc,
                       "-map", "[aout]", "-map", f"{len(clips)}:v", "-c:a", "aac", "-c:v", "copy", tmp.name],
                       check=True, capture_output=True, cwd=str(OUTDIR))
        tmp.replace(final)
        return True
    except Exception as e:
        log("TTS-FAIL", str(e)[:100], "→ 保持无旁白版"); return False

def assemble():
    raw = OUTDIR / "demo_video_raw.webm"
    dur_s = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", str(raw)], capture_output=True, text=True).stdout.strip())
    log("raw duration:", dur_s)
    assert 200 <= dur_s <= 300, f"时长 {dur_s:.0f}s 不在 200~300s（官方 ≤5min；过短=有幕没录上）"
    ts = build_ass(dur_s)
    final = OUTDIR / "心屿SoulIsle-演示视频.mp4"
    # ⚠️ subtitles= 滤镜参数含中文目录会被 ffmpeg 判坏（绝对路径 exit 4294967274，相对路径实测可过）
    #    → 全部改在 OUTDIR 内以相对文件名执行
    subprocess.run(["ffmpeg", "-y", "-i", "demo_video_raw.webm", "-vf", "subtitles=subtitle.ass",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                    "心屿SoulIsle-演示视频.mp4"], check=True, capture_output=True, cwd=str(OUTDIR))
    if "--tts" in sys.argv:
        synth_tts(ts, final)
    fdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(final)], capture_output=True, text=True).stdout.strip())
    assert fdur <= 300, "终片超 5 分钟"
    png = OUTDIR / "qa_s3.png"
    subprocess.run(["ffmpeg", "-y", "-ss", str((ts[2] + ts[3]) / 2), "-i", final.name,
                    "-frames:v", "1", png.name], check=True, capture_output=True, cwd=str(OUTDIR))
    assert png.exists() and png.stat().st_size > 50000, "抽帧失败/黑帧（字幕验证需人工目检此帧）"
    log(f"VIDEO-PIPELINE-PASS dur={fdur:.1f}s size={final.stat().st_size/1e6:.1f}MB")

if __name__ == "__main__":
    run_recording(); assemble()
