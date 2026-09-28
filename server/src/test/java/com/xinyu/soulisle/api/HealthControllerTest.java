package com.xinyu.soulisle.api;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * {@code GET /api/health} 判据守卫（r76；r75 实测本类目标 0% 覆盖）。
 *
 * <p>这个接口存在的理由就是「不许出现『服务起来了但页面其实是空目录』的假通过」，
 * 所以它必须回传解析后的绝对路径与两个命中位。AC-OBS-07 此前只在带外判据里验过，
 * 这里补编译级的一锁：<b>index 缺失必须降级成 DEGRADED，且 vendorFound 独立可判</b>
 * ——两半各管一件事，合并成一个布尔就回到了假通过。
 */
class HealthControllerTest {

    @Test
    @DisplayName("webRoot 命中 index.html 与 vendor/ 时判 UP，并回传解析后的绝对路径")
    void upWhenSourcesPresent(@TempDir Path web) throws Exception {
        Files.writeString(web.resolve("index.html"), "<html>心屿</html>");
        Files.createDirectory(web.resolve("vendor"));
        Map<String, Object> body = new HealthController(web.toString(), "J5").health();

        assertEquals("UP", body.get("status"));
        assertEquals("xinyu-soulisle", body.get("service"));
        assertEquals("J5", body.get("stage"));
        assertEquals(Boolean.TRUE, body.get("indexFound"));
        assertEquals(Boolean.TRUE, body.get("vendorFound"));
        Path reported = Path.of(String.valueOf(body.get("webRoot")));
        assertTrue(reported.isAbsolute(), "回传必须是解析后的绝对路径，否则换个工作目录就看不出一线之差");
        assertTrue(body.get("java").toString().length() > 0);
        assertTrue(body.get("ts").toString().startsWith("20"), "时间戳缺失会让两次读数无法区分");
    }

    @Test
    @DisplayName("index 缺失 ⇒ DEGRADED；vendor 缺失单独可见，不被 index 的结论掩盖")
    void degradedWhenIndexMissing(@TempDir Path web) throws Exception {
        Files.createDirectory(web.resolve("vendor"));
        Map<String, Object> noIndex = new HealthController(web.toString(), "J5").health();
        assertEquals("DEGRADED", noIndex.get("status"));
        assertEquals(Boolean.FALSE, noIndex.get("indexFound"));
        assertEquals(Boolean.TRUE, noIndex.get("vendorFound"), "两半独立判定，否则合并布尔=假通过");

        Map<String, Object> empty = new HealthController(web.resolve("nope").toString(), "J5").health();
        assertEquals("DEGRADED", empty.get("status"));
        assertFalse((Boolean) empty.get("vendorFound"));
        assertFalse((Boolean) empty.get("indexFound"));
    }
}
