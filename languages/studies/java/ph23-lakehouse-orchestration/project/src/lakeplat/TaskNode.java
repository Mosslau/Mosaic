// project/src/lakeplat/TaskNode.java —— DAG 节点：依赖 + 重试上限
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.List;

/**
 * 编排 DAG 上的一个任务节点（主文档 3.6 的 {@code TaskNode}）。
 *
 * <p>依赖用**任务 id 列表**表达（不是表名）：编排器只认「上游任务成功」这一个就绪条件，
 * 表与表的依赖纪律由 {@link WarehouseModel} 守，两者关注点分离。
 *
 * @param id       任务 id（同层排序的唯一确定性来源）
 * @param deps     上游任务 id 列表
 * @param retries  重试上限（失败后最多再跑几次；无限重试会占满执行槽）
 * @param table    该任务产出的表（把编排与湖仓模型对上）
 */
public record TaskNode(String id, List<String> deps, int retries, TableRef table) {

    public TaskNode {
        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException("任务 id 不能为空");
        }
        deps = List.copyOf(deps);
        if (retries < 0) {
            throw new IllegalArgumentException("重试上限不能为负：" + id);
        }
        if (deps.contains(id)) {
            throw new IllegalArgumentException("任务 " + id + " 依赖自身");
        }
    }

    /** 便捷构造：默认重试 2 次。 */
    public static TaskNode of(String id, TableRef table, String... deps) {
        return new TaskNode(id, List.of(deps), 2, table);
    }

    /** 最大尝试次数 = 1 次初始 + retries 次重试。 */
    public int maxAttempts() {
        return retries + 1;
    }

    @Override
    public String toString() {
        return id + (deps.isEmpty() ? "(源任务)" : "←" + deps) + "，重试上限 " + retries;
    }
}
