// exercises/sol-01-source-report/ReportApiDemo.java —— 上报 API 验收演示
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//   然后 java -cp /tmp/tl21-sol ReportApiDemo
// 场景：单 SOURCE_ID 双路并发各报 1000 帧(seq 都从 1 到 1000)，坏 SOURCE_ID/越界帧混入；
//   验收：OK 恰 1000(去重保序)，坏帧全部拒绝，最终状态收敛到 seq=1000 且线程安全。
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicInteger;

public final class ReportApiDemo {
    private static final String SOURCE_ID = "LSV0000001";

    public static void main(String[] args) throws InterruptedException {
        ReportApi api = new ReportApi();
        List<ReportApi.Verdict>[] laneResults = allLaneResults(api);

        AtomicInteger pass = new AtomicInteger();
        // 1) 双路并发上报：每路 seq 1..1000
        Thread laneA = new Thread(() -> pump(api, laneResults[0], 1));
        Thread laneB = new Thread(() -> pump(api, laneResults[1], 200));
        laneA.start();
        laneB.start();
        laneA.join();
        laneB.join();

        long ok = laneResults[0].stream().filter(v -> v == ReportApi.Verdict.OK).count()
                + laneResults[1].stream().filter(v -> v == ReportApi.Verdict.OK).count();
        check(pass, ok == 1000, "双路各 1000 帧并发上报，去重后 OK=1000(seq 单调性被保住)");
        check(pass, api.latest(SOURCE_ID) != null && api.latest(SOURCE_ID).seq() == 1000,
                "最终状态收敛到 seq=1000(旧帧未覆写新帧)");

        // 2) 坏帧：非法 SOURCE_ID / CPU 越界
        check(pass, api.handle(new DataReport("SOURCE_ID", 1, 50, 60, 40)) == ReportApi.Verdict.REJECT_INVALID_ID,
                "非法 SOURCE_ID 被拒");
        check(pass, api.handle(new DataReport(SOURCE_ID, 1001, 105.0, 60, 40)) == ReportApi.Verdict.REJECT_RANGE,
                "CPU 越界被拒");
        check(pass, api.handle(new DataReport(SOURCE_ID, 5, 50, 60, 40)) == ReportApi.Verdict.DUPLICATE,
                "旧 seq 帧被判重复");

        System.out.println("已接收帧总数=" + api.okCount() + "，拒绝=" + api.rejectCount());
        System.out.printf("ALL PASS: %d/5%n", pass.get());
    }

    @SuppressWarnings("unchecked")
    private static List<ReportApi.Verdict>[] allLaneResults(ReportApi api) {
        return new List[] { new CopyOnWriteArrayList<>(), new CopyOnWriteArrayList<>() };
    }

    private static void pump(ReportApi api, List<ReportApi.Verdict> out, int startDelayMs) {
        if (startDelayMs > 0) {
            try { Thread.sleep(startDelayMs); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        }
        for (long seq = 1; seq <= 1000; seq++) {
            out.add(api.handle(new DataReport(SOURCE_ID, seq, 50.0, 60.0, 40.0)));
        }
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) { pass.incrementAndGet(); }
    }
}
