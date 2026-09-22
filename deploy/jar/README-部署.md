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

## 八、Docker 环境（2026-09-23 已装好并**全链路实测通过**）

### 8.1 安装（已完成）

Docker Desktop 4.91.0，daemon 实测 `Server 29.8.0 / linux / overlayfs`。

```powershell
# 管理员权限的 PowerShell / 终端里执行（会弹 UAC，需本人点确认；装完需重启）
winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
```

> ⚠️ **2026-09-23 实测踩坑：`winget install Docker.sbx` 装错了**。Docker Sandboxes 是「给 AI agent 用的隔离沙箱」，
> **不提供 `docker` CLI**，自带 daemon 也起不来（`sbx daemon start` 挂死无输出、进程表里没有 `sandboxd`、
> `sbx diagnose` 报 `Daemon — not reachable`；其余 9 项通过）。它**不是镜像构建器**，装它等于白装。
> 包 ID 必须**精确**写 `Docker.DockerDesktop`（写错一个词就会装到另一个产品）。

### 8.2 🔴 国内必读：Docker Hub 被墙，直接 `docker build` 必失败

实测（2026-09-23）：本机**根本无法访问 Docker Hub** ——
`registry-1.docker.io` 返回 **000**（连接超时），构建报
`failed to authorize: ... dial tcp 88.191.249.182:443: connectex: ...`

加速源连通性实测（`/v2/` 探测）：

| 源 | 结果 |
|---|---|
| `registry-1.docker.io` | **000（不通）** |
| `mirror.ccs.tencentyun.com` | **000（仅腾讯 CVM 内网可用）** |
| `docker.mirrors.ustc.edu.cn` | **000（已停止公共访问）** |
| `docker.1ms.run` | **401（通）** ← 本次使用 |
| `docker.m.daocloud.io` | 401（通） |
| `docker.1panel.live` | 200（通） |
| `hub.rat.dev` | 302（通） |

**本次采用的解法（不改 daemon 配置、不重启 Docker Desktop）**：先从可用源拉基础镜像并本地打标，
之后 build 就会用本地镜像，不再去 Docker Hub 取元数据。

```bash
docker pull docker.1ms.run/library/eclipse-temurin:17-jre
docker tag  docker.1ms.run/library/eclipse-temurin:17-jre eclipse-temurin:17-jre
docker build -f server/Dockerfile -t xinyu-soulisle .     # 此时才可成功
```

> 另一条路（更"正规"但要重启 Docker Desktop）：在 `~/.docker/daemon.json` 里加
> `"registry-mirrors": ["https://docker.1ms.run","https://docker.m.daocloud.io"]`，然后重启。
> 本次未走这条，因为前者已验证可行。

### 8.3 已执行的完整清单

下列步骤已于 2026-09-23 全部执行完毕（结果见「十」）：

1. `docker version` 确认 daemon 起来了
2. `python _test/deploy_sync_check.py` —— **构建前置闸门**：公网版前端必须与 `src/` 三类归零，否则会把过时/带缺陷的前端打进镜像
3. `docker build -f server/Dockerfile -t xinyu-soulisle .`（context = 仓库根）
4. `docker run -d -p 8080:8080 -v xinyu-data:/app/data xinyu-soulisle`
5. 验收：`/api/health`（`UP` + `indexFound/vendorFound=true`）、`/`、`/js/app.js`、`/vendor/three.min.js`、`/api/emotion/eval`（73 条 / 98.6%）
6. **镜像内密钥扫描**：`docker run --rm xinyu-soulisle sh -c "grep -rE 'sk-[A-Za-z0-9]{20,}' /app || echo CLEAN"` —— 必须 `CLEAN`
7. 清理容器；把实测结果回填本文档与 `08-ac-obs.md`

## 九、已知未验项

- ✅ ~~Docker 镜像构建/运行未实测~~ → **2026-09-23 已实测通过**（真 `docker build` + `docker run` + 镜像内密钥扫描 + 持久化重启验证），详见「十」。原先「命令一条都没跑过」的状态已解除。
- **真实云服务器部署未做**：需要老大提供目标机器（IP / 登录方式 / 是否有公网与安全组放行端口）。
- **`start.sh` 未实跑**：本机为 Windows，仅做了静态检查（语法 + JDK 探测逻辑与 ps1 同构），未真机验证。已用 `.gitattributes`（`*.sh text eol=lf`）保证行尾不被转成 CRLF。
- ✅ ~~两条装 Docker 的路都卡在需要老大本人在场~~ → **已解决**：走 Docker Desktop 4.91.0（`winget install -e --id Docker.DockerDesktop`，需 UAC + 重启）后 daemon 就绪（`Server 29.8.0 / linux / overlayfs`）。WSL2 路线未采用。
- **Docker Sandboxes 不可用**（2026-09-23 实测）：无 `docker` CLI、daemon 起不来，产品定位是 agent 隔离沙箱而非构建器。已在「八」节记录，避免重复踩。

