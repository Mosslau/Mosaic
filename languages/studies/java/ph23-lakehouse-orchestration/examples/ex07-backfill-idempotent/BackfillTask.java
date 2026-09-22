// languages/java/ph23-lakehouse-orchestration/examples/ex07-backfill-idempotent/BackfillTask.java —— 回填任务：重算哪个表的哪个分区、为什么重算（原因留痕）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex07 *.java && java -cp /tmp/ph23-ex07 BackfillDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）

/**
 * 一次分区级回填：
 *   table     —— 要重算的表（ODS/DWD/DWS/ADS 之一）；
 *   partition —— 要重算的分区（示例统一用日期字符串 `2024-06-01`，与 3.7 的「分区级幂等」对应）；
 *   reason    —— **为什么**重算：上游修数 / 规则变更 / 故障补偿。原因必须留痕（{@link Backfill#history()}），
 *                否则「数变了但没人知道为什么变」——这是湖仓最经典的事故形态（4.4）。
 *
 * 构造时校验非空：回填计划是「依赖图闭包」算出来的，任何空表名/空分区都会让闭包传播失去依据。
 */
public record BackfillTask(String table, String partition, String reason) {

    public BackfillTask {
        if (table == null || table.isBlank()) {
            throw new IllegalArgumentException("表名不能为空");
        }
        if (partition == null || partition.isBlank()) {
            throw new IllegalArgumentException("分区不能为空");
        }
        if (reason == null || reason.isBlank()) {
            throw new IllegalArgumentException("回填原因必须留痕，不能为空");
        }
    }
}
