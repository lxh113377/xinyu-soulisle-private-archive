# -*- coding: utf-8 -*-
"""gh 凭据取数的唯一入口（r96 立）。

要拦的形态（一手实测）：`_test/peer_memory_probe.py:358`、`_test/peer_sec_headers_probe.py:212`、
`_test/peer_community_probe.py:283` 三件只读 `GITHUB_TOKEN` / `GH_TOKEN` 环境变量，
**从不回落 `gh auth token`**。本机 `gh` 是通过 keyring 登录的（`gh auth token` 实测有值），
而 shell 里没有那两个环境变量 ⇒ 三件探针在本机**结构性取不到凭据**，稳定报
`MEMPEER-UNVERIFIED: 无 GitHub token` / rc=2。

这件事有两层坏：
  ① rc=2 的语义被污染。判据写的是「环境未验（无凭据）」，实际是「取凭据的方式只有一条」——
     红因会被记成"这台机器没配 token"，而配了也照样取不到。
  ② 探针的 `peers` 面因此长期不刷新 ⇒ 台账超 fuse（正是 `_test/ledger_age_check.py`
     本轮点名它们的原因）。**换句话说：判据报的"数据旧"，根因是取数件的凭据面单一。**

先例在同仓：`peer_maintenance_probe.gh_token()`（r95 立）与 `peer_capability_safety_probe.py:155`
之后都做了 `gh auth token` 回落。本件把这个形态收成一处，三件探针各自 import，
**不在三份文件里各抄一遍**（抄了就会出现"改了 2 个忘 1 个"）。

本件是库不是判据：不进电池、不写盘、无副作用（G9 import-safe）。
"""
import os
import subprocess

_TOKEN = {"cached": None}


def gh_credential(timeout=60):
    """环境变量优先，其次 `gh auth token`。取不到返回 ""（调用方据此判 rc=2 环境未验）。"""
    for k in ("GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(k)
        if v and v.strip():
            _TOKEN["cached"] = v.strip()
            return _TOKEN["cached"]
    if _TOKEN["cached"] is not None:
        return _TOKEN["cached"]
    try:
        p = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        _TOKEN["cached"] = (p.stdout or "").strip() if p.returncode == 0 else ""
    except Exception:                                          # noqa: BLE001 —— 取不到就是空串
        _TOKEN["cached"] = ""
    return _TOKEN["cached"]


def credential_source():
    """凭据来自哪一面（报因用，别把"环境变量"和"gh 钥匙串"混成一句话）。"""
    if os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
        return "env"
    return "gh-auth-token" if gh_credential() else "none"
