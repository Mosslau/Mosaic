// project/src/dataplat/DataPlatformDemo.java —— 数据平台后台(收官项目)端到端演示
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令(在 project/ 目录)：
//   javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
//   java -cp /tmp/tl21-proj dataplat.DataPlatformDemo
//
// 数据链路(roadmap §21 的「数据源 → 接入 → 总线 → 消费/清洗/告警/存储 → 后台」)：
//
//   3 台模拟g ──并发──▶ IngestService(校验+去重) ──▶ MetricBus(按 SOURCE_ID 分区)
//        ──▶ MetricConsumer.drain ──▶ 状态缓存 + 作业历史 + 节点在线 + 告警引擎
//   ReleasePlatform 单独跑一个升级批次(成功/失败/回滚)，最后 OpsConsole 出运维总览。
//
// 全部内存实现、无第三方依赖，验收断言即 PASS 行。每个模块对应一个真实服务边界：
// registry=节点管理服务，ingest=接入网关后的接入服务，bus≈Kafka topic，
// consumer=指标消费服务，alert=告警引擎，ota=版本发布平台，console=运维后台。
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class DataPlatformDemo {
    private static final int FRAMES_PER_SOURCE = 400;

    public static void main(String[] args) throws InterruptedException {
        NodeRegistry registry = new NodeRegistry();
        // 注册 6 个数据源：3 台即将并发上报指标，3 台留给 版本发布批次
        for (int i = 1; i <= 6; i++) {
            registry.register("LSV" + String.format("%07d", i), MODEL(i), "v1.4.0");
        }

        MetricBus bus = new MetricBus();
        IngestService ingest = new IngestService(bus);

        SourceStateCache stateCache = new SourceStateCache();
        JobHistoryStore jobHistoryStore = new JobHistoryStore();
        AlertEngine alerts = new AlertEngine(List.of(new AlertRules.CpuWatermarkRule(), new AlertRules.DiskOverheatRule()));

        // 三个模拟数据源并发上报(数据源 1 末帧 CPU 高水位、数据源 2 末帧磁盘过热，供规则引擎触发)
        List<Thread> cars = new ArrayList<>();
        for (int i = 1; i <= 3; i++) {
            final String sourceId = "LSV" + String.format("%07d", i);
            final boolean cpuHighEnd = (i == 1);
            final boolean overheatEnd = (i == 2);
            Thread t = new Thread(() -> reportCar(sourceId, ingest, cpuHighEnd, overheatEnd), "source-" + sourceId);
            cars.add(t);
            t.start();
        }
        for (Thread t : cars) {
            t.join();
        }

        // 消费总线积压：一次 drain 处理全部帧
        MetricConsumer consumer = new MetricConsumer(bus, registry, stateCache, jobHistoryStore, alerts);
        long drained = consumer.drain();

        // 版本发布批次：发布 2.2.0 并给 4/5/6 号数据源升级
        ReleasePlatform ota = new ReleasePlatform();
        ReleasePlatform.ReleaseBatch batch = runOtaBatch(ota, registry);

        // 运维后台
        OpsConsole ops = new OpsConsole(registry, stateCache, alerts, consumer, ota);
        ops.print();

        // ---- 验收断言 ----
        AtomicInteger pass = new AtomicInteger();
        // ① 接入层：校验/去重/坏帧拦截计数精确
        check(pass, ingest.accepted() == 3L * FRAMES_PER_SOURCE, "接入：3 个数据源 × 400 帧全部接受入总线");
        check(pass, ingest.duplicates() == 9, "接入：3 个数据源各 3 次重发全部判重");
        check(pass, ingest.rejected() == 6, "接入：6 条坏帧全部被拒");
        check(pass, bus.totalProduced() == 3L * FRAMES_PER_SOURCE, "总线：恰好接收 1200 帧(去重/坏帧未污染)");
        // ② 消费层：drain 完积压、状态缓存与作业历史落库
        check(pass, drained == 1200 && consumer.lag() == 0, "消费：drain 1200 帧且积压归零");
        check(pass, stateCache.size() == 3 && stateCache.all().stream().allMatch(s -> s.seq() == FRAMES_PER_SOURCE),
                "状态缓存：3 个数据源最新帧收敛到 seq=" + FRAMES_PER_SOURCE);
        check(pass, jobHistoryStore.totalPoints() == 1200, "作业历史：1200 个点全部落库");
        // ③ 节点域：上报数据源在线，未上报仍 REGISTERED
        check(pass, registry.countByStatus(NodeRegistry.Status.ONLINE) == 3, "节点：3 台上报g在线");
        // ④ 告警引擎：低电与过热各一条活跃告警
        check(pass, alerts.activeCount() == 2, "告警：CPU_HIGH_WATERMARK + DISK_OVERHEAT 各 1 条活跃");
        // ⑤ 版本发布：批次结果 + 失败数据源回滚 + 版本升级
        check(pass, batch.count(ReleasePlatform.TaskState.SUCCEEDED) == 2, "版本发布：2 台升级成功");
        check(pass, batch.count(ReleasePlatform.TaskState.ROLLED_BACK) == 1, "版本发布：失败数据源已回滚(ROLLED_BACK)");
        check(pass, registry.findById("LSV0000004").orElseThrow().fwVersion().equals("v2.2.0"),
                "版本发布：4 号数据源版本已升到 FW 2.2.0");
        check(pass, batch.audit().size() >= 8 && ota.audit().size() >= 2, "审计：批次与平台操作均可回溯");
        // ⑥ 运维台聚合读数
        OpsConsole.OpsView view = ops.snapshot();
        check(pass, view.totalSources() == 6 && view.onlineSources() == 3
                        && view.activeAlerts() == 2 && view.busLag() == 0,
                "运维台：6 个数据源 / 在线 3 / 告警 2 / 无积压，聚合读数一致");
        System.out.printf("ALL PASS: %d/14%n", pass.get());
    }

    /** 一个模拟数据源：发送 400 帧，中途重发 3 次、注入 2 条坏帧；末帧按需构造告警条件。 */
    private static void reportCar(String sourceId, IngestService ingest, boolean cpuHighEnd, boolean overheatEnd) {
        for (long seq = 1; seq <= FRAMES_PER_SOURCE; seq++) {
            double cpuPct = 35 + (seq % 30);
            double latencyMs = seq % 60;
            double temp = 35 + (seq % 25);
            if (seq == FRAMES_PER_SOURCE && cpuHighEnd) {
                cpuPct = 92;                    // 末帧 CPU 高水位：触发 CPU_HIGH_WATERMARK
            }
            if (seq == FRAMES_PER_SOURCE && overheatEnd) {
                temp = 82;                     // 末帧磁盘过热：触发 DISK_OVERHEAT
            }
            ingest.submit(frame(sourceId, seq, cpuPct, latencyMs, temp));
            if (seq == 100 || seq == 200 || seq == 300) {
                ingest.submit(frame(sourceId, seq, cpuPct, latencyMs, temp));   // 故意重发：应判 dup
            }
            if (seq == 150 || seq == 350) {
                ingest.submit("T|" + sourceId + "|bad|not|frame");      // 坏帧：应被拒
            }
        }
    }

    private static String frame(String sourceId, long seq, double cpuPct, double latencyMs, double temp) {
        return String.format("T|%s|%d|%.1f|%.1f|%.1f", sourceId, seq, cpuPct, latencyMs, temp);
    }

    private static ReleasePlatform.ReleaseBatch runOtaBatch(ReleasePlatform ota, NodeRegistry registry) {
        ota.publish("1.4.0");
        ota.publish("2.0.0");
        ota.publish("2.2.0");
        List<String> targets = List.of("LSV0000004", "LSV0000005", "LSV0000006");
        ReleasePlatform.ReleaseBatch batch = ota.createBatch("版本发布-2025-001", "2.2.0", targets);
        for (String sourceId : targets) {
            batch.advance(sourceId, ReleasePlatform.TaskState.PENDING, ReleasePlatform.TaskState.DOWNLOADING);
            batch.advance(sourceId, ReleasePlatform.TaskState.DOWNLOADING, ReleasePlatform.TaskState.INSTALLING);
        }
        // 4 号数据源成功、5 号数据源失败、6 号数据源成功
        batch.advance("LSV0000004", ReleasePlatform.TaskState.INSTALLING, ReleasePlatform.TaskState.SUCCEEDED);
        batch.advance("LSV0000005", ReleasePlatform.TaskState.INSTALLING, ReleasePlatform.TaskState.FAILED);
        batch.advance("LSV0000006", ReleasePlatform.TaskState.INSTALLING, ReleasePlatform.TaskState.SUCCEEDED);
        // 失败数据源回滚，成功数据源版本生效(写节点档案)
        batch.rollback("LSV0000005");
        registry.upgradeFirmware("LSV0000004", "v2.2.0");
        registry.upgradeFirmware("LSV0000006", "v2.2.0");
        return batch;
    }

    private static String MODEL(int i) {
        return i <= 4 ? "EV-Sedan" : "EV-Truck";
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
