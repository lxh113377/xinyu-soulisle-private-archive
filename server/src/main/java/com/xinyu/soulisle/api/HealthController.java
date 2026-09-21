package com.xinyu.soulisle.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
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
        body.put("ts", Instant.now().toString());
        return body;
    }
}
