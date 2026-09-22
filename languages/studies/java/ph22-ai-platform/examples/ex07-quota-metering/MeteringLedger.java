// languages/java/ph22-ai-platform/examples/ex07-quota-metering/MeteringLedger.java —— 事件驱动的 GPU 秒计量台账：分配/释放各写一条事件，按租户累计
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex07 *.java && java -cp /tmp/ph22-ex07 QuotaMeteringDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.LongSupplier;

/**
 * 计量的口径是「先有事件、后有汇总」：每次分配写一条 alloc 事件，每次释放写一条 release 事件并结算
 * (释放时刻 − 分配时刻) × 卡数 的 GPU·秒。相比定时采样，事件驱动既不会漏掉短任务（采样会漏），
 * 写入量也小得多（4.4 的取舍）。
 * 两个工程细节：
 *   ① 时钟可注入（LongSupplier，秒级时间戳）——未释放任务的「至今消耗」必须能确定性复现；
 *   ② 未释放的分配按**当前时钟**计入累计值——否则长任务在跑的时候，值班看板上这个租户像是没花钱。
 */
public final class MeteringLedger {

    public static final String ALLOC = "alloc";
    public static final String RELEASE = "release";

    /** 一条计量事件：分配事件 gpuSeconds=0，释放事件带上本次结算的 GPU·秒。 */
    public record MeterEvent(String tenant, String jobId, String type, int gpus, long ts, long gpuSeconds) {
        public String render() {
            return type + " " + tenant + "/" + jobId + " gpus=" + gpus + " ts=" + ts + " gpuSeconds=" + gpuSeconds;
        }
    }

    /** 未释放的分配（内存中的「在跑任务」集合）。 */
    private record Live(String tenant, int gpus, long startTs) { }

    private final LongSupplier clock;
    private final List<MeterEvent> events = new ArrayList<>();
    private final Map<String, Long> settled = new HashMap<>();      // tenant → 已结算 GPU·秒
    private final Map<String, Live> live = new LinkedHashMap<>();   // jobId → 未释放分配

    public MeteringLedger() {
        this(() -> System.currentTimeMillis() / 1000L);
    }

    /** 注入固定时钟（秒级）后可确定性复现「未释放任务计到此刻」。 */
    public MeteringLedger(LongSupplier clockSeconds) {
        this.clock = clockSeconds;
    }

    /** 分配：写 alloc 事件并登记在跑任务；同一 jobId 重复分配会被拒（否则计量会翻倍）。 */
    public synchronized MeterEvent allocate(String tenant, String jobId, int gpus, long ts) {
        if (gpus <= 0) {
            throw new IllegalArgumentException("gpus 必须为正：" + gpus);
        }
        Live running = live.get(jobId);
        if (running != null) {
            throw new IllegalStateException("任务已在计量中：" + jobId + "（租户 " + running.tenant() + "）");
        }
        live.put(jobId, new Live(tenant, gpus, ts));
        MeterEvent event = new MeterEvent(tenant, jobId, ALLOC, gpus, ts, 0);
        events.add(event);
        return event;
    }

    /** 释放：结算 GPU·秒（秒级时间戳 × 卡数），写 release 事件并结清该任务。 */
    public synchronized MeterEvent release(String tenant, String jobId, long ts) {
        Live running = live.get(jobId);
        if (running == null) {
            throw new IllegalStateException("任务未在计量中（或已释放）：" + jobId);
        }
        if (!running.tenant().equals(tenant)) {
            throw new IllegalStateException("租户不匹配：" + jobId + " 属于 " + running.tenant() + "，不能按 " + tenant + " 结算");
        }
        if (ts < running.startTs()) {
            throw new IllegalStateException("释放时间早于分配时间：" + ts + " < " + running.startTs());
        }
        live.remove(jobId);
        long gpuSeconds = (ts - running.startTs()) * running.gpus();
        settled.merge(tenant, gpuSeconds, Long::sum);
        MeterEvent event = new MeterEvent(tenant, jobId, RELEASE, running.gpus(), ts, gpuSeconds);
        events.add(event);
        return event;
    }

    /** 租户累计 GPU·秒 = 已结算 + 未释放任务按当前时钟计到此刻。 */
    public synchronized long gpuSeconds(String tenant) {
        long total = settled.getOrDefault(tenant, 0L);
        long now = clock.getAsLong();
        for (Live running : live.values()) {
            if (running.tenant().equals(tenant)) {
                total += Math.max(0L, now - running.startTs()) * running.gpus();
            }
        }
        return total;
    }

    /** 只统计已释放任务结算出的 GPU·秒（对账用，不含在跑任务）。 */
    public synchronized long settledGpuSeconds(String tenant) {
        return settled.getOrDefault(tenant, 0L);
    }

    /** 不可变事件流快照（真实平台里这份流会落到 Kafka/数仓，见 ph21）。 */
    public synchronized List<MeterEvent> events() {
        return List.copyOf(events);
    }

    public synchronized int eventCount() {
        return events.size();
    }

    public synchronized int liveCount() {
        return live.size();
    }
}
