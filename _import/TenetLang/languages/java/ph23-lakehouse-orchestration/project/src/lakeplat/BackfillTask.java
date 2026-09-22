// project/src/lakeplat/BackfillTask.java —— 回填任务：分区 + 原因 + 状态（原因留痕的最小单位）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

/**
 * 一次回填的最小工作项（主文档 3.7）：**重算哪张表的哪个分区、为什么**。
 *
 * <p>「原因留痕」不是可选项：上游修数、规则变更、故障补偿三种原因对应完全不同的后续动作，
 * 没有 reason 的回填记录在事故复盘时等于没有记录。
 *
 * @param table     目标表
 * @param partition 目标分区（本模型用「分区键=值」或裸值字符串）
 * @param reason    回填原因（上游修数 / 规则变更 / 故障补偿）
 */
public record BackfillTask(TableRef table, String partition, String reason) implements Comparable<BackfillTask> {

    public BackfillTask {
        if (partition == null || partition.isBlank()) {
            throw new IllegalArgumentException("回填分区不能为空");
        }
        if (reason == null || reason.isBlank()) {
            throw new IllegalArgumentException("回填原因不能为空（原因留痕是硬要求）");
        }
    }

    /** 一次执行后的状态（断点续跑的依据）。 */
    public enum Status {
        /** 尚未执行。 */
        PENDING,
        /** 已执行成功（断点续跑时跳过）。 */
        SUCCEEDED,
        /** 中断前未执行（断点续跑时从这里继续）。 */
        SKIPPED
    }

    public String key() {
        return table.table() + "/" + partition;
    }

    @Override
    public int compareTo(BackfillTask other) {
        int byTable = table.table().compareTo(other.table.table());
        return byTable != 0 ? byTable : partition.compareTo(other.partition);
    }

    @Override
    public String toString() {
        return key() + "（" + reason + "）";
    }
}
