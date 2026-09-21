# 心屿 SoulIsle 服务端镜像（J5）
#
# 构建（**build context 必须是仓库根**，因为前端权威源 src/ 在根下）：
#   mvn -f server/pom.xml package
#   docker build -f server/Dockerfile -t xinyu-soulisle .
#
# 运行（密钥只走环境变量，绝不打进镜像）：
#   docker run -p 8080:8080 -e DEEPSEEK_KEY=sk-xxx -v xinyu-data:/app/data xinyu-soulisle

FROM eclipse-temurin:17-jre

WORKDIR /app

# fat jar 由 Maven repackage 产出
COPY server/target/soulisle-server.jar /app/app.jar

# 前端静态页与评测集**不在 jar 内**：服务端直读外部目录（权威源 src/，零副本），
# 所以镜像里也必须带着它们，否则页面会 404。
COPY src/ /app/web/
COPY _test/emotion-eval-dataset.json /app/_test/emotion-eval-dataset.json

ENV XINYU_WEB_ROOT=/app/web
ENV XINYU_EVAL_DATASET=/app/_test/emotion-eval-dataset.json
ENV XINYU_DB_URL="jdbc:h2:file:/app/data/xinyu;MODE=MySQL;DB_CLOSE_DELAY=-1"
ENV DEEPSEEK_BASE=https://api.deepseek.com/v1
ENV DEEPSEEK_MODEL=deepseek-chat

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
