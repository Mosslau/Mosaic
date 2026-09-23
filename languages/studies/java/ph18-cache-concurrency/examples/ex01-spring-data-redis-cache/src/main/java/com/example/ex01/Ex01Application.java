// examples/ex01-spring-data-redis-cache/src/main/java/com/example/ex01/Ex01Application.java
// Redis 数据结构与缓存用法演示（对应主文档 3.1/3.3/3.4）：
//   String + TTL（缓存）→ Hash（对象/状态）→ List（队列）→ Set（去重）→ ZSet（排行）
//   → 缓存读写姿势（Cache-Aside）→ SETNX 拿锁（3.4 语义）→ Lua 原子扣库存（3.3 原子性）
// 验证环境：OpenJDK 17 + Spring Boot 3.3.0 + spring-boot-starter-data-redis（Lettuce）
// 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run
//          （联网环境去掉 -o；前置：examples/ 下 docker compose up -d redis）
// 验证状态：未在本环境验证（需本地 Redis 服务）

package com.example.ex01;

import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

/** 启动类：跑完演示即退出（Redis 键统一前缀 ex01: 便于清理） */
@SpringBootApplication
public class Ex01Application implements CommandLineRunner {

    private final StringRedisTemplate redis;
    private final RedisCacheService cacheService;

    public Ex01Application(StringRedisTemplate redis, RedisCacheService cacheService) {
        this.redis = redis;
        this.cacheService = cacheService;
    }

    public static void main(String[] args) {
        SpringApplication.run(Ex01Application.class, args);
    }

    @Override
    public void run(String... args) {
        // 1. String：缓存读写的起点 —— SET key val EX ttl / GET
        redis.opsForValue().set("ex01:user:1:name", "alice", Duration.ofSeconds(60));
        System.out.println("1. String GET -> " + redis.opsForValue().get("ex01:user:1:name"));
        System.out.println("   TTL(剩余秒) -> " + redis.getExpire("ex01:user:1:name", TimeUnit.SECONDS));

        // 2. Hash：一个对象多个字段（比把整个 JSON 塞 String 更省流量、可改单个字段）
        redis.opsForHash().put("ex01:device:sn001", "status", "ONLINE");
        redis.opsForHash().put("ex01:device:sn001", "speed", "42");
        Map<Object, Object> device = redis.opsForHash().entries("ex01:device:sn001");
        System.out.println("2. Hash device -> " + device);

        // 3. List：右侧入队左侧消费 = 简单队列（ph17 消息队列的单机形态）
        redis.opsForList().rightPush("ex01:queue:task", "t1");
        redis.opsForList().rightPush("ex01:queue:task", "t2");
        System.out.println("3. List 队列弹出 -> " + redis.opsForList().leftPop("ex01:queue:task"));

        // 4. Set：去重（重复请求/签到等）
        redis.opsForSet().add("ex01:dedup:order-1001", "consumer-a");
        boolean dup = Boolean.TRUE.equals(redis.opsForSet().isMember("ex01:dedup:order-1001", "consumer-a"));
        System.out.println("4. Set 去重 isMember(重复消费?) -> " + dup);

        // 5. ZSet：按分数排序（排行榜/定时轮询游标）
        redis.opsForZSet().add("ex01:rank", "sn001", 88);
        redis.opsForZSet().add("ex01:rank", "sn002", 95);
        System.out.println("5. ZSet 前 2 名 -> " + redis.opsForZSet().reverseRange("ex01:rank", 0, 1));

        // 6. Cache-Aside 读写姿势：读缓存，miss 再查数据源并回填（对应主文档 3.1/3.3 的缓存套路）
        String name = cacheService.getOrLoad("ex01:user:2:name", Duration.ofSeconds(30), () -> "load-from-db:bob");
        System.out.println("6. Cache-Aside 读 -> " + name + "（再读同 key 应命中缓存，数据源不再执行）");

        // 7. 分布式锁的最小形态：SETNX + TTL（完整语义见主文档 3.4 与 examples/ex04）
        String lockKey = "ex01:lock:order-1001";
        boolean acquired = Boolean.TRUE.equals(
                redis.opsForValue().setIfAbsent(lockKey, "instance-a", Duration.ofSeconds(10)));
        System.out.println("7. 分布式锁 tryLock -> " + acquired + "（SET key val NX EX 10）");
        // 释放：Lua 校验 value 再删（不是裸 DEL，否则会删掉别人的锁）
        DefaultRedisScript<Long> releaseScript = new DefaultRedisScript<>(
                "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                Long.class);
        Long released = redis.execute(releaseScript, List.of(lockKey), "instance-a");
        System.out.println("   释放锁（Lua compare-and-del）-> " + (released != null && released == 1L));

        // 8. Lua 原子扣库存：扣减与检查在服务端一条龙执行（超卖防线，主文档 3.3/5 章；对应练习 3 与 project）
        String stockKey = "ex01:stock:sku1001";
        redis.opsForValue().set(stockKey, "3");
        DefaultRedisScript<Long> deductScript = new DefaultRedisScript<>(
                "local stock = tonumber(redis.call('GET', KEYS[1]) or '0')\n"
                        + "if stock >= tonumber(ARGV[1]) then\n"
                        + "  redis.call('DECRBY', KEYS[1], ARGV[1])\n"
                        + "  return 1\n"
                        + "end\n"
                        + "return 0",
                Long.class);
        System.out.println("8. Lua 扣库存 2 -> " + redis.execute(deductScript, List.of(stockKey), "2")
                + "（库存剩余 " + redis.opsForValue().get(stockKey) + "）");
        System.out.println("   再扣 2 -> " + redis.execute(deductScript, List.of(stockKey), "2")
                + "（库存不足，返回 0 不扣 —— 原子性由 Redis 单线程执行 Lua 保证）");

        // 清理演示键（学习场景别污染本地 Redis）
        redis.delete(List.of("ex01:user:1:name", "ex01:device:sn001", "ex01:queue:task",
                "ex01:dedup:order-1001", "ex01:rank", "ex01:user:2:name", stockKey));
        System.out.println("演示结束。对照主文档 3.1：五种结构的选型表 + 缓存读写姿势；");
        System.out.println("7/8 对应 3.4 分布式锁与 3.3 的原子扣减（Lua 是 Redis 原子性的事实标准）。");
    }

    /** 数据源回填只演示一次：第二次读同 key 应命中缓存、不触发 loader（验证在输出日志里看 load 标记） */
    @org.springframework.stereotype.Component
    static class RedisCacheService {
        private final StringRedisTemplate redis;

        RedisCacheService(StringRedisTemplate redis) {
            this.redis = redis;
        }

        /** Cache-Aside：先查缓存，miss 则由 loader 回源并写回（TTL 防缓存雪崩要加抖动，见主文档 3.3） */
        String getOrLoad(String key, Duration ttl, Supplier<String> loader) {
            String cached = redis.opsForValue().get(key);
            if (cached != null) {
                return cached;
            }
            String value = loader.get();           // 真实系统 = 查 DB / 调下游
            if (value != null) {
                redis.opsForValue().set(key, value, ttl);
            }
            return value;
        }
    }
}
