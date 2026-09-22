package com.example;

import java.io.IOException;
import java.net.Socket;

/**
 * 测试基础设施：起一个临时 redis-server（独立端口 6399），全部测试结束后关闭。
 * 真实集成测试就该这么写——不测 mock 出来的 Redis，测真实服务。
 */
final class RedisServerHandle {

    static final int PORT = 6399;

    private final Process process;

    private RedisServerHandle(Process process) {
        this.process = process;
    }

    /** 启动 redis-server 并轮询等待端口就绪（最长 10 秒） */
    static RedisServerHandle start() throws IOException, InterruptedException {
        Process process = new ProcessBuilder(
                "redis-server",
                "--port", String.valueOf(PORT),
                "--save", "",            // 不落盘：临时测试实例
                "--appendonly", "no",
                "--daemonize", "no")
                .redirectErrorStream(true)
                .start();
        long deadline = System.currentTimeMillis() + 10_000;
        while (System.currentTimeMillis() < deadline) {
            try (Socket s = new Socket("127.0.0.1", PORT)) {
                return new RedisServerHandle(process);   // 端口可连即就绪
            } catch (IOException refused) {
                if (!process.isAlive()) {
                    throw new IOException("redis-server 启动失败，退出码 "
                            + process.exitValue() + "（请确认已安装 redis-server）");
                }
                Thread.sleep(100);
            }
        }
        process.destroyForcibly();
        throw new IOException("等待 redis-server 就绪超时");
    }

    void stop() {
        process.destroy();   // 优雅退出；JVM 退出时子进程由 destroyForcibly 兜底（见测试类 shutdown hook）
    }
}
