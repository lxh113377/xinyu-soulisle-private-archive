-- 心屿 J4 持久化表结构（H2 / MySQL 双兼容；IF NOT EXISTS 保证可重复启动）
-- 说明：created_at 由应用侧显式写入（不用 DEFAULT CURRENT_TIMESTAMP），避免两端默认值语义漂移。

CREATE TABLE IF NOT EXISTS chat_message (
  id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
  session_id  VARCHAR(64)  NOT NULL,
  role        VARCHAR(16)  NOT NULL,
  content     VARCHAR(2000) NOT NULL,
  created_at  TIMESTAMP    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_message_session ON chat_message (session_id, id);

CREATE TABLE IF NOT EXISTS emotion_record (
  id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
  session_id  VARCHAR(64)  NOT NULL,
  emotion     VARCHAR(16)  NOT NULL,
  intensity   DOUBLE       NOT NULL,
  secondary   VARCHAR(16),
  text        VARCHAR(200) NOT NULL,
  created_at  TIMESTAMP    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_emotion_record_session ON emotion_record (session_id, id);
