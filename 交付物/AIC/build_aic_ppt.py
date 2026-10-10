# -*- coding: utf-8 -*-
"""
心屿 MindIsle · AIC 参赛 PPT 构建脚本（基于用户原版迭代，不覆盖原稿）

原则（用户 2026-10-09 立规）：
  1. 绝不修改/删除用户的原文件 —— 只操作 `_原版备份-勿删` 之外的派生副本；
  2. 用户原有 20 页全部保留，仅在派生副本上做最小必要文本修正（赛道/日期/团队口径）；
  3. 新增内容追加在末尾，视觉样式沿用用户原版第 14 页（PowerPoint 原生 Duplicate 复制，
     背景图与卡片样式 100% 继承）。

用法：python build_aic_ppt.py
"""
import copy
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

HERE = Path(__file__).parent
ORIGINAL = (
    Path(r"c:\Users\37533\Desktop\workspace\项目\陪聊\交付物\提交包\心屿MindIsle_参赛方案.pptx")
)
DST = HERE / "心屿MindIsle_AIC参赛方案.pptx"
BACKUP_DIR = HERE / "_原版备份-勿删"

AIC_FULL = "2026 第八届全球校园人工智能算法精英大赛 · 算法创新赛 · 赛题2「AI+软件创新」"

# ---------- 原稿最小必要修正（不删任何页，只改文本） ----------
TEXT_FIXES = [
    ("iCAN 大学生创新创业大赛 AI 应用创新挑战赛", AIC_FULL),
    ("AI 应用创新挑战赛 · 互联网 · 情感陪伴", "算法创新赛 · AI+软件创新 · 情感陪伴"),
    ("汇报日期：2026 年 9 月", "汇报日期：2026 年 10 月"),
    # 注：不得出现"指导教师"字样（AIC 公平性红线），故此处不写指导老师名额
    ("团队配置（8 人 + 顾问）", "团队配置（参赛队 ≤3 人，按官网报名信息）"),
]

