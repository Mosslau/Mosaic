// languages/java/ph22-ai-platform/examples/ex01-training-job/JobState.java —— 训练任务状态机：sealed 状态集 + 终态语义
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex01 *.java && java -cp /tmp/ph22-ex01 TrainingJobDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 为什么用 sealed interface 而不是 enum：状态本身可以携带数据（失败原因、产物 id、
// 取消操作人），而 sealed 让「还有哪些状态」在编译期闭合——后面新增状态时，所有
// switch 都会编译报错提醒补分支，不会漏掉某个状态的处理。
// 但状态机真正的不变式（谁能转到谁）不放在这里，而是收在聚合根 TrainingJob 内部：
// 状态集是「数据结构」，迁移规则是「领域约束」，两者职责不同。
sealed interface JobState permits JobState.Queued, JobState.Running, JobState.Succeeded,
        JobState.Failed, JobState.Cancelled {

    /** 排队中：已通过提交校验并占用幂等键，等待调度器分配 GPU。 */
    record Queued() implements JobState { }

    /** 运行中：已拿到 GPU，训练执行体（PyTorch 作业，黑盒进程）正在跑。 */
    record Running(String node) implements JobState { }

    /** 成功（终态）：训练产出已登记为模型版本，不可再迁移。 */
    record Succeeded(String artifactId) implements JobState { }

    /** 失败：可由 retry() 重新入队，但受 attempt 上限约束。 */
    record Failed(String reason) implements JobState { }

    /** 已取消（终态）：人为终止，不可再迁移，防止「已完成又被拉回排队」。 */
    record Cancelled(String operator) implements JobState { }
}
