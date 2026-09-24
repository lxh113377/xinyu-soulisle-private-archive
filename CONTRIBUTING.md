# 贡献指南 — 心屿 SoulIsle

感谢关注！本仓库改动半径小、红线多，动手前请先读完本页。

## 环境要求

| 工具 | 版本 | 说明 |
|---|---|---|
| JDK | **17**（必须显式设置 `JAVA_HOME`） | 系统默认可能是 JDK 8，Spring Boot 3 会编译失败 |
| Maven | 3.9+ | `mvn -f server/pom.xml package` |
| Node.js | 20+ | 跑情绪评测与前端一致性脚本 |
| Python | 3.10+ | 回归脚本（仅标准库，无需 pip 安装） |

## 四条红线（违反任一 = 拒收）

1. **密钥红线**：密钥零落前端、零入库、零进镜像。环境变量文档写进 `.env.example`（占位符），真实值只走部署平台。
2. **同步红线**：改 `src/` 必须同步 `deploy/xinyu/`，并跑 `python _test/deploy_sync_check.py` 至 `DEPLOY-SYNC-PASS`（MISSING/DIFF/EXTRA 三类归零）。`deploy/xinyu/js/demo-config.js` 是零密钥代理版，**禁止**被 `src` 版覆盖。
3. **词表一致性红线**：情绪引擎 JS/Java 两端并存（本地那份是离线降级，不可删）。改任一端词表必须两端同步，并跑 `python _test/engine_consistency_check.py`（词表结构 / 逐条 73 预测 / 汇总指标三层判据，不一致即失败）。
4. **契约红线**：`POST /api/chat` 与 v1 Pages Function 保持 1:1（错误体、判定顺序、上游透传均一致），改动须同步更新并通过 `_test/j2_chat_contract.py`（单变量对照：A 组在线 / B 组回落离线）。

## 开发流程

```bash
# 1. 起服务（工作目录必须是仓库根——静态页直读 ./src/）
java -jar server/target/soulisle-server.jar --server.port=8123

# 2. 改动后本地验证（CI 会复跑同样判据）
python _test/deploy_sync_check.py       # src ↔ deploy 同步守卫
node _test/emotion_eval.js              # 情绪评测（73 条，输出 JSON）
mvn -f server/pom.xml -B package        # Java 构建

# 3. 涉及前端运行时行为时，追加：
python _test/browser_check.py           # 离线降级/双色/滚动淡入淡出 → ALL-ASSERT-PASS
python _test/pixel_dual_check.py        # 双色像素级三用例
python _test/public_check.py            # KEY_LEAK: False
```

## 提交规范

沿用仓库既有风格：`type(范围): 中文描述`，type ∈ `feat / fix / perf / docs / test / chore`。
一次提交一件事；文档与代码分开提交。

## 其它约定

- 禁止把前端复制进 `server/src/main/resources/static/`（零副本策略，见 README「架构」）。
- 禁止把评测集复制进 jar 资源目录（服务端直读 `_test/emotion-eval-dataset.json`）。
- 新增 `_test/` 回归脚本必须自带失败出口（非零退出码），不允许"打印 FAIL 但 exit 0"。
- Java 源码一律 UTF-8；构建前确认 JDK 17（`java -version` 应为 17.x）。