# ---------- 新增 4 页内容 ----------
NEW_SLIDES = [
    {
        "kicker": "DELIVERY",
        "title": "本次参赛交付范围：已落地 / 路线图（如实标注）",
        "subtitle": "对照赛题2「AI+软件创新」逐项标明实现状态——能演的标已落地，没做完的标路线图，杜绝虚报",
        "cols": [1.35, 2.55, 1.35, 3.65],
        "header": ["类别", "模块", "状态", "依据 / 说明"],
        "rows": [
            ["感知", "三级共识情绪路由（危机短路 → 词典×本地模型共识 → LLM 可选仲裁）", "✅ 已落地", "/api/emotion 实测，判定路径逐条可见"],
            ["感知", "自研微调中文情绪模型（chinese-roberta-wwm-ext）", "✅ 已落地", "冻结盲测 237 条：92.2% · 26.6 ms"],
            ["生成", "情绪条件化共情对话（SSE 逐字流式）", "✅ 已落地", "在线端到端约 1.0–1.4 s；失败回落离线模板并明示"],
            ["呈现", "3D 情绪星雾 + 五幕滚动叙事", "✅ 已落地", "无 WebGL 环境自动降级为渐变"],
            ["记忆", "情绪曲线（本机留存，可清除可导出）", "✅ 已落地", "演示环境可实时查看与清除"],
            ["安全", "危机词表短路 + 专业热线转介", "✅ 已落地", "危机召回 6/6，14 ms 响应"],
            ["感知", "门控多模态（语音韵律 / 面部 AU）", "🟡 路线图", "当前仅文本与语音转写输入"],
            ["记忆", "情感记忆图谱 EMG（四层 + 时间衰减检索）", "🟡 路线图", "当前为会话上下文 + 情绪曲线"],
            ["决策", "PACE 主动陪伴引擎（状态预测 + 约束优化）", "🟡 路线图", "未上线，属后续迭代"],
        ],
    },
    {
        "kicker": "EMOTION ROUTING",
        "title": "三级共识路由：让「模型准不准」成为可切换、可实测的工程问题",
        "subtitle": "危机永不概率化；词典与本地模型一致即双证据；分歧由词典裁决；LLM 仲裁保留为可现场切换的对照实验",
        "cols": [1.35, 2.75, 2.05, 2.75],
        "header": ["层级", "行为", "触发 / 条件", "实测表现"],
        "rows": [
            ["⓪ 危机短路", "跳过全部生成与判定逻辑，直接返回专业热线", "命中危机词表", "14 ms，危机召回 6/6"],
            ["① 词典快判", "106 触发词 + 否定/程度修正，结果可解释", "每条输入", "≈0 ms，完全离线"],
            ["② 本地微调模型", "RoBERTa 推理，置信度进入证据链", "模型腿可用时", "26.6 ms，完全离线"],
            ["③ 共识采信", "两路标签一致 → 双证据采信（读数取词典）", "标签一致 · 73 条中 57 条", "98.6%，离线/在线双口径恒等"],
            ["④ 分歧裁决", "标签不一致 → 词典裁决，分歧信号保留展示", "标签不一致 · 73 条中 10 条", "结构性不倒退（对照：升 LLM 会跌至 94.5%）"],
            ["⑤ LLM 仲裁", "route=lexicon 可切换的旧双路语义", "开关切换，现场对照演示", "647 ms / 按次付费"],
        ],
    },
    {
        "kicker": "EVIDENCE",
        "title": "可验证的证据：以下每项都欢迎评委现场复跑",
        "subtitle": "均为团队在自建评测集与自有环境下的实测；评委可当场重算，而非听我们口头承诺",
        "cols": [1.85, 1.45, 2.85, 2.75],
        "header": ["指标", "数值", "口径", "复跑方式"],
        "rows": [
            ["情绪判定准确率", "98.6%（72/73）", "自建 73 条评测集，离线/在线双口径恒等", "GET /api/emotion/eval"],
            ["危机召回", "6/6", "危机词表规则短路层", "输入危机语句即刻演示"],
            ["盲测准确率（口语生成域）", "92.2%", "237 条冻结盲测集，与训练集零交集", "_test/emotion_blindset_eval.py"],
            ["单条推理延迟", "26.6 ms", "本地微调模型腿（消费级显卡）", "界面耗时显示"],
            ["单元测试", "101 用例全绿", "JUnit 5 + Mockito（桩断言不触网）", "mvn test"],
            ["覆盖率门禁", "行 97.00% / 分支 95.21%", "守卫脚本独立复算", "java_test_guard"],
            ["训练成本", "6 epoch ≈ 5 分钟", "RTX 5070 Ti，混合语料 3622 条", "ml/train_emotion.py"],
        ],
    },
    {
        "kicker": "SCORING MAP",
        "title": "对照 AIC 赛题2 评分规则的逐项举证",
        "subtitle": "创新性 20 ／ 技术实现 20 ／ 功能完整性 20 ／ 方案完整性 20 ／ 应用价值 15 ／ 总结与展望 5",
        "cols": [1.35, 0.85, 4.0, 2.7],
        "header": ["评分项", "分值", "本作品对应证据", "自评档位"],
        "rows": [
            ["创新性", "20", "三级共识路由 + route 开关做策略对照实验 + 危机永不概率化", "7–13 档偏上"],
            ["技术实现", "20", "自研微调模型（训练/评测/推理全链路自建）+ 覆盖率门禁 + 双端契约对账", "14–20 档"],
            ["功能完整性", "20", "识别→生成→呈现→记忆→安全五段闭环；三路部署在线可体验；降级链路完备", "14–20 档"],
            ["方案完整性", "20", "按官方六部分大纲成册，附架构图、核心代码、测试数据与参考文献", "14–20 档"],
            ["应用价值", "15", "校园情绪场景明确；尚未开展真实试点（如实声明，非量化承诺）", "5–9 档偏上，试点佐证补齐后可上抬"],
            ["总结与展望", "5", "不足与改进路线如实列出：域偏移、危机词表盲区、未试点三项", "3–5 档"],
        ],
    },
    {
        # 官方六部分大纲（四）开发测试与部署 —— 老大 PPT 原本缺这一块
        "kicker": "DEV & DEPLOY",
        "title": "开发测试与部署：本届实际走了哪几步",
        "subtitle": "按官方大纲补：开发流程 → 代码实现 → 测试优化 → 部署方案，四段俱全",
        "cols": [1.35, 1.25, 2.85, 3.45],
        "header": ["环节", "时间", "主要产出", "说明 / 可核查点"],
        "rows": [
            ["需求与设计", "第 1–2 周", "痛点调研、功能矩阵与验收判据", "每项需求绑定可复核判据：评测集、接口断言、契约对账"],
            ["核心引擎", "第 3–5 周", "词典引擎 + 评分公式 + 危机词表", "词表单一真相源，两端一致性守卫三层比对"],
            ["可视化与叙事", "第 4–6 周", "3D 星雾、五幕滚动、降级链路", "无 WebGL 自动降级为渐变背景"],
            ["模型补强", "第 7–8 周", "数据管道 → 微调 → 三级路由 → 盲测", "train 3622 / dev 970 / blind 237，无泄漏断言放行"],
            ["测试与加固", "贯穿全程", "101 用例、覆盖率门禁、契约对账", "行覆盖 97.00% / 分支 95.21%，低于阈值即构建失败"],
            ["部署上线", "第 8–9 周", "三路部署全在线", "Cloudflare Pages 主 / CloudBase 备 / Docker 482MB 或 fat jar"],
        ],
    },
    {
        # 官方六部分大纲（六）附录 —— 软件设计资料 / 核心代码 / 测试数据 / 参考文献
        "kicker": "APPENDIX",
        "title": "附录：设计资料、核心代码、测试数据与参考文献",
        "subtitle": "对应官方大纲第六部分，评委可在材料包与在线环境中按图索骥",
        "cols": [1.55, 3.15, 4.2],
        "header": ["类别", "内容", "在哪里 / 如何查"],
        "rows": [
            ["软件设计资料", "系统架构图、三级路由流程图、降级时序", "本册第 7 页（总架构）与第 22 页（路由）"],
            ["核心代码", "三级路由 EmotionClassifier.java / ModelProxy.java / 词典评分公式", "代码包随作品材料一并提交（网盘，按官方命名）"],
            ["测试数据", "73 条评测集逐条结果、237 条盲测四路对比、性能指标", "本册第 23 页；亦可 GET /api/emotion/eval 现场重跑"],
            ["参考文献", "心理健康蓝皮书系列；BERT 与 chinese-roberta-wwm-ext；SMP2020-ECDT；官方竞赛规则", "详见《作品方案》第 6.4 节清单"],
            ["其他材料", "用户试用反馈、代码包（网盘）", "网盘命名：团队编号-赛题名称-作品名称-XX"],
        ],
    },
]


