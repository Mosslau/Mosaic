package com.example;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/** 手写 RESP 客户端实测：对真实 redis-server 做 SET/GET/DEL/EXPIRE/TTL */
class RespClientTest {

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
    @DisplayName("PING/SET/GET/DEL：协议往返全对，DEL 返回删除条数")
    void setGetDel_roundTrip() throws IOException {
        try (RespClient redis = new RespClient("127.0.0.1", RedisServerHandle.PORT)) {
            assertEquals("PONG", redis.ping());
            assertEquals("OK", redis.set("greeting", "你好 Redis"));
            assertEquals("你好 Redis", redis.get("greeting"));
            assertEquals(1, redis.del("greeting"));
            assertNull(redis.get("greeting"), "删除后 GET 应返回 nil（RESP $-1）");
            assertEquals(0, redis.del("greeting"), "重复删除返回 0");
        }
    }

    @Test
    @DisplayName("EXPIRE/TTL：过期语义是「懒过期 + 主动过期」，TTL 给出剩余秒数")
    void expireAndTtl() throws IOException {
        try (RespClient redis = new RespClient("127.0.0.1", RedisServerHandle.PORT)) {
            redis.set("session:u1", "token-abc");
            assertEquals(-1, redis.ttl("session:u1"), "无过期的键 TTL 为 -1");
            assertEquals(1, redis.expire("session:u1", 60));
            long ttl = redis.ttl("session:u1");
            assertTrue(ttl > 0 && ttl <= 60, "TTL 应在 (0, 60] 区间，实测 " + ttl);
            assertEquals(-2, redis.ttl("no-such-key"), "不存在的键 TTL 为 -2");
            redis.del("session:u1");
        }
    }
}
