// examples/ex06-ota-batch/OtaBatch.java —— OTA 批次：单车状态机 + 批次汇总 + 审计 + 回滚
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 教学点：OTA 的「可靠性」来自三件事——
//   1. 单车任务走状态机：PENDING→DOWNLOADING→INSTALLING→SUCCEEDED/FAILED，
//      非法迁移抛异常(与 ex01 设备聚合同款思路)，绝不直接改字段；
//   2. 每个状态变更都写审计行(谁在何时把车从哪个状态推到哪个状态)；
//   3. 批次可回滚：一旦出现 FAILED，平台把已成功的车集体退回上一版本(版本回滚比逐车手工修可靠)。
// 并发：单车升级用一个锁串行化，避免「下载完成与超时判失败」这类并发改状态。
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.locks.ReentrantLock;

public final class OtaBatch {
    public enum CarTaskStatus { PENDING, DOWNLOADING, INSTALLING, SUCCEEDED, FAILED }

    public record CarTask(String vin, OtaVersion fromVersion, CarTaskStatus status, String detail) { }

    public record AuditLine(Instant at, String vin, String action, String detail) {
        static AuditLine of(String vin, String action, String detail) {
            return new AuditLine(Instant.now(), vin, action, detail);
        }
    }

    private final String batchId;
    private final OtaVersion targetVersion;
    private final List<CarTask> tasks = new ArrayList<>();
    private final List<AuditLine> audit = new ArrayList<>();
    private final ReentrantLock batchLock = new ReentrantLock();   // 串行化所有状态变更

    public OtaBatch(String batchId, OtaVersion targetVersion, OtaVersion beforeVersion, List<String> vins) {
        this.batchId = batchId;
        this.targetVersion = targetVersion;
        for (String vin : vins) {
            tasks.add(new CarTask(vin, beforeVersion, CarTaskStatus.PENDING, "created"));
        }
    }

    public String batchId()         { return batchId; }
    public OtaVersion targetVersion() { return targetVersion; }
    public List<CarTask> tasks()    { return List.copyOf(tasks); }
    public List<AuditLine> audit()  { return List.copyOf(audit); }

    /** 推进单车状态：当前状态必须等于 expect，否则抛异常(防并发重复推进)。 */
    public void advance(String vin, CarTaskStatus expect, CarTaskStatus next, String detail) {
        batchLock.lock();
        try {
            CarTask task = findByVin(vin);
            if (task.status() != expect) {
                throw new IllegalStateException("批次 " + batchId + " 车辆 " + vin
                        + " 期望状态 " + expect + " 实际 " + task.status());
            }
            CarTask updated = new CarTask(vin, fromVersionOf(vin), next, detail);
            replace(vin, updated);
            audit.add(AuditLine.of(vin, expect + "->" + next, detail));
        } finally {
            batchLock.unlock();
        }
    }

    /** 回滚：把所有 SUCCEEDED 的车打回 PENDING(代表需要刷回上一固件版本)。 */
    public int rollbackSuccessfulCars() {
        batchLock.lock();
        try {
            int rolled = 0;
            for (int i = 0; i < tasks.size(); i++) {
                CarTask t = tasks.get(i);
                if (t.status() == CarTaskStatus.SUCCEEDED) {
                    CarTask back = new CarTask(t.vin(), t.fromVersion(), CarTaskStatus.PENDING,
                            "rollback-to-" + t.fromVersion());
                    tasks.set(i, back);
                    audit.add(AuditLine.of(t.vin(), "SUCCEEDED->PENDING", "rollback: " + t.detail()));
                    rolled++;
                }
            }
            return rolled;
        } finally {
            batchLock.unlock();
        }
    }

    public long count(CarTaskStatus s) {
        return tasks.stream().filter(t -> t.status() == s).count();
    }

    private CarTask findByVin(String vin) {
        return tasks.stream().filter(t -> t.vin().equals(vin)).findFirst().orElseThrow();
    }

    private OtaVersion fromVersionOf(String vin) {
        return findByVin(vin).fromVersion();
    }

    private void replace(String vin, CarTask updated) {
        for (int i = 0; i < tasks.size(); i++) {
            if (tasks.get(i).vin().equals(vin)) {
                tasks.set(i, updated);
                return;
            }
        }
    }
}
