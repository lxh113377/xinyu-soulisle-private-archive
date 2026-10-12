package com.xinyu.soulisle.api;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.CodeSource;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
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

    @Test
    @DisplayName("回传产物身份 build —— service/stage/java 在新旧产物上逐字相同，只有它能区分")
    void reportsBuildIdentity() {
        Map<String, Object> body = new HealthController(".", "J5").health();
        Object build = body.get("build");
        assertNotNull(build, "缺这一格就分不清 8123 上跑的是哪份产物（r128、r130 两次栽在这）");
        String b = build.toString();
        assertNotEquals("unknown", b, "取不到产物身份 ⇒ 指纹又退回不可区分的老样子");
        assertTrue(b.startsWith("jar:") || b.startsWith("classes:"),
                "形态 = jar:<名>:<摘要12>:<字节数> 或 classes:<目录>:<mtime>，实际 = " + b);
        assertEquals(b, HealthController.buildIdentity(),
                "必须缓存：健康端点会被性能判据高频打，每次重算摘要会把自己变成被测噪声");
    }

    @Test
    @DisplayName("产物身份 describe()：jar / classes / null / 路径不存在 四态各自可判")
    void describesBuildSource(@TempDir Path tmp) throws Exception {
        // ① 文件（fat jar 的正常形态）：文件名 + 摘要 + 字节数都得到位，字节数是识别瘦 jar 的关键
        Path jar = tmp.resolve("soulisle-server.jar");
        Files.writeString(jar, "PKfake-jar");
        String fileId = HealthController.describe(new CodeSource(jar.toUri().toURL(), (java.security.cert.Certificate[]) null));
        assertTrue(fileId.startsWith("jar:soulisle-server.jar:"), fileId);
        assertTrue(fileId.endsWith(":" + Files.size(jar)), "字节数必须在串里——93,975B 的瘦 jar 就是靠它现形：" + fileId);

        // ② 目录（spring-boot:run 直跑 classes）
        Path dir = tmp.resolve("classes");
        Files.createDirectory(dir);
        String dirId = HealthController.describe(new CodeSource(dir.toUri().toURL(), (java.security.cert.Certificate[]) null));
        assertTrue(dirId.startsWith("classes:classes:"), dirId);

        // ③ null / ④ 路径不存在：都归 unknown，不许抛（健康端点抛栈会把"服务在"读成"服务挂了"）
        assertEquals("unknown", HealthController.describe(null));
        assertEquals("unknown", HealthController.describe(
                new CodeSource(tmp.resolve("no-such-artifact").toUri().toURL(), (java.security.cert.Certificate[]) null)));
    }
}