def duplicate_slide(prs, src_index):
    """完整复制一页（含 p:bg 背景图及其关系），不依赖 PowerPoint COM。

    用户这份 PPT 的背景是每页各自引用的图片（<p:bg><p:bgPr><a:blipFill><a:blip r:embed>），
    只拷形状会丢背景，所以这里连关系和背景节点一起搬运并做 rId 重映射。
    """
    src = prs.slides[src_index]
    new = prs.slides.add_slide(src.slide_layout)

    # 清掉从布局继承来的占位符（用户模板本身无固定占位符）
    for shp in list(new.shapes):
        shp._element.getparent().remove(shp._element)

    # 搬形状
    for shp in src.shapes:
        new.shapes._spTree.append(copy.deepcopy(shp._element))

    # 搬关系（notesSlide 不复制，否则会多挂备注页）
    rid_map = {}
    for rid, rel in src.part.rels.items():
        if "notesSlide" in rel.reltype:
            continue
        if rel.is_external:
            rid_map[rid] = new.part.rels.get_or_add_ext_rel(rel.reltype, rel.target_ref)
        else:
            rid_map[rid] = new.part.rels.get_or_add(rel.reltype, rel.target_part)

    # 搬背景并重映射 rId（注意：p:bg 是 p:cSld 的子节点，不能用 p:sld.find 直接找）
    src_cSld = src.part._element.find(qn("p:cSld"))
    src_bg = src_cSld.find(qn("p:bg")) if src_cSld is not None else None
    if src_bg is not None:
        new_el = new.part._element
        cSld = new_el.find(qn("p:cSld"))
        for old in cSld.findall(qn("p:bg")):
            cSld.remove(old)
        bg = copy.deepcopy(src_bg)
        for node in bg.iter():
            for attr in (qn("r:embed"), qn("r:link"), qn("r:id")):
                val = node.get(attr)
                if val and val in rid_map:
                    node.set(attr, rid_map[val])
        cSld.insert(0, bg)
    return new


