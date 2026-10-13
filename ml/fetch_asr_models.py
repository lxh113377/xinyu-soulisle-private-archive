# -*- coding: utf-8 -*-
"""心屿 · 拉取 ASR sidecar 模型（B1 第一步，可复现）

为什么单独一个脚本：模型体量大（int8 约 250MB）且**不入库**（与 ml/tts 的模型资产同一条红线：
`D:/xinyu-ml/` 在 .gitignore 的 ml/ 资产段）。写死"从哪个 repo 拉哪些文件、拉到哪、拉完自证什么"，
下一台机器重建环境只需跑这一条，不必凭记忆重找模型名。

选型实测记录（2026-10-14，一手）：
  · 引擎 = sherpa-onnx 的 SenseVoice（`OfflineSenseVoiceModelConfig`）。
    理由：官方与 sherpa 文档均列 Mandarin / **粤语** / EN / JA / KO 五语，并有专文对比
    「SenseVoice 保住真粤语，Whisper 不行」——本项目的方言场景**必须**要粤语原生能力。
  · 许可：SenseVoiceSmall 在 ModelScope 标 **Apache License 2.0**（宽松，比赛/商用无碍）；
    ONNX 导出包是 csukuangfj（sherpa-onnx 作者）的社区镜像，LICENSE 指向同一出处。
  · 取 int8 权重而非 fp32：本机 RTX 5070 Ti 只有 12GB 显存，且本 sidecar 的定位是
    「浏览器 Web Speech 兜底 + 评测集转写」——int8 的 CER 代价在评测脚本里会与 fp32 对照量化，
    不在这里预设"没差"。

用法：
  D:/xinyu-ml/asr-venv/Scripts/python.exe ml/fetch_asr_models.py [--check]
    （不带 --check = 下载；带 --check = 只校验已下载的文件，不联网）
"""
import hashlib
import os
import sys

REPO = "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
DEST = os.environ.get("XINYU_ASR_MODEL_DIR", "D:/xinyu-ml/asr/sensevoice-int8-2024-07-17")
# 只要推理必需的两个件。test_wavs/ 是上游的示例音频，其中 yue.wav 被评测集冒烟测试直接引用，
# 所以也拉下来（缺了它，冒烟测试只能判"未验"而不是"通过"）。
FILES = ("model.int8.onnx", "tokens.txt", "test_wavs/yue.wav", "README.md")


def sha256_of(path, limit=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(limit)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def check():
    """只读校验：每个件都在、非空，并打出 sha256 与体积（供判据/台账引用）"""
    ok = True
    for name in FILES:
        p = os.path.join(DEST, name.replace("/", os.sep))
        if not os.path.isfile(p) or os.path.getsize(p) == 0:
            print("  MISSING %s" % name)
            ok = False
            continue
        print("  OK %-22s %10d B  sha256=%s" % (name, os.path.getsize(p), sha256_of(p)[:16]))
    return ok


def main():
    if "--check" in sys.argv[1:]:
        return 0 if check() else 1
    os.makedirs(DEST, exist_ok=True)
    from huggingface_hub import hf_hub_download
    for name in FILES:
        p = hf_hub_download(REPO, name, local_dir=DEST)
        print("  fetched %-22s %10d B" % (name, os.path.getsize(p)))
    print("MODEL-FETCH-PASS 目标目录 %s" % DEST)
    return 0 if check() else 1


if __name__ == "__main__":
    raise SystemExit(main())
