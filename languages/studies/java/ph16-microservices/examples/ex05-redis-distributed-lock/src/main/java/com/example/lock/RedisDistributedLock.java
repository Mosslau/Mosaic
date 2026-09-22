package com.example.lock;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;

import java.time.Duration;
import java.util.List;

/**
 * Redis 分布式锁的最小正确实现（生产用 Redisson，其看门狗机制见主文档 3.4；本类演示底层语义）：
 * - 加锁：SET key token NX PX ttl —— 一条原子命令同时完成「占位 + 过期时间」，杜绝「占位后宕机永不释放」
 * - token 是持有者唯一标识：只能解自己的锁（防止误删他人锁）
 * - 解锁：Lua 脚本「比对 token 再删」原子执行 —— 先 GET 后 DEL 两条命令之间有窗口，会误删
 */
public class RedisDistributedLock {

    private static final DefaultRedisScript<Long> UNLOCK_SCRIPT = new DefaultRedisScript<>(
            "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
            Long.class);

    private final StringRedisTemplate redis;

    public RedisDistributedLock(StringRedisTemplate redis) {
        this.redis = redis;
    }

    /** 尝试加锁（非阻塞）：拿到返回 true，被占返回 false */
    public boolean tryLock(String key, String token, Duration ttl) {
        Boolean acquired = redis.opsForValue().setIfAbsent(key, token, ttl);
        return Boolean.TRUE.equals(acquired);
    }

    /** 解锁：仅当锁是自己的才删（Lua 原子比对+删除） */
    public boolean unlock(String key, String token) {
        Long result = redis.execute(UNLOCK_SCRIPT, List.of(key), token);
        return Long.valueOf(1L).equals(result);
    }

    /** 锁当前是否被占用（观测用） */
    public boolean isLocked(String key) {
        return Boolean.TRUE.equals(redis.hasKey(key));
    }
}