def set_text(tf, text):
    """写入文本并保留首个 run 的字体样式（原素材多为整段同格式）。"""
    paras = tf.paragraphs
    p0 = paras[0]
    runs = list(p0.runs)
    if not runs:
        r = p0.add_run()
        runs = [r]
    runs[0].text = text
    for r in runs[1:]:
        r._r.getparent().remove(r._r)
    for p in paras[1:]:
        if not p.text.strip():
            continue
        keep = list(p.runs)
        for r in keep[1:]:
            r._r.getparent().remove(r._r)
        if keep:
            keep[0].text = ""


def apply_text_fixes(prs):
    hits = 0
    for slide in prs.slides:
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            for para in sh.text_frame.paragraphs:
                joined = "".join(r.text for r in para.runs)
                for old, new in TEXT_FIXES:
                    if old not in joined:
                        continue
                    # 命中整段：整段文本交给首个 run，保留首 run 样式
                    if any(old in r.text for r in para.runs):
                        for r in para.runs:
                            if old in r.text:
                                r.text = r.text.replace(old, new)
                                hits += 1
                    else:
                        new_text = joined.replace(old, new)
                        runs = list(para.runs)
                        runs[0].text = new_text
                        for r in runs[1:]:
                            r._r.getparent().remove(r._r)
                        hits += 1
    return hits


def tune_table(shape, spec):
    """复用用户表格样式（原 cols=4 / rows=13），裁剪行数并按内容重排列宽。"""
    tbl = shape.table
    need = len(spec["rows"]) + 1  # 含表头

    # 1) 行数裁剪（多余行从末尾删除）
    el = tbl._tbl
    trs = list(el.tr_lst)
    for tr in trs[need:]:
        el.remove(tr)
    while len(el.tr_lst) < need:  # 兜底：不足则复制末行
        last = el.tr_lst[-1]
        el.append(copy.deepcopy(last))

    # 2) 列数裁剪 + 列宽（用户模板为 4 列；单位 EMU）
    n_cols = len(spec["cols"])
    grid = el.tblGrid
    if len(grid.gridCol_lst) > n_cols:
        for gc in list(grid.gridCol_lst)[n_cols:]:
            grid.remove(gc)
        for tr in el.tr_lst:  # 每行同步删掉多余的 a:tc，否则表格结构非法
            for tc in list(tr.findall(qn("a:tc")))[n_cols:]:
                tr.remove(tc)
    total_emu = shape.width
    for i, ratio in enumerate(spec["cols"]):
        if i >= len(grid.gridCol_lst):
            break
        frac = ratio / sum(spec["cols"])
        grid.gridCol_lst[i].set("w", str(int(Emu(total_emu) * frac)))

    # 3) 文本写入：表头沿用原表头样式，表体沿用原表体样式
    header_src = [r.font for r in tbl.cell(0, 0).text_frame.paragraphs[0].runs[:1]]
    for c, txt in enumerate(spec["header"]):
        cell = tbl.cell(0, c)
        cell.text = ""
        para = cell.text_frame.paragraphs[0]
        run = para.add_run()
        if header_src:
            run.font.size = header_src[0].size
            run.font.name = header_src[0].name
            run.font.bold = True
            try:
                run.font.color.rgb = header_src[0].color.rgb
            except Exception:
                pass
        run.text = txt

    body_src = [r.font for r in tbl.cell(1, 1).text_frame.paragraphs[0].runs[:1]]
    for ri, row in enumerate(spec["rows"], start=1):
        for ci, txt in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.text = ""
            para = cell.text_frame.paragraphs[0]
            run = para.add_run()
            if body_src:
                try:
                    run.font.size = body_src[0].size
                    run.font.name = body_src[0].name
                    run.font.color.rgb = body_src[0].color.rgb
                except Exception:
                    run.font.size = Pt(10)
            else:
                run.font.size = Pt(10)
            run.font.name = "微软雅黑"
            run.text = txt


