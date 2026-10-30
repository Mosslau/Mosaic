package com.ninebot.dataagent.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.springframework.data.domain.Range;
import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.StreamOperations;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * Java SSE 网关：轮询 Python 发布的 per-run Redis Stream，并转成浏览器 SSE。
 *
 * <p>生产环境应使用 Redis Consumer Group、消费位点表和断线恢复策略；本实现先完成
 * 单 Run 调试链路，事件本身仍由 Redis Stream 作为事实来源。</p>
 */
@Service
public class RedisEventSseService {
    private final StringRedisTemplate redis;
    private final ObjectMapper mapper;
    private final ExecutorService executor = Executors.newCachedThreadPool();

    public RedisEventSseService(StringRedisTemplate redis, ObjectMapper mapper) {
        this.redis = redis;
        this.mapper = mapper;
    }

    public SseEmitter open(String runId, String lastEventId) {
        SseEmitter emitter = new SseEmitter(TimeUnit.MINUTES.toMillis(30));
        executor.submit(() -> poll(runId, lastEventId == null ? "0-0" : lastEventId, emitter));
        return emitter;
    }

    private void poll(String runId, String cursor, SseEmitter emitter) {
        String stream = "agent:run:" + runId + ":events";
        try {
            boolean terminal = false;
            for (int round = 0; round < 3600 && !terminal; round++) {
                List<MapRecord<String, String, String>> records = streamOps().range(stream, Range.unbounded());
                for (MapRecord<String, String, String> record : records) {
                    String id = record.getId().getValue();
                    if (compareIds(id, cursor) <= 0) continue;
                    String raw = record.getValue().get("event");
                    JsonNode event = raw == null ? mapper.valueToTree(record.getValue()) : mapper.readTree(String.valueOf(raw));
                    emitter.send(SseEmitter.event().id(id).name("agent_event").data(event));
                    cursor = id;
                    String eventType = event.path("event_type").asText();
                    terminal = eventType.equals("run_completed") || eventType.equals("run_failed")
                            || eventType.equals("run_cancelled");
                    if (terminal) break;
                }
                if (terminal) {
                    emitter.complete();
                    return;
                }
                Thread.sleep(500);
            }
            emitter.complete();
        } catch (Exception ex) {
            try {
                emitter.send(SseEmitter.event().name("error").data(Map.of("code", "SSE_STREAM_ERROR", "message", ex.getMessage())));
            } catch (Exception ignored) {
                // 客户端断开时不再重复写入。
            }
            emitter.completeWithError(ex);
        }
    }

    private StreamOperations<String, String, String> streamOps() { return redis.opsForStream(); }

    private static int compareIds(String left, String right) {
        long[] a = parseId(left), b = parseId(right);
        return a[0] == b[0] ? Long.compare(a[1], b[1]) : Long.compare(a[0], b[0]);
    }

    private static long[] parseId(String value) {
        String[] parts = value.split("-", 2);
        return new long[]{Long.parseLong(parts[0]), parts.length == 1 ? 0 : Long.parseLong(parts[1])};
    }
}
