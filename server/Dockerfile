# 心屿 SoulIsle 服务端镜像（J5）
#
# 构建（**build context 必须是仓库根**）：
#   mvn -f server/pom.xml package
#   docker build -f server/Dockerfile -t xinyu-soulisle .
#
# 运行（密钥只走环境变量，绝不打进镜像）：
#   docker run -p 8080:8080 -e DEEPSEEK_KEY=sk-xxx -v xinyu-data:/app/data xinyu-soulisle
#
# ⚠️ 2026-09-23 修正（红线级）：原版 `COPY src/ /app/web/` 会把
#    `src/js/demo-config.js` 一起打进镜像，而该文件含**真实 API Key**（本地演示用）。
#    这与本文件原先写的「密钥绝不打进镜像」直接矛盾。
#    改为 COPY `deploy/xinyu/`（公网零密钥版，前端权威部署产物）。
#    代价：镜像内前端走 proxy stub（`/api/chat`），且不含 `remote`（J4 公网默认关闭），
#    与 Pages/CloudBase 的公网形态一致 —— 这正是我们要的形态。
#    ⚠️ 因此**构建前必须先同步 deploy/xinyu 并跑 SHA256 双向比对**（项目同步红线），
#    否则会把过时的前端打进镜像。

FROM eclipse-temurin:17-jre

WORKDIR /app

# fat jar 由 Maven repackage 产出（JDK 17）
COPY server/target/soulisle-server.jar /app/app.jar

# 前端静态页不在 jar 内：服务端直读外部目录（零副本策略），镜像里必须带一份。
# 用 deploy/xinyu/（零密钥公网版），禁止改用 src/（含 Key）。
COPY deploy/xinyu/ /app/web/

# 评测集同样不在 jar 内（决策 #5：不复制进资源目录，保证双端跑同一份数据）
COPY _test/emotion-eval-dataset.json /app/_test/emotion-eval-dataset.json

# H2 数据落挂载卷：容器重建不丢
VOLUME /app/data

ENV XINYU_WEB_ROOT=/app/web
ENV XINYU_EVAL_DATASET=/app/_test/emotion-eval-dataset.json
ENV XINYU_DB_URL="jdbc:h2:file:/app/data/xinyu;MODE=MySQL;DB_CLOSE_DELAY=-1"
ENV DEEPSEEK_BASE=https://api.deepseek.com/v1
ENV DEEPSEEK_MODEL=deepseek-chat

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
