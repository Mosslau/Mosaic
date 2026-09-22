// examples/ex04-completable-future-demo.java —— CompletableFuture 异步编排：并行汇合 + 串行转换 + 异常兜底
// 对应主文档 6. 示例 4：两个独立任务并行执行，thenCombine 汇合、thenApply 转换、exceptionally 兜底
// 验证环境：OpenJDK 17.0.18
// 编译：javac ex04-completable-future-demo.java
// 运行：java CompletableFutureDemo（注意是类名不是文件名）
// 验证状态：已验证：OpenJDK 17.0.18
import java.util.concurrent.*;

class CompletableFutureDemo {
    public static void main(String[] args) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(4);
        CompletableFuture<Integer> fetch = CompletableFuture.supplyAsync(() -> {
            sleep(100);                       // 模拟远程调用
            return 100;
        }, pool);
        CompletableFuture<Integer> compute = CompletableFuture.supplyAsync(() -> {
            sleep(150);                       // 模拟本地计算
            return 50;
        }, pool);
        CompletableFuture<String> result = fetch
                .thenCombine(compute, Integer::sum)   // 两个任务汇合：100 + 50 = 150
                .thenApply(total -> total * 2)        // 串行转换：150 * 2 = 300
                .exceptionally(ex -> {                // 异常兜底：任一步失败走这里，返回默认值
                    System.out.println("计算失败: " + ex.getMessage());
                    return -1;
                })
                .thenApply(v -> "最终结果: " + v);
        String finalValue = result.join();            // join() 阻塞取最终结果
        System.out.println(finalValue);
        pool.shutdown();
        if (!finalValue.equals("最终结果: 300")) {
            throw new AssertionError("编排结果不符: " + finalValue);
        }
        demoNoCatch();                                // 对照：链上不兜底时，异常被吞到取结果才暴露
        System.out.println("自检通过：编排结果 = 最终结果: 300");
    }

    /** 对照实验：supplyAsync 抛异常且链上无 exceptionally，异常不会立即炸出来，直到 join()/get() 才抛 */
    static void demoNoCatch() {
        CompletableFuture<Integer> bad = CompletableFuture.supplyAsync(() -> {
            throw new IllegalStateException("模拟失败");
        });
        try {
            bad.join();
            System.out.println("未捕获到异常（意外）");
        } catch (CompletionException e) {
            System.out.println("join() 抛出 CompletionException, cause = " + e.getCause().getMessage());
        }
    }

    static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
