package com.example;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;

/**
 * 测试用 redis-server 拉起/关闭工具：随机端口起真实 Redis（不写盘、目录放系统临时区）。
 * 找不到 redis-server 二进制时返回 null，测试用 Assumptions 整组跳过并如实标注「未在本环境验证」。
 */
final class RedisServerSupport {

    private RedisServerSupport() {
    }

    static Process start(int port) throws IOException, InterruptedException {
        String binary = findRedisServer();
        if (binary == null) {
            return null;
        }
        Path workDir = Files.createTempDirectory("ph16-redis-test");
        Process process = new ProcessBuilder(binary,
                "--port", String.valueOf(port),
                "--save", "",                 // 不写 RDB
                "--appendonly", "no",         // 不写 AOF
                "--dir", workDir.toString())
                .redirectErrorStream(true)
                .redirectOutput(ProcessBuilder.Redirect.DISCARD)
                .start();
        waitUntilReady(port, Duration.ofSeconds(10));
        return process;
    }

    private static String findRedisServer() {
        String env = System.getenv("REDIS_SERVER_BIN");
        if (env != null && Files.isExecutable(Path.of(env))) {
            return env;
        }
        Path homebrew = Path.of("/opt/homebrew/bin/redis-server");
        if (Files.isExecutable(homebrew)) {
            return homebrew.toString();
        }
        try {
            Process which = new ProcessBuilder("which", "redis-server").start();
            String path = new String(which.getInputStream().readAllBytes()).trim();
            if (which.waitFor() == 0 && !path.isBlank()) {
                return path;
            }
        } catch (IOException | InterruptedException ignored) {
            // 找不到就返回 null，由测试决定跳过
        }
        return null;
    }

    private static void waitUntilReady(int port, Duration timeout) throws InterruptedException {
        long deadline = System.nanoTime() + timeout.toNanos();
        while (System.nanoTime() < deadline) {
            try (Socket socket = new Socket()) {
                socket.connect(new InetSocketAddress("127.0.0.1", port), 200);
                return;
            } catch (IOException notReady) {
                Thread.sleep(50);
            }
        }
        throw new IllegalStateException("redis-server 端口 " + port + " 等待就绪超时");
    }
}
