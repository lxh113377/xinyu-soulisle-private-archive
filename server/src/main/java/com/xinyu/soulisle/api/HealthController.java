package com.xinyu.soulisle.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.CodeSource;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 健康检查：证明「Java 服务端 + 前端权威源」这条链路真的通了。
 *
 * <p>判据设计原则（本项目硬要求：结论可复核）——不返回笼统的 UP，
 * 而是把解析后的静态目录绝对路径与 index.html / vendor 是否命中一并回传，
 * 免得出现「服务起来了但页面其实是空目录」的假通过。
 */
@RestController
public class HealthController {

    private final String webRoot;
    private final String stage;

    public HealthController(@Value("${xinyu.web-root}") String webRoot,
                            @Value("${xinyu.stage}") String stage) {
        this.webRoot = webRoot;
        this.stage = stage;
    }

    @GetMapping("/api/health")
    public Map<String, Object> health() {
        Path root = Path.of(webRoot).toAbsolutePath().normalize();
        boolean indexFound = Files.isRegularFile(root.resolve("index.html"));
        boolean vendorFound = Files.isDirectory(root.resolve("vendor"));

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("status", indexFound ? "UP" : "DEGRADED");
        body.put("service", "xinyu-soulisle");
        body.put("stage", stage);
        body.put("java", System.getProperty("java.version"));
        body.put("webRoot", root.toString());
        body.put("indexFound", indexFound);
        body.put("vendorFound", vendorFound);
        body.put("build", buildIdentity());
        body.put("ts", Instant.now().toString());
        return body;
    }

    /** 只算一次：健康端点会被性能判据高频打，每次重算 20MB 的摘要会把自己变成被测噪声。 */
    private static volatile String buildId;

    /**
     * **产物身份**：回答「这个实例跑的到底是哪一份产物」。
     *
     * <p>为什么要有这一格（r131）：r128 与本轮 r130 都栽在同一个坑上 ——
     * 8123 上跑的是他人旧 jar，而健康自证回传的 {@code service/stage/java/webRoot}
     * 在新旧产物上**逐字相同**，于是「旧产物没有新路由」这件事在指纹上完全看不出来，
     * 只能靠「某个端点超时/404」去猜。更糟的一次是 `mvn package` 被文件锁打断后
     * 留下了 93,975 B 的瘦 jar 冒充 20 MB fat jar —— 那时连"大小"都对不上却没人发现。
     *
     * <p>形态：{@code jar:soulisle-server.jar:<摘要前12>:<字节数>} 或
     * {@code classes:<目录名>:<摘要前12>}（{@code spring-boot:run} 直跑 classes 时）。
     * 摘要只取**前 64 KiB**（够区分瘦/fat 且几乎无开销），取不到返回 {@code unknown}。
     */
    static String buildIdentity() {
        String cached = buildId;
        if (cached != null) {
            return cached;
        }
        CodeSource cs;
        try {
            cs = HealthController.class.getProtectionDomain().getCodeSource();
        } catch (Exception e) {
            cs = null;
        }
        String v = describe(cs);
        buildId = v;
        return v;
    }

    /**
     * 纯逻辑版（可测）：给一个 {@link CodeSource}，回产物身份串。
     *
     * <p>拆出来是为了覆盖：整段塞进 {@code buildIdentity()} 时，{@code cs == null}、
     * 路径不存在、摘要抛异常这几支在构建期**根本走不到**（本类的 CodeSource 永远非空），
     * 于是覆盖率被拖到门槛边上（r131 实测 BRANCH 90.07%，距门 0.90 只剩 0.07 点余量）。
     * 给了 seam 之后这几支都能直接喂进去判。
     */
    static String describe(CodeSource cs) {
        try {
            if (cs == null || cs.getLocation() == null) {
                return "unknown";
            }
            Path p = Path.of(cs.getLocation().toURI());
            if (Files.isRegularFile(p)) {
                // 只读前 64 KiB：整包读进来会白白吃掉 20MB 堆，且摘要本就只需要区分瘦/fat
                byte[] head;
                try (java.io.InputStream in = Files.newInputStream(p)) {
                    head = in.readNBytes(65536);
                }
                String sha = HexFormat.of().formatHex(
                        MessageDigest.getInstance("SHA-256").digest(head)).substring(0, 12);
                return "jar:" + p.getFileName() + ":" + sha + ":" + Files.size(p);
            }
            if (Files.isDirectory(p)) {
                return "classes:" + p.getFileName() + ":" + Files.getLastModifiedTime(p).toMillis();
            }
            return "unknown";
        } catch (Exception e) {
            return "unknown";
        }
    }
}
