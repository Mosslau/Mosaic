// exercises/sol-03-ota-platform/OtaPlatformDemo.java —— OTA 升级平台验收演示
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//   然后 java -cp /tmp/tl21-sol OtaPlatformDemo
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class OtaPlatformDemo {
    public static void main(String[] args) throws InterruptedException {
        OtaPlatform platform = new OtaPlatform();
        List<String> fleet = List.of("LSV0000001", "LSV0000002", "LSV0000003", "LSV0000004");

        AtomicInteger pass = new AtomicInteger();
        platform.publish("1.4.0");
        platform.publish("2.0.0");
        check(pass, platform.highestVersion().toString().equals("2.0.0"), "发布 1.4.0 / 2.0.0，最高版本 2.0.0");
        check(pass, versionDowngradeRejected(platform), "版本倒退(再发 1.5.0)被平台拒绝");

        // 批次 A：3 台车升 2.0.0
        OtaPlatform.Batch batchA = platform.createBatch("OTA-A", "2.0.0", fleet.subList(0, 3));
        check(pass, platform.batchIds().contains("OTA-A"), "批次 OTA-A 创建成功");
        check(pass, batchA.summary().byState().get(OtaPlatform.TaskState.PENDING) == 3L,
                "批次 A 初始 3 台 PENDING");

        // 并发推进：两个批次线程各推自己的车(验证批次隔离)
        OtaPlatform.Batch batchB = platform.createBatch("OTA-B", "2.0.0", List.of("LSV0000004"));
        Thread ta = new Thread(() -> {
            for (String vin : fleet.subList(0, 3)) {
                batchA.advance(vin, OtaPlatform.TaskState.PENDING, OtaPlatform.TaskState.DOWNLOADING);
            }
        });
        Thread tb = new Thread(() -> batchB.advance("LSV0000004",
                OtaPlatform.TaskState.PENDING, OtaPlatform.TaskState.DOWNLOADING));
        ta.start();
        tb.start();
        ta.join();
        tb.join();
        check(pass, batchA.summary().byState().get(OtaPlatform.TaskState.DOWNLOADING) == 3L
                        && batchB.summary().byState().get(OtaPlatform.TaskState.DOWNLOADING) == 1L,
                "两批次并发推进互不干扰(A=3,B=1)");

        // 安装：A 中 2 台成功 1 台失败；B 成功
        batchA.advance("LSV0000001", OtaPlatform.TaskState.DOWNLOADING, OtaPlatform.TaskState.INSTALLING);
        batchA.advance("LSV0000001", OtaPlatform.TaskState.INSTALLING, OtaPlatform.TaskState.SUCCEEDED);
        batchA.advance("LSV0000002", OtaPlatform.TaskState.DOWNLOADING, OtaPlatform.TaskState.INSTALLING);
        batchA.advance("LSV0000002", OtaPlatform.TaskState.INSTALLING, OtaPlatform.TaskState.FAILED);
        batchA.advance("LSV0000003", OtaPlatform.TaskState.DOWNLOADING, OtaPlatform.TaskState.INSTALLING);
        batchA.advance("LSV0000003", OtaPlatform.TaskState.INSTALLING, OtaPlatform.TaskState.SUCCEEDED);
        batchB.advance("LSV0000004", OtaPlatform.TaskState.DOWNLOADING, OtaPlatform.TaskState.INSTALLING);
        batchB.advance("LSV0000004", OtaPlatform.TaskState.INSTALLING, OtaPlatform.TaskState.SUCCEEDED);

        check(pass, batchA.summary().byState().get(OtaPlatform.TaskState.SUCCEEDED) == 2L
                        && batchA.summary().byState().get(OtaPlatform.TaskState.FAILED) == 1L,
                "批次 A 汇总：2 成功 1 失败");
        check(pass, batchA.auditLog().size() >= 7 && batchA.auditLog().contains(
                "LSV0000002 INSTALLING->FAILED batch=OTA-A"),
                "车级审计轨迹完整且含失败记录");

        // 对失败车做回滚落点(生产上回滚到 1.4.0 是单独一轮 OTA 任务)
        batchA.advance("LSV0000002", OtaPlatform.TaskState.FAILED, OtaPlatform.TaskState.ROLLED_BACK);
        check(pass, batchA.summary().byState().get(OtaPlatform.TaskState.ROLLED_BACK) == 1L,
                "失败车进入 ROLLED_BACK(等待回滚任务)");

        System.out.println("批次 A 汇总: " + batchA.summary().byState());
        System.out.printf("ALL PASS: %d/8%n", pass.get());
    }

    private static boolean versionDowngradeRejected(OtaPlatform p) {
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
