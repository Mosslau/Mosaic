// languages/java/ph22-ai-platform/examples/ex07-quota-metering/QuotaMeteringDemo.java —— 配额校验（提交前拒绝）+ 事件驱动 GPU 秒计量（运行中累计）演练
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex07 *.java && java -cp /tmp/ph22-ex07 QuotaMeteringDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;

public final class QuotaMeteringDemo {

    public static void main(String[] args) {
        AtomicInteger pass = new AtomicInteger();
        int total = 9;

        // ---------- 数据（确定性自造）：两个租户的配额 ----------
        QuotaGuard guard = new QuotaGuard()
                .put("team-vision", new Quota(8, 4, 20_000))
                .put("team-nlp", new Quota(4, 2, 5_000));
        MeteringLedger ledger = new MeteringLedger();

        // 1) 配额内：允许提交（Optional.empty = 没有拒绝原因）
        Optional<String> allowed = guard.check("team-vision", 4, 1, 3_600);
        check(pass, allowed.isEmpty(),
                "配额内通过：team-vision 申请 4 卡（上限 8）、排队 2/4、今日 3600/20000 GPU 秒 → 允许提交");

        // 2) 超 GPU 配额 → 拒绝，原因可读且是「申请/上限」的对照
        Optional<String> overGpu = guard.check("team-vision", 12, 1, 3_600);
        check(pass, overGpu.isPresent() && overGpu.get().equals("配额不足：GPU 12/8"),
                "超 GPU 配额被拒且原因可读：" + overGpu.orElse("(未拒绝)"));

        // 3) 超排队数 → 拒绝（本次提交也要占一个排队位）
        Optional<String> overQueue = guard.check("team-vision", 4, 4, 3_600);
        check(pass, overQueue.isPresent() && overQueue.get().contains("排队超限") && overQueue.get().contains("5/4"),
                "超排队数被拒：" + overQueue.orElse("(未拒绝)"));

        // 4) 超日 GPU 秒 → 拒绝（卡数不超也能把预算烧穿）
        Optional<String> overDaily = guard.check("team-vision", 4, 1, 20_000);
        check(pass, overDaily.isPresent() && overDaily.get().contains("GPU 秒") && overDaily.get().contains("20000/20000"),
                "超日 GPU 秒被拒：" + overDaily.orElse("(未拒绝)"));

        // 5) 未登记租户 → 直接拒绝（配额系统不认识他，就没有「等一等」这回事）
        Optional<String> unknown = guard.check("team-unknown", 1, 0, 0);
        check(pass, unknown.isPresent() && unknown.get().contains("未登记租户"),
                "未登记租户被拒：" + unknown.orElse("(未拒绝)"));

        // 6) 拒绝是快速失败：不排队、不写计量事件（校验是纯函数，台账零副作用）
        check(pass, ledger.eventCount() == 0 && ledger.liveCount() == 0,
                "超限快速失败而非排队：5 次拒绝后计量台账仍为空（0 事件 / 0 在跑任务）");

        // 7) 计量：先分配后释放，事件配对且汇总一致 ----------
        long[] now = { 1_400 };   // 固定时钟（秒级），让「未释放任务计到此刻」可复现
        MeteringLedger meter = new MeteringLedger(() -> now[0]);
        meter.allocate("team-vision", "job-1", 4, 1_000);
        meter.release("team-vision", "job-1", 1_300);   // 4 卡 × 300s = 1200 GPU·秒
        meter.allocate("team-vision", "job-2", 2, 1_300);   // 仍在跑
        meter.allocate("team-nlp", "job-3", 8, 1_300);
        meter.release("team-nlp", "job-3", 1_400);      // 8 卡 × 100s = 800 GPU·秒

        List<MeteringLedger.MeterEvent> events = meter.events();
        long allocs = events.stream().filter(e -> e.type().equals(MeteringLedger.ALLOC)).count();
        long releases = events.stream().filter(e -> e.type().equals(MeteringLedger.RELEASE)).count();
        long releasedGpuSeconds = events.stream()
                .filter(e -> e.type().equals(MeteringLedger.RELEASE))
                .mapToLong(MeteringLedger.MeterEvent::gpuSeconds)
                .sum();
        check(pass, events.size() == 5 && allocs == 3 && releases == 2 && releasedGpuSeconds == 2_000
                        && meter.settledGpuSeconds("team-nlp") == 800,
                "计量汇总与事件数一致：3 次分配 + 2 次释放 = 5 条事件，释放结算合计 "
                        + releasedGpuSeconds + " GPU·秒（team-nlp=800）");
        System.out.println("  事件流：" + events.stream().map(MeteringLedger.MeterEvent::render).toList());

        // 8) 未释放任务按当前时钟计入累计值：team-vision = 1200（已结算）+ 2 卡 × 100s（在跑）
        check(pass, meter.gpuSeconds("team-vision") == 1_400 && meter.gpuSeconds("team-nlp") == 800,
                "未释放任务计到此刻：team-vision=" + meter.gpuSeconds("team-vision")
                        + "（1200 已结算 + 2 卡 × 100s 在跑），team-nlp=" + meter.gpuSeconds("team-nlp"));

        // 9) 台账不变量：重复分配同一 jobId / 释放未分配的任务 → 拒绝，且一条事件都不多写
        String dupAlloc = failure(() -> meter.allocate("team-vision", "job-2", 2, 1_500));
        String orphanRelease = failure(() -> meter.release("team-vision", "job-999", 1_500));
        check(pass, dupAlloc != null && dupAlloc.contains("已在计量中")
                        && orphanRelease != null && orphanRelease.contains("未在计量中")
                        && meter.eventCount() == 5,
                "台账不变量：重复分配被拒（" + dupAlloc + "）、释放未分配任务被拒（" + orphanRelease + "），事件数仍为 5");

        System.out.printf("ALL PASS: %d/%d%n", pass.get(), total);
        if (pass.get() != total) {
            System.exit(1);
        }
    }

    /** 期望「必须抛异常」的断言：返回可读原因，未抛异常则返回 null。 */
    private static String failure(Runnable action) {
        try {
            action.run();
            return null;
        } catch (IllegalStateException | IllegalArgumentException e) {
            return e.getMessage();
        }
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
