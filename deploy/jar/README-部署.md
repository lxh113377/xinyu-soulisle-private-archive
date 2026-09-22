# 心屿 SoulIsle · fat jar 部署包（L5）

> 目标：把已建成的 Java 服务端部署到**国内可达的机器**上，摆脱 CloudBase 测试域名首访的「风险提醒」中间页。
> 本目录只放**启动脚本与说明**，不含 29 MB 的 jar 与前端副本 —— 脚本会自动定位仓库内的产物，也支持独立目录部署。

## 一、两种部署形态

| 形态 | 目录摆放 | 适用场景 |
|---|---|---|
| **A. 仓库内直接起**（推荐先验证） | 保持仓库结构，`server/target/soulisle-server.jar` + `src/` | 本机、有仓库的机器 |
| **B. 独立目录部署** | 建一个目录，放 `soulisle-server.jar` + `web/`（前端）+ 本目录两个脚本 + `emotion-eval-dataset.json` | 拷贝到任意目标机器（含无仓库的云服务器） |

形态 B 的 `web/` 用 `deploy/xinyu/` 的**公网零密钥版**（禁止用 `src/`，`src/js/demo-config.js` 含真实 Key）。

## 二、启动

```powershell
# Windows（形态 A，默认 8080，前端直读仓库 src/）
.\start.ps1

# Windows（形态 B / 指定端口与静态根）
.\start.ps1 -Port 8080 -WebRoot "D:\xinyu\web"

# Windows（私有部署开启鉴权）
.\start.ps1 -Token "your-secret"
```

```bash
# Linux
chmod +x start.sh
./start.sh --port 8080 --web-root /opt/xinyu/web
```

脚本会做四件事：定位 jar → 定位静态根目录（校验 `index.html` 存在）→ 注入环境变量 → 拉起 `java -jar`。
**找不到 jar 或缺 `index.html` 时直接报错退出**，不会带病启动。

## 三、环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `DEEPSEEK_KEY` | 否 | 不设则 `/api/chat` 回落离线模板（界面明示「离线」，不伪装在线） |
| `XINYU_WEB_ROOT` | 否 | 脚本自动设；不设则服务端默认 `./src/`（**要求工作目录 = 项目根**） |
| `XINYU_API_TOKEN` | 否 | 留空=不鉴权（演示默认）；置非空则 `/api/**` 除 `/api/health` 需 `X-Xinyu-Token` |
| `XINYU_EVAL_DATASET` | 否 | 评测集直读路径；脚本在同目录发现 `emotion-eval-dataset.json` 时自动设置 |

> 红线：**密钥只走环境变量，零落前端、零入库。**

## 四、部署后验收（逐条跑，全部为真才算部署成功）

```powershell
# 1) 健康检查（webRoot 必须解析到实际目录，indexFound/vendorFound 均 true）
Invoke-RestMethod http://<host>:8080/api/health

# 2) 首页与静态资源
(Invoke-WebRequest http://<host>:8080/ -UseBasicParsing).StatusCode              # 200
(Invoke-WebRequest http://<host>:8080/js/app.js -UseBasicParsing).StatusCode     # 200
(Invoke-WebRequest http://<host>:8080/vendor/three.min.js -UseBasicParsing).StatusCode  # 200

# 3) 前端零密钥（关键红线，公网部署必查）
#    抓首页 + js/demo-config.js，不得出现 sk- 开头的字符串

# 4) 情绪引擎复跑（评委可现场复现的 97.2%）
Invoke-RestMethod http://<host>:8080/api/emotion/eval

# 5) 持久化（J4，需前端 cfg.remote=true）
#    对话几句 → 清空 localStorage → 刷新，星图仍点亮 => 数据真来自数据库
```

## 五、实测留痕

| 项 | 实测值（2026-09-23） |
|---|---|
| JDK | `17.0.20.1`（Temurin） |
| jar | `server/target/soulisle-server.jar`，29,414,999 B，构建于 2026-09-22 01:12:06（**晚于** Java 源码最新改动 01:11:30，未过期） |
| `/api/health` | `status=UP` / `webRoot` 正确 / `indexFound=true` / `vendorFound=true` |
| `/api/emotion/eval` | 71 条 / 97.2% / 危机召回 6/6，与 JS 侧逐项全等 |
| 独立目录部署 | ✅ 实测：从任意工作目录启动 + `-WebRoot` 指向仓库外的静态副本，首页 200 |

## 六、实测踩坑（脚本里已修，别再踩）

