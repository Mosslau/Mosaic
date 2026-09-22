// exercises/sol-01-job-lifecycle/JobState.java —— 训练任务状态机（sealed interface + 终态判定）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

/**
 * 训练任务生命周期：Queued → Running → Succeeded | Failed | Cancelled。
 * 用 sealed interface 表达「状态集合封闭」：任何新增状态都必须显式加入 permits，
 * 否则编译器直接拒绝（穷尽性由编译器兜底）。
 */
public sealed interface JobState permits Queued, Running, Succeeded, Failed, Cancelled {

    /** 稳定的状态名（审计与指标标签都用它，不依赖 toString）。 */
    String name();

    /** 终态不可变：Succeeded / Cancelled 之后不允许任何迁移。 */
    default boolean terminal() {
        return this instanceof Succeeded || this instanceof Cancelled;
    }
}
