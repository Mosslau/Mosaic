package com.example;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import redis.clients.jedis.Jedis;

/** Jedis 实测：与手写 RESP 客户端做同一件事，对照「协议 vs 客户端库」 */
class JedisClientTest {

    private static RedisServerHandle server;

    @BeforeAll
    static void startRedis() throws IOException, InterruptedException {
        server = RedisServerHandle.start();
    }

    @AfterAll
    static void stopRedis() {
        server.stop();
    }

    @Test
    @DisplayName("Jedis set/get/del：库封装的就是 RESP 协议帧")
    void jedisBasicCommands() {
        try (Jedis jedis = new Jedis("127.0.0.1", RedisServerHandle.PORT)) {
            assertEquals("PONG", jedis.ping());
            assertEquals("OK", jedis.set("user:1:name", "mosslau"));
            assertEquals("mosslau", jedis.get("user:1:name"));
            assertEquals(1L, jedis.del("user:1:name"));
            assertNull(jedis.get("user:1:name"));
        }
    }

    @Test
    @DisplayName("缓存旁路（Cache-Aside）：读穿透时回源加载并回填缓存，这是缓存策略的基本型")
    void cacheAsidePattern() {
        // 模拟慢速数据源（真实工程里是 MySQL/PostgreSQL）
        Map<String, String> database = new HashMap<>();
        database.put("user:42", "{\"name\":\"mosslau\"}");

        try (Jedis jedis = new Jedis("127.0.0.1", RedisServerHandle.PORT)) {
            String key = "cache:user:42";
            jedis.del(key);

            // 第一次：缓存未命中 → 回源 → 回填缓存（带过期时间兜底）
            String first = cacheAsideGet(jedis, key, () -> database.get("user:42"));
            assertEquals("{\"name\":\"mosslau\"}", first);

            // 第二次：删掉「数据库」，缓存仍命中——证明读的是缓存不是库
            database.clear();
            String second = cacheAsideGet(jedis, key, () -> database.get("user:42"));
            assertEquals(first, second, "缓存命中时不再回源");

            jedis.del(key);
        }
    }

    /** 缓存旁路读：先查缓存，未命中回源并回填（设置 60 秒过期防止脏数据永生） */
    private static String cacheAsideGet(Jedis jedis, String key, java.util.function.Supplier<String> loader) {
        String cached = jedis.get(key);
        if (cached != null) {
            return cached;
        }
        String loaded = loader.get();
        if (loaded != null) {
            jedis.setex(key, 60, loaded);
        }
        return loaded;
    }
}