## 十、Dockerfile 磁盘级模拟验收（2026-09-23，无 Docker 时的最强替代证据）

`python _test/docker_image_sim_check.py` —— 把 Dockerfile 在磁盘上逐行等价实现：

| Dockerfile 指令 | 模拟做法 |
|---|---|
| `COPY` | 真实拷文件（并遵守 `.dockerignore` 排除语义） |
| `ENV` | 真实注入子进程环境 |
| `WORKDIR /app` | 真实作为 java 进程 cwd |
| `ENTRYPOINT ["java","-jar","/app/app.jar"]` | 真实执行 |

> **关键设计**：COPY / ENV / WORKDIR **直接从 `server/Dockerfile` 解析，禁止手抄** —— 否则 Dockerfile 一改，
> 这份模拟就静默失效，变成「说明与实际脱钩」的假证据。

实测结果（`DOCKER-SIM-PASS`）：

```
[解析] COPY×3 ENV×5 WORKDIR=/app
[COPY] 共写入 14 个文件
[内容] 评测集 73 条
[红线] 镜像内 sk- 命中: 0
[健康] status=UP  webRoot=<tmp>/web  indexFound=true  vendorFound=true
[静态] 200 / (7437B)   200 /js/app.js   200 /vendor/three.min.js (603445B)   200 /css/style.css
[评测] 73 条 / 98.6% / 危机 6/6
```

**判据含隔离桩**（`--selftest`）：注入 1 处假密钥 + 1 个干净文件 → 命中恰好 1 处；移除后回到 0
⇒ 证明「0 命中」既不恒真也不恒假（当天已因 PowerShell 别名覆盖踩过一次假通过，故凡 0 命中类判据一律附桩）。

**它证明了什么 / 没证明什么**：
- ✅ 镜像内文件齐全、路径与 ENV 正确、静态页与 API 可用、**镜像内无密钥**
- ❌ **不等于 `docker build` 已验证** —— 该模拟只是「装好 Docker 之前」的过渡证据，**现已由真 Docker 取代**（见「十一」）

## 十一、真 Docker 实测结果（2026-09-23，已取代模拟）

环境：Docker Desktop 4.91.0 → daemon `Server 29.8.0 / linux / overlayfs`。
镜像：`xinyu-soulisle:latest`，**482 MB**（`FROM eclipse-temurin:17-jre`）。

| # | 验收项 | 实测结果 |
|---|---|---|
| 1 | `docker build` | ✅ 成功（`COPY` 三条 layer 全绿，见「8.2」的 Hub 绕行） |
| 2 | 容器状态 | ✅ `Up`，`0.0.0.0:8080->8080/tcp` |
| 3 | `/api/health` | ✅ `UP` / `webRoot=/app/web` / `indexFound=true` / `vendorFound=true` |
| 4 | 静态资源 | ✅ `/` 7437B、`/js/app.js` 14091B、`/vendor/three.min.js` 603445B、`/css/style.css` 9131B 全 200 |
| 5 | `/api/emotion/eval` | ✅ **73 条 / 98.6% / 危机召回 6-6** |
| 6 | **镜像内密钥扫描** | ✅ `IMAGE_KEY_SCAN=CLEAN` |
| 7 | 扫描判据有效性对照 | ✅ 输入非空（`/app` 15 文件）；注入假密钥 → `GREP_EFFECTIVE`；干净文件 → `NO_FALSE_POSITIVE` |
| 8 | **持久化（Docker 专属坑）** | ✅ 写 2 情绪 + 1 消息 → `docker restart` → **重启后仍为 2 / 1** ⇒ DB 确实落在挂载卷里 |
| 9 | 清理 | ✅ 测试容器与探针卷已删，仅保留镜像 |

> 第 8 项是 Docker 场景最容易踩的坑：容器内**相对路径**写的 DB 可能落在卷外，容器一删数据全丢。
> `application.yml` 的默认 `jdbc:h2:file:./server/data/xinyu` 是**相对 cwd** 的，而 Dockerfile 用
> `XINYU_DB_URL` 显式覆盖成 `/app/data/xinyu` 并把 `/app/data` 声明为 `VOLUME` —— 实测证明这条链路是通的。
