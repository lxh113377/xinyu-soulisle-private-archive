package com.xinyu.soulisle.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.xinyu.soulisle.service.MemoryPortService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * r130：导出/导入两个端点的接线判据（服务层逻辑由 {@code MemoryPortServiceTest} 覆盖）。
 *
 * <p>这里只锁三件接线层的事：状态码映射、{@code sessionId} 缺失的 400、
 * 以及**坏 JSON 不得抛栈**（端点对匿名可达，抛栈等于把内部结构往外递）。
 */
class MemoryPortControllerTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static JsonNode read(ResponseEntity<byte[]> resp) throws Exception {
        return MAPPER.readTree(resp.getBody());
    }

    @Test
    @DisplayName("导出 200 且回传 schema")
    void exportReturnsSchema() throws Exception {
        MemoryPortService port = mock(MemoryPortService.class);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("schema", MemoryPortService.SCHEMA);
        when(port.exportSession(anyString(), anyInt())).thenReturn(body);

        ResponseEntity<byte[]> resp = new MemoryPortController(port).exportMemory("s1", 500);

        assertEquals(200, resp.getStatusCode().value());
        assertEquals(MemoryPortService.SCHEMA, read(resp).get("schema").asText());
    }

    @Test
    @DisplayName("导出缺 sessionId ⇒ 400（不给匿名端点开全量下载）")
    void exportWithoutSessionIsBadRequest() throws Exception {
        MemoryPortService port = mock(MemoryPortService.class);
        when(port.exportSession(any(), anyInt())).thenReturn(null);

        ResponseEntity<byte[]> resp = new MemoryPortController(port).exportMemory(null, 500);

        assertEquals(400, resp.getStatusCode().value());
        assertEquals("bad-json", read(resp).get("error").asText());
    }

    @Test
    @DisplayName("导入成功 200；服务层报结构性错误则 400")
    void importStatusFollowsService() throws Exception {
        MemoryPortService port = mock(MemoryPortService.class);
        Map<String, Object> ok = new LinkedHashMap<>();
        ok.put("ok", true);
        ok.put("inserted", 1);
        when(port.importPayload(any())).thenReturn(ok);
        assertEquals(200, new MemoryPortController(port).importMemory("{}").getStatusCode().value());

        Map<String, Object> bad = new LinkedHashMap<>();
        bad.put("error", "schema-mismatch");
        when(port.importPayload(any())).thenReturn(bad);
        ResponseEntity<byte[]> resp = new MemoryPortController(port).importMemory("{}");
        assertEquals(400, resp.getStatusCode().value());
        assertEquals("schema-mismatch", read(resp).get("error").asText());
    }

    @Test
    @DisplayName("坏 JSON 不抛栈：非对象/空串/截断串都落到 400")
    void malformedBodyNeverThrows() throws Exception {
        MemoryPortService port = mock(MemoryPortService.class);
        Map<String, Object> bad = new LinkedHashMap<>();
        bad.put("error", "bad-json");
        when(port.importPayload(any())).thenReturn(bad);
        MemoryPortController c = new MemoryPortController(port);

        for (String raw : new String[]{null, "", "not-json", "[1,2]", "{\"a\":", "\"just-a-string\""}) {
            ResponseEntity<byte[]> resp = c.importMemory(raw);
            assertEquals(400, resp.getStatusCode().value(), "入参 [" + raw + "] 不该抛栈");
            assertTrue(read(resp).has("error"));
        }
    }
}