def build_new_slides(prs, start_page):
    total = len(prs.slides)
    first_new = start_page - 1  # 0-based
    for i, spec in enumerate(NEW_SLIDES):
        slide = prs.slides[first_new + i]
        shapes = list(slide.shapes)
        # 模板结构（源自用户第 14 页）：#0 标签底色  #1 标签文字  #2 标题  #3 副标题  #4 表格  #5 页码
        set_text(shapes[1].text_frame, spec["kicker"])
        set_text(shapes[2].text_frame, spec["title"])
        set_text(shapes[3].text_frame, spec["subtitle"])
        set_text(shapes[5].text_frame, str(start_page + i))
        tune_table(shapes[4], spec)
    return len(NEW_SLIDES)


def main():
    """只负责「写内容」。版式页复制与 PDF 导出由 Shell 侧脚本承担：
         prepare_base.ps1  →  build_aic_ppt.py  →  export_pdf.ps1

       不合并的原因：Python 子进程唤起 PowerPoint COM 会报 TYPE_E_CANTLOADLIBRARY
       （拿不到 Office 类型库），只有从 Shell 直接唤起 COM 才稳定。
    """
    if not ORIGINAL.exists():
        print("✗ 找不到用户原稿：", ORIGINAL)
        return 1
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # 0) 用户原稿只读备份（存在即不覆盖）
    backup = BACKUP_DIR / "心屿MindIsle_参赛方案.原版备份-20261009.pptx"
    if not backup.exists():
        shutil.copy2(ORIGINAL, backup)
        print(f"   已建原稿只读备份：{backup}")

    # 1) 从「用户的原稿」重建中间底座：20 页 + n 张沿用其第 14 页版式的空白页
    base = HERE / "_build_base.pptx"
    shutil.copy2(ORIGINAL, base)
    prs = Presentation(str(base))
    tpl_index = 13  # 用户第 14 页（0-based）：标签条 + 标题 + 副标题 + 表格 + 页码
    for _ in range(len(NEW_SLIDES)):
        duplicate_slide(prs, tpl_index)
    prs.save(str(base))
    print(f"   底座就绪：{len(prs.slides)} 页（20 用户页 + {len(NEW_SLIDES)} 版式页，背景图已继承）")

    # 2) 在底座上写内容，输出为派生文件（用户的原稿不被写入）
    prs = Presentation(str(base))
    if len(prs.slides) != 20 + len(NEW_SLIDES):
        print(f"✗ 页数异常：{len(prs.slides)}（应为 {20 + len(NEW_SLIDES)}）")
        return 1
    hits = apply_text_fixes(prs)
    build_new_slides(prs, 21)
    prs.save(str(DST))

    print(f"✅ 派生文件：{DST}")
    print(f"   用户原稿 20 页零改动；赛道/日期/团队口径修正 {hits} 处；末尾新增 {len(NEW_SLIDES)} 页")
    print("   下一步：powershell -File export_pdf.ps1")

    check = Presentation(str(DST))
    print(f"   复算页数：{len(check.slides)} 页（20 + {len(NEW_SLIDES)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
