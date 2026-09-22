// languages/java/ph23-lakehouse-orchestration/examples/ex06-orchestration-dag/TaskNode.java —— 编排图的节点：一个任务 + 它的上游依赖 + 重试上限
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex06 *.java && java -cp /tmp/ph23-ex06 OrchestrationDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
import java.util.List;

/**
 * 编排图的一个任务节点：
 *   id      —— 任务标识（也是确定性排序的键：同层按 id 排序，保证执行顺序可复盘）；
 *   deps    —— **上游任务 id**：只有全部成功，本任务才就绪（3.6「上游全部成功才就绪」）；
 *   retries —— 失败后的重试上限（示例固定语义：retries 次重试，即最多 retries+1 次尝试）。
 *
 * 构造时校验 id 非空、deps 无自依赖且无重复——依赖图的错误在建模阶段就该被拦下，
 * 否则编排器的就绪判断会建立在错误的图上（与 3.1「口径漂移在建模阶段被拦下」同一条纪律）。
 */
public record TaskNode(String id, List<String> deps, int retries) {

    public TaskNode {
        if (id == null || id.isBlank()) {
            throw new IllegalArgumentException("任务 id 不能为空");
        }
        if (retries < 0) {
            throw new IllegalArgumentException("重试上限不能为负：" + retries);
        }
        deps = List.copyOf(deps);
        if (deps.contains(id)) {
            throw new IllegalArgumentException("任务不能依赖自己：" + id);
        }
        if (deps.stream().distinct().count() != deps.size()) {
            throw new IllegalArgumentException("依赖不能重复声明：" + deps);
        }
    }
}
