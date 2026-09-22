// languages/java/ph23-lakehouse-orchestration/examples/ex05-batch-stream-unified/UnifiedPipelineDemo.java —— 批流一体确定性演练：批算/流算一致、迟到侧输出、水位线、幂等窗口覆盖与重放不重复计数
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex05 *.java && java -cp /tmp/ph23-ex05 UnifiedPipelineDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

public final class UnifiedPipelineDemo {

    /** 口径固定：60s 窗口、允许迟到 5s（水位线 = maxSeenEventTs - 5000）。 */
    private static final long WINDOW = 60_000L;
    private static final long LATENESS = 5_000L;

    public static void main(String[] args) {
        AtomicInteger pass = new AtomicInteger();
        int total = 7;

        // ---------- 数据（确定性自造）：inst-a 与 inst-b 两个 key、三个 60s 窗口、事件时间乱序到达 ----------
        // 第一批（全部按时到达，可称为「正常流」）
        Event a = new Event("inst-a", 10_000, 1.0);
        Event b = new Event("inst-a", 20_000, 2.0);
        Event c = new Event("inst-b", 30_000, 3.0);
        Event d = new Event("inst-a", 70_000, 4.0);    // 乱序：先到 70000，再到 80000
        Event e = new Event("inst-b", 80_000, 5.0);
        Event g = new Event("inst-a", 120_000, 7.0);
        // 第二批：只把水位线推到 125_000（maxSeenEventTs 130_000 - lateness 5_000），不产生新的窗口值
        Event f = new Event("inst-a", 130_000, 6.0);
        // 第三批：两条「必然迟到」的事件（g 已在第一批按时到达，不在迟到之列），eventTs 都 <= 到达时刻的水位线
        Event lateB = new Event("inst-b", 40_000, 8.0);    // 到达时水位线 125_000 → 40_000 <= 125_000
        Event lateEdge = new Event("inst-b", 45_000, 9.0); // 到达时水位线 125_000 → 45_000 <= 125_000

        List<Event> onTimeArrival = List.of(a, b, c, d, e, g);
        List<Event> watermarkAdvance = List.of(f);
        List<Event> lateArrival = List.of(lateB, lateEdge);
        List<Event> fullLog = List.of(a, b, c, d, e, g, f, lateB, lateEdge);

        // ---------- 运行 1：无迟到事件的第一批到达 ----------
        Pipeline first = new Pipeline(WINDOW, LATENESS);
        Pipeline.Result r1 = first.stream(onTimeArrival);
        Map<Window, Pipeline.WindowAgg> batch1 = first.batch(onTimeArrival);

        System.out.println("批算(60s 窗口)     ：" + Pipeline.render(batch1));
        System.out.println("流算(无迟到)       ：" + Pipeline.render(r1.windows()));
        System.out.println("水位线推进         ：" + watermarkTrace(onTimeArrival));
        System.out.println("侧输出(无迟到)     ：" + Pipeline.renderEvents(r1.sideOutput()));

        // A) 无迟到时，批算与流算对同一窗口结果逐项一致
        Pipeline.WindowAgg w1a = r1.window("inst-a", 60_000, 120_000);
        Pipeline.WindowAgg w2a = r1.window("inst-a", 120_000, 180_000);
        Pipeline.WindowAgg w0a = r1.window("inst-a", 0, WINDOW);
        boolean batchStreamEqual = Pipeline.render(batch1).equals(Pipeline.render(r1.windows()));
        check(pass, batchStreamEqual && r1.lateCount() == 0
                        && w1a.count() == 1 && w1a.sum() == 4.0
                        && w0a.count() == 2 && w0a.sum() == 3.0
                        && w2a.count() == 1 && w2a.sum() == 7.0,
                "批算与流算同一窗口结果一致：5 个窗口逐项相等（" + w1a + "、" + w0a
                        + "），口径与执行方式无关");

        // ---------- 运行 2：f 到达把水位线推到 125_000；随后两条迟到事件到达 ----------
        first.stream(watermarkAdvance);            // 只推水位线，不改既有窗口
        Pipeline.Result r2 = first.stream(lateArrival);
        System.out.println("流算(含迟到)       ：" + Pipeline.render(r2.windows()));
        System.out.println("侧输出(迟到分区)   ：" + Pipeline.renderEvents(r2.sideOutput()));
        System.out.println("水位线(迟到后)     ：" + r2.lastWatermark() + "，迟到计数 " + r2.lateCount());

        // B) 迟到事件被计数并写入侧输出；它们在补偿前不参与窗口聚合
        Pipeline.WindowAgg w0bPartial = r2.window("inst-b", 0, WINDOW);
        check(pass, r2.lateCount() == 2
                        && r2.sideOutput().equals(List.of(lateB, lateEdge))
                        && w0bPartial.count() == 1 && w0bPartial.sum() == 3.0,
                "迟到事件被计数且进侧输出：lateCount=2，侧输出=[" + Pipeline.renderEvents(r2.sideOutput())
                        + "]，窗口仍是原值（inst-b[0,60000) count=" + w0bPartial.count() + "，迟到事件不混进窗口）");

        // C) 水位线计算正确：等于 maxSeenEventTs - allowedLateness，且 <= 水位线即判迟到
        check(pass, r1.lastWatermark() == 120_000L - LATENESS
                        && r2.lastWatermark() == 130_000L - LATENESS
                        && lateB.eventTs() <= r2.lastWatermark() && lateEdge.eventTs() <= r2.lastWatermark(),
                "水位线计算正确：第一批后 " + r1.lastWatermark() + "（=120000-5000），f 到达后 "
                        + r2.lastWatermark() + "（=130000-5000）；两条迟到事件 eventTs ∈ {40000,45000} 都 <= 水位线");

        // ---------- 运行 3：侧输出补偿（迟到事件回灌，用同一口径重跑） ----------
        Pipeline freshCompensation = new Pipeline(WINDOW, LATENESS);
        freshCompensation.stream(onTimeArrival);            // 第一批：按时到达
        freshCompensation.stream(watermarkAdvance);         // 第二批：推水位线（g 由此被判迟到）
        freshCompensation.stream(lateArrival);              // 第三批：两条迟到事件
        Pipeline.Result freshResult = freshCompensation.compensate();   // 把侧输出回灌重算
        Pipeline.Result r3 = first.compensate();            // 在运行 2 的侧输出（3 条）上补偿
        Map<Window, Pipeline.WindowAgg> batchFull = new Pipeline(WINDOW, LATENESS).batch(fullLog);

        // D) 侧输出补偿后，窗口结果与「批算(原事件 ∪ 迟到事件)」逐项一致
        check(pass, Pipeline.render(r3.windows()).equals(Pipeline.render(batchFull))
                        && Pipeline.render(freshResult.windows()).equals(Pipeline.render(batchFull))
                        && r3.window("inst-b", 0, WINDOW).count() == 3
                        && r3.window("inst-b", 0, WINDOW).sum() == 20.0
                        && r3.window("inst-a", 120_000, 180_000).count() == 2
                        && r3.window("inst-a", 120_000, 180_000).sum() == 13.0,
                "侧输出补偿后与批算一致：inst-b[0,60000) count=3 sum=20.0（含两条迟到事件）"
                        + "，均等于批算值（迟到只影响出数时机，不影响数值）");

        // ---------- 运行 4：重放同一批事件（幂等） ----------
        String beforeReplay = Pipeline.render(r3.windows());
        int processedBefore = r3.processedEvents();
        Pipeline.Result r4 = first.replay();
        Pipeline.Result r5 = first.replay();

        // E) 重放不重复计数：窗口逐项相同、迟到计数不变、已消费事件数不增长
        check(pass, Pipeline.render(r4.windows()).equals(beforeReplay)
                        && Pipeline.render(r5.windows()).equals(beforeReplay)
                        && r4.lateCount() == 2 && r5.lateCount() == 2
                        && r4.processedEvents() == processedBefore && r5.processedEvents() == processedBefore,
                "重放不重复计数：连续两次 replay 窗口值逐项不变，lateCount 仍为 " + r5.lateCount()
                        + "，已消费事件数停在 " + r5.processedEvents());

        // F) 窗口覆盖语义：整体覆盖 → 同窗口再算一次值不变；若换成追加语义 → 计数翻倍
        Pipeline.WindowAgg keyWindow = r1.window("inst-a", 60_000, 120_000);
        Map<Window, Pipeline.WindowAgg> appended = Pipeline.applyIncrementally(batch1, onTimeArrival, WINDOW);
        Pipeline.WindowAgg appendedWindow = appended.get(new Window("inst-a", 60_000, 120_000));
        check(pass, keyWindow.count() == 1 && keyWindow.sum() == 4.0
                        && appendedWindow.count() == 2 && appendedWindow.sum() == 8.0,
                "窗口覆盖 vs 追加：覆盖语义下 inst-a[60000,120000) 恒定 count=1 sum=4.0；"
                        + "同一批事件走追加语义变成 count=" + appendedWindow.count() + " sum=" + appendedWindow.sum()
                        + "（这就是重放重复计数的来源）");

        // G) 乱序但未迟到的事件仍按事件时间正确归类；恰好等于水位线的边界事件判迟到
        Pipeline outOfOrderPipe = new Pipeline(WINDOW, LATENESS);
        outOfOrderPipe.stream(List.of(new Event("inst-c", 40_000, 1.0)));   // 先把水位线推到 35000
        Pipeline.Result outOfOrder = outOfOrderPipe.stream(List.of(
                new Event("inst-c", 65_000, 2.0),   // 乱序到达但 65000 > 水位线 35000 → 不迟到
                new Event("inst-c", 5_000, 3.0),    // 处理到它时水位线已升到 60000 → 迟到
                new Event("inst-c", 60_000, 5.0))); // 恰好等于水位线 60000 → 边界也判迟到
        boolean boundary = outOfOrder.sideOutput().contains(new Event("inst-c", 5_000, 3.0))
                && outOfOrder.sideOutput().contains(new Event("inst-c", 60_000, 5.0));
        check(pass, outOfOrderPipe.windowOf("inst-c", 59_999).windowStart() == 0
                        && outOfOrderPipe.windowOf("inst-c", 60_000).windowStart() == 60_000
                        && outOfOrder.window("inst-c", 60_000, 120_000).count() == 1
                        && outOfOrder.window("inst-c", 60_000, 120_000).sum() == 2.0
                        && outOfOrder.window("inst-c", 0, 60_000).count() == 1
                        && outOfOrder.window("inst-c", 0, 60_000).sum() == 1.0
                        && outOfOrder.lateCount() == 2 && boundary,
                "乱序未迟到仍按事件时间归类：乱序到达的 65000 进 inst-c[60000,120000)（count=1 sum=2.0）；"
                        + "5000 与恰好等于水位线的 60000 都被判迟到（lateCount=" + outOfOrder.lateCount()
                        + "）——半开区间让 60000 归属 [60000,120000)，而水位线把它判为迟到");

        System.out.printf("ALL PASS: %d/%d%n", pass.get(), total);
        if (pass.get() != total) {
            System.exit(1);
        }
    }

    /** 逐条重算水位线并渲染成「事件时间→水位线」的推进轨迹（确定性、不读系统时间）。 */
    private static String watermarkTrace(List<Event> events) {
        StringBuilder sb = new StringBuilder();
        long watermark = Long.MIN_VALUE;
        for (Event event : events) {
            watermark = Math.max(watermark, event.eventTs()) - LATENESS;
            if (sb.length() > 0) {
                sb.append(" -> ");
            }
            sb.append(event.eventTs()).append("⇒").append(watermark);
        }
        return sb.toString();
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
