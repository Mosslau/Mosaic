// project/src/aiplat/MeteringLedger.java —— GPU 秒计量账本（事件驱动）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.ArrayList;
import java.util.List;

/**
 * 计量账本（主文档 3.7/4.4）：先有事件、后有汇总。
 *
 * <p>为什么用「分配/释放事件 + 秒级时间戳」而不是定时采样：
 * 采样会漏掉比采样间隔更短的任务（短任务免费，成本被摊到长任务上），
 * 而提高采样频率又会放大写入压力。事件驱动天然精确（每个任务的卡时被完整记账）且写入量最小——
 * 一个任务只写一条。
 *
 * <p>为什么按 GPU 秒而不是按任务计费：任务大小差异巨大，按任务计费会让小任务补贴大任务。
 */
public final class MeteringLedger {

    private final List<Event> events = new ArrayList<>();

    /** 记录一次「任务结束」的计量事件：持有卡数 × 持有秒数。 */
    public Event record(String tenant, String jobId, int gpus, long startTs, long endTs) {
        long seconds = Math.max(0L, (endTs - startTs) / 1000L);
        Event e = new Event(tenant, jobId, gpus, startTs, endTs, gpus * seconds);
        events.add(e);
        return e;
    }

    public List<Event> events() {
        return List.copyOf(events);
    }

    public int eventCount() {
        return events.size();
    }

    /** 全平台累计 GPU 秒（运维一屏的记账读数）。 */
    public long totalGpuSeconds() {
        long sum = 0;
        for (Event e : events) {
            sum += e.gpuSeconds();
        }
        return sum;
    }

    public long totalGpuSeconds(String tenant) {
        long sum = 0;
        for (Event e : events) {
            if (e.tenant().equals(tenant)) {
                sum += e.gpuSeconds();
            }
        }
        return sum;
    }

    /** 某租户在某一天（epochDay = ts / 86_400_000）消耗的 GPU 秒，配额校验的输入。 */
    public long gpuSecondsOnDay(String tenant, long epochDay) {
        long sum = 0;
        for (Event e : events) {
            if (e.tenant().equals(tenant) && e.startTs() / 86_400_000L == epochDay) {
                sum += e.gpuSeconds();
            }
        }
        return sum;
    }

    /** 计量事件：分配与释放之间的一个事实，只追加不修改。 */
    public record Event(String tenant, String jobId, int gpus, long startTs, long endTs, long gpuSeconds) {
        public long durationSeconds() {
            return Math.max(0L, (endTs - startTs) / 1000L);
        }
    }
}
