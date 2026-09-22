package com.example;

import com.example.lock.RedisDistributedLock;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.io.IOException;
import java.net.ServerSocket;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

/**
 * 真实 Redis（本机 redis-server 8.6.2，随机端口，ProcessBuilder 拉起）上的分布式锁语义实测。
 * 无 redis-server 二进制的环境整组跳过（Assumptions），不伪造结果。
 */
class DistributedLockTest {

    private static Process redisProcess;
    private static StringRedisTemplate redis;
    private static RedisDistributedLock lock;

    @BeforeAll
    static void startRedis() throws Exception {
        int port = freePort();
        redisProcess = RedisServerSupport.start(port);
        assumeTrue(redisProcess != null, "未找到 redis-server 二进制，跳过（未在本环境验证）");
        LettuceConnectionFactory factory = new LettuceConnectionFactory("127.0.0.1", port);
        factory.afterPropertiesSet();
        redis = new StringRedisTemplate(factory);
        lock = new RedisDistributedLock(redis);
    }

    @AfterAll
    static void stopRedis() {
        if (redisProcess != null) {
            redisProcess.destroy();
        }
    }

    private static int freePort() throws IOException {
        try (ServerSocket socket = new ServerSocket(0)) {
            return socket.getLocalPort();
        }
    }

    @Test
    void acquireAndRelease() {
        String key = "lock:basic";
        assertThat(lock.tryLock(key, "owner-1", Duration.ofSeconds(5))).isTrue();
        assertThat(lock.isLocked(key)).isTrue();
        assertThat(lock.unlock(key, "owner-1")).isTrue();
        assertThat(lock.isLocked(key)).isFalse();
    }

    @Test
    void secondHolderIsRejectedWhileLockHeld() {
        String key = "lock:mutex";
        assertThat(lock.tryLock(key, "owner-1", Duration.ofSeconds(5))).isTrue();
        assertThat(lock.tryLock(key, "owner-2", Duration.ofSeconds(5))).isFalse();  // 互斥
        lock.unlock(key, "owner-1");
        assertThat(lock.tryLock(key, "owner-2", Duration.ofSeconds(5))).isTrue();   // 释放后可得
        lock.unlock(key, "owner-2");
    }

    @Test
    void wrongTokenCannotUnlockOthersLock() {
        String key = "lock:token";
        assertThat(lock.tryLock(key, "owner-1", Duration.ofSeconds(2))).isTrue();
        assertThat(lock.unlock(key, "owner-2")).isFalse();   // 不是自己的锁，删不掉
        assertThat(lock.isLocked(key)).isTrue();
        assertThat(lock.unlock(key, "owner-1")).isTrue();
    }

    @Test
    void lockExpiresAfterTtlWhenHolderCrashes() throws InterruptedException {
        String key = "lock:ttl";
        // 持有者「宕机」：加锁后不解锁，锁必须在 TTL 后自动释放，否则永远死锁
        assertThat(lock.tryLock(key, "owner-crash", Duration.ofMillis(300))).isTrue();
        assertThat(lock.tryLock(key, "owner-next", Duration.ofSeconds(1))).isFalse();
        Thread.sleep(500);
        assertThat(lock.tryLock(key, "owner-next", Duration.ofSeconds(1))).isTrue();
        lock.unlock(key, "owner-next");
    }

    @Test
    void concurrentCompetitorsExactlyOneWins() throws Exception {
        String key = "lock:race";
        int threads = 12;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch gate = new CountDownLatch(1);
        AtomicInteger winners = new AtomicInteger();
        List<Future<Boolean>> futures = new ArrayList<>();
        for (int i = 0; i < threads; i++) {
            String token = "worker-" + i;
            Callable<Boolean> task = () -> {
                gate.await();
                boolean got = lock.tryLock(key, token, Duration.ofSeconds(5));
                if (got) {
                    winners.incrementAndGet();
                    Thread.sleep(30);          // 持锁干活
                    lock.unlock(key, token);
                }
                return got;
            };
            futures.add(pool.submit(task));
        }
        gate.countDown();
        int got = 0;
        for (Future<Boolean> f : futures) {
            if (f.get()) {
                got++;
            }
        }
        pool.shutdown();
        // 同一瞬间只有一个赢家（先抢到的一直持有 30ms，其余全部失败）
        assertThat(got).isEqualTo(1);
        assertThat(winners.get()).isEqualTo(1);
    }
}
