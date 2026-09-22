// project/src/aiplat/Policy.java —— 调度策略接口：可插拔、可解释、确定性
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.List;

/**
 * 调度策略（主文档 3.3）：引擎不变，策略可换（与 ph21 的 SPI 规则引擎同思路）。
 *
 * <p>为什么接口签名里没有「运行中任务」：本阶段的策略是<b>纯函数</b>——
 * 同一输入必须给出同一决策，否则「为什么昨天那批任务排了 6 小时」无法复盘。
 * 一次只做「这一轮让谁跑」的决策，把抢占/老化这类跨轮次机制留给扩展方向。
 *
 * <p>{@link Candidate} 是策略的输入视图：只暴露决策需要的字段（规格 + 入队时间），
 * 不把可变聚合根（{@link TrainingJob}）交给策略——策略不该能改任务状态。
 */
public interface Policy {

    /** 策略名，用于审计与指标标签。 */
    String name();

    /**
     * 从排队任务中选出本轮可运行的任务 id（按执行顺序）。
     *
     * @param queue    排队任务（调用方按入队顺序给出）
     * @param freeGpus 当前空闲卡数
     * @return 选中的任务 id 列表；总卡数不会超过 freeGpus
     */
    List<String> select(List<Candidate> queue, int freeGpus);

    /** 调度候选：任务的只读决策视图。 */
    record Candidate(String jobId, JobSpec spec, long enqueueTs) { }
}
