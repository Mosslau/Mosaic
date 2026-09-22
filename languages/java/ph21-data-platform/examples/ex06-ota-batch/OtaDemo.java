// examples/ex06-ota-batch/OtaDemo.java —— OTA 批次演示主入口
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：
//   javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//   java -cp /tmp/tl21-cls OtaDemo
// 期望：5 台车批次推进，4 台成功 1 台失败；失败触发回滚把 4 台成功车打回 PENDING(待刷旧版)。
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class OtaDemo {
    public static void main(String[] args) {
        OtaVersion before = OtaVersion.of("1.4.0");
        OtaVersion target = OtaVersion.of("2.0.0");
        List<String> vins = List.of("LSV0000001", "LSV0000002", "LSV0000003", "LSV0000004", "LSV0000005");

        OtaBatch batch = new OtaBatch("OTA-2025-09-B", target, before, vins);

        // 5 台车各自走完 DOWNLOADING -> INSTALLING
        for (String vin : vins) {
            batch.advance(vin, OtaBatch.CarTaskStatus.PENDING, OtaBatch.CarTaskStatus.DOWNLOADING, "download-start");
            batch.advance(vin, OtaBatch.CarTaskStatus.DOWNLOADING, OtaBatch.CarTaskStatus.INSTALLING, "download-done");
        }
        // 安装：4 台成功、第 5 台失败(模拟刷写中断)
        for (int i = 0; i < 4; i++) {
            batch.advance(vins.get(i), OtaBatch.CarTaskStatus.INSTALLING,
                    OtaBatch.CarTaskStatus.SUCCEEDED, "install-ok");
        }
        batch.advance(vins.get(4), OtaBatch.CarTaskStatus.INSTALLING,
                OtaBatch.CarTaskStatus.FAILED, "install-eeprom-error");

        // 非法迁移必须被拒(已完成的车不能再被推回 INSTALLING)
        boolean rejected = false;
        try {
            batch.advance(vins.get(0), OtaBatch.CarTaskStatus.INSTALLING,
                    OtaBatch.CarTaskStatus.SUCCEEDED, "duplicate");
        } catch (IllegalStateException e) {
            rejected = true;
        }

        AtomicInteger pass = new AtomicInteger();
        check(pass, batch.count(OtaBatch.CarTaskStatus.SUCCEEDED) == 4, "4 台车安装成功");
        check(pass, batch.count(OtaBatch.CarTaskStatus.FAILED) == 1, "1 台车安装失败");
        check(pass, rejected, "期望状态不匹配的推进被拒(防并发/重复推进)");

        int rolledBack = batch.rollbackSuccessfulCars();   // 失败触发整体回滚

        check(pass, rolledBack == 4 && batch.count(OtaBatch.CarTaskStatus.PENDING) == 4,
                "失败触发回滚：4 台成功车全部打回 PENDING 待刷回 1.4.0");
        check(pass, batch.count(OtaBatch.CarTaskStatus.SUCCEEDED) == 0, "回滚后无残留 SUCCEEDED");
        check(pass, batch.audit().size() >= 15, "审计行 >= 15(每个状态迁移一条)");

        System.out.println("-- 审计轨迹(前 6 行) --");
        batch.audit().stream().limit(6).forEach(a ->
                System.out.println("  " + a.vin() + "  " + a.action() + "  " + a.detail()));
        System.out.printf("ALL PASS: %d/6%n", pass.get());
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