1. **默认 `JAVA_HOME` 是 JDK 8** —— Spring Boot 3（class 文件 v61）在 JDK 8 下直接 `UnsupportedClassVersionError` 起不来。脚本改为**探测版本**（要求 major ≥ 17）而不是信任 `JAVA_HOME`；探测不到就报错退出。
2. **探测函数不能用 `& $java -version 2>&1`** —— 本脚本顶部有 `$ErrorActionPreference = 'Stop'`，PowerShell 会把原生命令的 stderr 变成终止性 ErrorRecord，探测**恒为 false**。`java -version` 恰好只写 stderr，所以必须经 `cmd /c` 合并流再取文本。
3. **H2 数据文件路径跟随工作目录** —— 启动日志为 `jdbc:h2:file:./server/data/xinyu`，是相对**进程工作目录**的。独立目录部署时务必先 `cd` 到部署目录再启动，否则数据库会建到别处（用 MySQL 可彻底避开，见 `application.yml`）。

## 七、容器化（Docker）

```bash
# 前置 1：先同步公网版前端并跑 SHA256 双向比对（同步红线）
# 前置 2：mvn -f server/pom.xml package
docker build -f server/Dockerfile -t xinyu-soulisle .   # build context 必须是仓库根
docker run -p 8080:8080 -e DEEPSEEK_KEY=sk-xxx -v xinyu-data:/app/data xinyu-soulisle
```

> ⚠️ **2026-09-23 修了一条红线级问题**：原 Dockerfile 写 `COPY src/ /app/web/`，会把含**真实 API Key** 的
> `src/js/demo-config.js` 打进镜像（与其自身注释「密钥绝不打进镜像」矛盾）。现改为 `COPY deploy/xinyu/`
> （公网零密钥版），并新增根目录 `.dockerignore` 做纵深防御。
> **代价**：镜像内前端走 proxy stub 且不含 `remote`（J4 公网默认关闭），与 Pages/CloudBase 形态一致 —— 这是我们要的形态。
> **新约束**：构建前必须先同步 `deploy/xinyu/` 并跑 SHA256 双向比对，否则会把过时前端打进镜像。

已做的三层静态核验（无需 Docker 即可证）：① `git check-ignore` 命中 `.gitignore:9:src/js/demo-config.js`；② `deploy/xinyu/**`（12 文件）`sk-` 正则 **0 命中**；③ fat jar 抽字节后（29,415,359 B）`sk-` **0 命中**。

## 八、装 Docker（老大执行，2026-09-23 定：走 Docker Desktop）

```powershell
# 管理员权限的 PowerShell / 终端里执行（会弹 UAC，需本人点确认；装完需重启）
winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
```

装完重启后回来说一句「好了」，我接着执行（无需你再决策）：

1. `docker version` 确认 daemon 起来了
2. `python _test/deploy_sync_check.py` —— **构建前置闸门**：公网版前端必须与 `src/` 三类归零，否则会把过时/带缺陷的前端打进镜像
3. `docker build -f server/Dockerfile -t xinyu-soulisle .`（context = 仓库根）
4. `docker run -d -p 8080:8080 -v xinyu-data:/app/data xinyu-soulisle`
5. 验收：`/api/health`（`UP` + `indexFound/vendorFound=true`）、`/`、`/js/app.js`、`/vendor/three.min.js`、`/api/emotion/eval`（73 条 / 98.6%）
6. **镜像内密钥扫描**：`docker run --rm xinyu-soulisle sh -c "grep -rE 'sk-[A-Za-z0-9]{20,}' /app || echo CLEAN"` —— 必须 `CLEAN`
7. 清理容器；把实测结果回填本文档与 `08-ac-obs.md`

## 九、已知未验项

- **Docker 镜像构建/运行未实测**：本机**未安装 Docker**（`docker` 不在 PATH，`C:\Program Files\Docker\Docker` 不存在）。上面的命令**一条都没跑过**，装好 Docker 后必须真跑一次再对外声称已验证。
- **真实云服务器部署未做**：需要老大提供目标机器（IP / 登录方式 / 是否有公网与安全组放行端口）。
- **`start.sh` 未实跑**：本机为 Windows，仅做了静态检查（语法 + JDK 探测逻辑与 ps1 同构），未真机验证。已用 `.gitattributes`（`*.sh text eol=lf`）保证行尾不被转成 CRLF。
- **两条装 Docker 的路都卡在需要老大本人在场**：① Docker Desktop（`winget install -e --id Docker.DockerDesktop`）→ 需 **UAC 点确认 + 重启**；② WSL2 内 Ubuntu 26.04 装 `docker.io` → 需 **sudo 密码**，且 WSL 当前报「localhost 代理未镜像到 WSL」，apt 联网可能受阻。
