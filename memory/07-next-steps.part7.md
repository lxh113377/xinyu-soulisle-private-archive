# 07-next-steps.part7.md

<!-- 本卷为 07-next-steps.md 的延续 -->

- [x] **J4 持久化** ✅ 2026-09-22：`chat_message` / `emotion_record` 两表（MyBatis-Plus 3.5.7 + **H2 file 默认 / MySQL 8 可切**）+ `/api/memory/**` CRUD。实测**跨重启持久**（2 emotion / 2 message 重启后仍在）、`DELETE` 清除 `removed=4` 且会话隔离。前端接入为**可选项**（`cfg.remote===true`，默认关闭）：`_test/j4_memory_check.py` **J4-MEMORY-PASS** —— 核心断言「**清空 localStorage 后刷新星图仍点亮 6 颗**」证明数据真来自数据库；对照组默认关闭时服务端 0/0（判据非恒真）
