-- 心屿 J4 持久化表结构（H2 / MySQL 双兼容；可重复启动）
-- 索引必须内联成表内 KEY：MySQL 不支持 CREATE INDEX IF NOT EXISTS（实测 ERROR 1064），
-- 而裸 CREATE INDEX 两侧第二次启动都报错（H2 42111 / MySQL 1061）。内联后幂等由表级
-- IF NOT EXISTS 承载。代价：H2 须带 MODE=MySQL（默认 URL/.env.example/Dockerfile 三处均已带）。
-- 说明：created_at 由应用侧显式写入（不用 DEFAULT CURRENT_TIMESTAMP），避免两端默认值语义漂移。

CREATE TABLE IF NOT EXISTS chat_message (
  id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
  session_id  VARCHAR(64)  NOT NULL,
  role        VARCHAR(16)  NOT NULL,
  content     VARCHAR(2000) NOT NULL,
  created_at  TIMESTAMP    NOT NULL,
  KEY idx_chat_message_session (session_id, id)
);

CREATE TABLE IF NOT EXISTS emotion_record (
  id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
  session_id  VARCHAR(64)  NOT NULL,
  emotion     VARCHAR(16)  NOT NULL,
  intensity   DOUBLE       NOT NULL,
  secondary   VARCHAR(16),
  text        VARCHAR(200) NOT NULL,
  created_at  TIMESTAMP    NOT NULL,
  KEY idx_emotion_record_session (session_id, id)
);
