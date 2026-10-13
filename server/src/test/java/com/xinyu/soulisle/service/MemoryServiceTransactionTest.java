package com.xinyu.soulisle.service;

import com.xinyu.soulisle.mapper.ChatMessageMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

/**
 * {@code clear()} 两表删除的**事务行为**回执（r169）。
 *
 * <p>为什么不能只靠单测：{@code MemoryServiceTest} 直接 new 出 service 并塞两个假 mapper，
 * 那条路径上**没有 Spring 代理**，而 {@code @Transactional} 是代理在方法外面包的 ——
 * 不起容器就永远测不到回滚。于是 r169 之前这条要求只有结构证据
 * （{@code server_hardening_check} 的 H7 断言「注解在位」+ 摘注解即红的变异腿），
 * 「第二张表失败时第一张表必须回滚」这个**行为**一次都没被证实过。
 *
 * <p>两条腿缺一不可：只留回滚腿，「第一张表没被删」可能是「压根没执行删除」的假象，
 * 所以正向对照腿必须证明不抛异常时第一张表**真的被删干净**（②-b「反例要落在被保护分支上」
 * 与「判据两侧都要取」在本仓的第三次实踩）。
 *
 * <p>库用 {@code jdbc:h2:mem}：06-constraints 的 env_mode 红线禁止测试写演示库
 * {@code server/data/xinyu.mv.db}。表由 Flyway 的 V1 建（不是手写 DDL），所以本类同时是
 * 「迁移产物能被真实服务层跑通」的回执。
 *
 * <p>⚠️ 两个必须显式覆盖的属性（少了就起不来，且红因离缺陷很远）：surefire 的工作目录是
 * {@code server/}，所以默认 {@code ./src/} 会解析成 {@code server/src/} —— 词表加载器按
 * fail-fast 设计直接终止启动。{@code xinyu.web-root} 与 {@code xinyu.lexicon} 因此都要给。
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE, properties = {
        "spring.datasource.url=jdbc:h2:mem:xinyu-tx-receipt;MODE=MySQL;DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.datasource.username=sa",
        "spring.datasource.password=",
        "spring.flyway.enabled=true",
        "xinyu.web-root=../src",
        "xinyu.lexicon=../src/data/emotion-lexicon.js",
        "xinyu.eval.dataset=../_test/emotion-eval-dataset.json",
})
class MemoryServiceTransactionTest {

    @Autowired
    private MemoryService service;

    @Autowired
    private JdbcTemplate jdbc;

    /**
     * 只投毒第二张表的删除：mapper 是接口，Mockito 换成假 bean 后
     * 第一张表（emotion_record）仍走真库真 SQL —— 回滚与否就只能在真库上读出来。
     */
    @MockBean
    private ChatMessageMapper messageMapper;

    private void seed(String sessionId, int rows) {
        for (int i = 0; i < rows; i++) {
            jdbc.update("INSERT INTO emotion_record (session_id, emotion, intensity, secondary, text, created_at)"
                            + " VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    sessionId, "sad", 0.5, null, "情绪原文 " + i);
            jdbc.update("INSERT INTO chat_message (session_id, role, content, created_at)"
                            + " VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    sessionId, "user", "对话原文 " + i);
        }
    }

    private long emotions(String sessionId) {
        Long n = jdbc.queryForObject(
                "SELECT COUNT(*) FROM emotion_record WHERE session_id = ?", Long.class, sessionId);
        return n == null ? -1 : n;
    }

    private long messages(String sessionId) {
        Long n = jdbc.queryForObject(
                "SELECT COUNT(*) FROM chat_message WHERE session_id = ?", Long.class, sessionId);
        return n == null ? -1 : n;
    }

    @Test
    @DisplayName("回滚腿：第二张表删除抛异常 ⇒ 第一张表一条都没删（半清=隐私债）")
    void failureOnSecondTableRollsBackFirst() {
        String sid = "tx-rollback";
        seed(sid, 2);
        assertEquals(2, emotions(sid), "夹具没种进去，后面的断言就都是空的");
        assertEquals(2, messages(sid));

        when(messageMapper.delete(any())).thenThrow(new IllegalStateException("模拟第二张表删除失败"));

        assertThrows(IllegalStateException.class, () -> service.clear(sid));

        assertEquals(2, emotions(sid),
                "clear() 带 @Transactional，第一张表的删除必须被回滚；这里是 0 就说明注解没生效或代理没套上");
    }

    @Test
    @DisplayName("正向对照腿：不抛异常时第一张表真的被删干净（防回滚腿测的是『本来就没删』）")
    void successfulClearReallyDeletesFirstTable() {
        String sid = "tx-commit";
        seed(sid, 3);
        assertEquals(3, emotions(sid));

        // mock 只报数不真删，所以 chat_message 留 3 行是预期；本腿要的证据在第一张表上。
        when(messageMapper.delete(any())).thenReturn(3);

        assertEquals(6, service.clear(sid), "返回值 = 真删的情绪行数 3 + mock 报的消息行数 3");
        assertEquals(0, emotions(sid), "第一张表必须被真删 —— 否则回滚腿的红不能归因于回滚");
        assertEquals(3, messages(sid));
    }
}
