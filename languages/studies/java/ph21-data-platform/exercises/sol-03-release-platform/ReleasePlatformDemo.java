// exercises/sol-03-ota-platform/ReleasePlatformDemo.java —— 版本发布升级平台验收演示
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//   然后 java -cp /tmp/tl21-sol ReleasePlatformDemo
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class ReleasePlatformDemo {
    public static void main(String[] args) throws InterruptedException {
        ReleasePlatform platform = new ReleasePlatform();
        List<String> nodes = List.of("LSV0000001", "LSV0000002", "LSV0000003", "LSV0000004");

        AtomicInteger pass = new AtomicInteger();
        platform.publish("1.4.0");
        platform.publish("2.0.0");
        check(pass, platform.highestVersion().toString().equals("2.0.0"), "发布 1.4.0 / 2.0.0，最高版本 2.0.0");
        check(pass, versionDowngradeRejected(platform), "版本倒退(再发 1.5.0)被平台拒绝");

        // 批次 A：3 个数据源升 2.0.0
        ReleasePlatform.Batch batchA = platform.createBatch("版本发布-A", "2.0.0", nodes.subList(0, 3));
        check(pass, platform.batchIds().contains("版本发布-A"), "批次 版本发布-A 创建成功");
        check(pass, batchA.summary().byState().get(ReleasePlatform.TaskState.PENDING) == 3L,
                "批次 A 初始 3 台 PENDING");

        // 并发推进：两个批次线程各推自己的g(验证批次隔离)
        ReleasePlatform.Batch batchB = platform.createBatch("版本发布-B", "2.0.0", List.of("LSV0000004"));
        Thread ta = new Thread(() -> {
            for (String sourceId : nodes.subList(0, 3)) {
                batchA.advance(sourceId, ReleasePlatform.TaskState.PENDING, ReleasePlatform.TaskState.DOWNLOADING);
            }
        });
        Thread tb = new Thread(() -> batchB.advance("LSV0000004",
                ReleasePlatform.TaskState.PENDING, ReleasePlatform.TaskState.DOWNLOADING));
        ta.start();
        tb.start();
        ta.join();
        tb.join();
        check(pass, batchA.summary().byState().get(ReleasePlatform.TaskState.DOWNLOADING) == 3L
                        && batchB.summary().byState().get(ReleasePlatform.TaskState.DOWNLOADING) == 1L,
                "两批次并发推进互不干扰(A=3,B=1)");

        // 安装：A 中 2 台成功 1 台失败；B 成功
        batchA.advance("LSV0000001", ReleasePlatform.TaskState.DOWNLOADING, ReleasePlatform.TaskState.INSTALLING);
        batchA.advance("LSV0000001", ReleasePlatform.TaskState.INSTALLING, ReleasePlatform.TaskState.SUCCEEDED);
        batchA.advance("LSV0000002", ReleasePlatform.TaskState.DOWNLOADING, ReleasePlatform.TaskState.INSTALLING);
        batchA.advance("LSV0000002", ReleasePlatform.TaskState.INSTALLING, ReleasePlatform.TaskState.FAILED);
        batchA.advance("LSV0000003", ReleasePlatform.TaskState.DOWNLOADING, ReleasePlatform.TaskState.INSTALLING);
        batchA.advance("LSV0000003", ReleasePlatform.TaskState.INSTALLING, ReleasePlatform.TaskState.SUCCEEDED);
        batchB.advance("LSV0000004", ReleasePlatform.TaskState.DOWNLOADING, ReleasePlatform.TaskState.INSTALLING);
        batchB.advance("LSV0000004", ReleasePlatform.TaskState.INSTALLING, ReleasePlatform.TaskState.SUCCEEDED);

        check(pass, batchA.summary().byState().get(ReleasePlatform.TaskState.SUCCEEDED) == 2L
                        && batchA.summary().byState().get(ReleasePlatform.TaskState.FAILED) == 1L,
                "批次 A 汇总：2 成功 1 失败");
        check(pass, batchA.auditLog().size() >= 7 && batchA.auditLog().contains(
                "LSV0000002 INSTALLING->FAILED batch=版本发布-A"),
                "数据源级审计作业历史完整且含失败记录");

        // 对失败数据源做回滚落点(生产上回滚到 1.4.0 是单独一轮 版本发布任务)
        batchA.advance("LSV0000002", ReleasePlatform.TaskState.FAILED, ReleasePlatform.TaskState.ROLLED_BACK);
        check(pass, batchA.summary().byState().get(ReleasePlatform.TaskState.ROLLED_BACK) == 1L,
                "失败数据源进入 ROLLED_BACK(等待回滚任务)");

        System.out.println("批次 A 汇总: " + batchA.summary().byState());
        System.out.printf("ALL PASS: %d/8%n", pass.get());
    }

    private static boolean versionDowngradeRejected(ReleasePlatform p) {
        try {
            p.publish("1.5.0");      // 低于当前最高 2.0.0
            return false;
        } catch (IllegalArgumentException e) {
            return true;
        }
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) { pass.incrementAndGet(); }
    }
}
