-- 心屿 J4 持久化表结构（H2 / MySQL 双兼容；可重复启动）
-- 索引必须内联成表内 KEY：MySQL 不支持 CREATE INDEX IF NOT EXISTS（实测 ERROR 1064），
-- 而裸 CREATE INDEX 两侧第二次启动都报错（H2 42111 / MySQL 1061）。内联后幂等由表级
-- IF NOT EXISTS 承载。代价：H2 须带 MODE=MySQL（默认 URL/.env.example/Dockerfile 三处均已带）。
-- 说明：created_at 由应用侧显式写入（不用 DEFAULT CURRENT_TIMESTAMP），避免两端默认值语义漂移。
-- 字符集必须写在建表语句里，不能靠服务器默认（r130 实测反例腿：latin1 服务器上中文写入
-- ERROR 1366 / HTTP 500）。COLLATE 取 utf8mb4_unicode_ci 而非 utf8mb4_0900_ai_ci：前者在
-- MySQL 5.7 与 8.x 都存在，跨版本可迁；H2 2.2.224（MODE=MySQL）实测**接受并忽略**这段表选项，
-- 所以不需要拆双方言文件（多一处副本就多一处漏同步，见决策 #2）。
-- ENGINE 显式写 InnoDB：表锁的 MyISAM 撑不住 clear() 的两表事务，也不支持事务回滚。

CREATE TABLE IF NOT EXISTS chat_message (
  id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
  session_id  VARCHAR(64)  NOT NULL,
  role        VARCHAR(16)  NOT NULL,
  content     VARCHAR(2000) NOT NULL,
  created_at  TIMESTAMP    NOT NULL,
  KEY idx_chat_message_session (session_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS emotion_record (
  id          BIGINT       AUTO_INCREMENT PRIMARY KEY,
  session_id  VARCHAR(64)  NOT NULL,
  emotion     VARCHAR(16)  NOT NULL,
  intensity   DOUBLE       NOT NULL,
  secondary   VARCHAR(16),
  text        VARCHAR(200) NOT NULL,
  created_at  TIMESTAMP    NOT NULL,
  KEY idx_emotion_record_session (session_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
