// exercises/sol-03-scheduling/Sol03Demo.java —— 练习 3 验收入口：FIFO 队头阻塞 vs 优先级 + 回填的确定性决策
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol03 *.java && java -cp /tmp/ph22-sol03 Sol03Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 对应 22-ai-platform.md 3.3（可插拔调度策略）与 4.1（优先级、回填与抢占）以及第 7 章练习 3。
 * 两个场景：S1 = 队头被卡的 8 卡大任务（看队头阻塞与回填），S2 = 全部放得下（看优先级改变顺序）。
 */
public final class Sol03Demo {

    private static int passed = 0;
    private static int total = 0;

    public static void main(String[] args) {
        Policy fifo = new FifoPolicy();
        Policy priority = new PriorityPolicy();
        Policy backfill = new BackfillPolicy();
        Map<String, Integer> tenantUsed = new HashMap<>(Map.of("team-nlp", 0, "team-vision", 0));

        // ---- 场景 S1：池子只剩 4 卡，队头是 8 卡大任务 ----
        List<SchedJob> s1 = List.of(
                new SchedJob("train-llm",  "team-nlp",    10, 8, 1L, 900L),
                new SchedJob("eval-small", "team-vision",  5, 2, 2L, 600L),
                new SchedJob("train-detr", "team-vision",  4, 2, 3L, 3600L),
                new SchedJob("preprocess", "team-nlp",     3, 1, 4L, 300L));
        List<SchedJob> s1Snapshot = List.copyOf(s1);

        // ---- 场景 S2：8 卡全空闲，看顺序差异 ----
        List<SchedJob> s2 = List.of(
                new SchedJob("job-x", "team-nlp",    1, 2, 1L, 100L),
                new SchedJob("job-y", "team-nlp",    9, 2, 2L, 100L),
                new SchedJob("job-z", "team-vision", 5, 2, 3L, 100L));
        List<SchedJob> s2Snapshot = List.copyOf(s2);

        Map<String, Integer> tenantSnapshot = new HashMap<>(tenantUsed);

        // ---- 1) 确定性：同一输入必须重放出同一决策 ----
        check(fifo.select(s1, 4, tenantUsed).equals(fifo.select(s1, 4, tenantUsed)),
                "确定性：FIFO 对同一输入跑两遍，决策序列完全一致");
        check(priority.select(s1, 4, tenantUsed).equals(priority.select(s1, 4, tenantUsed))
                        && backfill.select(s1, 4, tenantUsed).equals(backfill.select(s1, 4, tenantUsed)),
                "确定性：PRIORITY 与 PRIORITY+BACKFILL 同样可重放（无随机、无时钟）");

        // ---- 2) FIFO 队头阻塞 ----
        List<String> fifoOnS1 = fifo.select(s1, 4, tenantUsed);
        check(fifoOnS1.isEmpty(),
                "FIFO 队头阻塞：队头 train-llm 要 8 卡而空闲只有 4 卡 → 本轮不放行任何任务（释放 " + fifoOnS1 + "）");
        check(s1.equals(s1Snapshot) && s1.get(0).id().equals("train-llm") && s1.size() == 4,
                "队头未被跳过也未被移除：队列保持提交顺序与长度（纯函数不改输入）");

        List<String> priorityOnS1 = priority.select(s1, 4, tenantUsed);
        check(priorityOnS1.isEmpty(),
                "优先级不改变物理约束：最高优先级的 train-llm 放不下时，PRIORITY 同样整轮停住");

        // ---- 3) 回填：利用空闲卡，不挤队头 ----
        List<String> backfillOnS1 = backfill.select(s1, 4, tenantUsed);
        check(backfillOnS1.equals(List.of("eval-small", "preprocess")),
                "回填利用空闲卡：放行 " + backfillOnS1 + "（FIFO/PRIORITY 此时都在空等）");
        check(!backfillOnS1.contains("train-llm") && !backfillOnS1.contains("train-detr"),
                "回填不挤队头：队头 train-llm 未入选；预估 3600s > 队头等待窗口 900s 的 train-detr 也被排除");

        int usedCards = backfillOnS1.stream().mapToInt(id -> gpusOf(s1, id)).sum();
        check(usedCards == 3 && usedCards <= 4,
                "回填把 4 张空闲卡用掉 " + usedCards + " 张（3/4），且不超发、不改变队头的等待位置");

        // ---- 4) 优先级改变顺序 ----
        List<String> fifoOnS2 = fifo.select(s2, 8, tenantUsed);
        List<String> priorityOnS2 = priority.select(s2, 8, tenantUsed);
        check(fifoOnS2.equals(List.of("job-x", "job-y", "job-z")) && priorityOnS2.equals(List.of("job-y", "job-z", "job-x")),
                "优先级改变顺序：FIFO=" + fifoOnS2 + "，PRIORITY=" + priorityOnS2 + "（同级仍按提交序）");
        check(!fifoOnS2.equals(priorityOnS2) && priorityOnS2.get(0).equals("job-y"),
                "决策差异可复现：两种策略的首个放行任务不同，PRIORITY 队首是优先级最高的 job-y");

        // ---- 5) 队头放得下时回填退化为优先级策略 ----
        List<String> backfillOnS2 = backfill.select(s2, 8, tenantUsed);
        check(backfillOnS2.equals(priorityOnS2) && backfillOnS2.get(0).equals("job-y"),
                "队头放得下时回填不插队：结果与 PRIORITY 一致 " + backfillOnS2 + "，队头优先入选");

        // ---- 6) 纯函数：入参零副作用 ----
        check(s1.equals(s1Snapshot) && s2.equals(s2Snapshot) && tenantUsed.equals(tenantSnapshot),
                "三个策略均为纯函数：队列顺序与租户占用在 9 次决策后逐项未变");

        // ---- 7) 边界 ----
        check(fifo.select(s1, 0, tenantUsed).isEmpty()
                        && priority.select(s1, 0, tenantUsed).isEmpty()
                        && backfill.select(s1, 0, tenantUsed).isEmpty(),
                "空闲 0 卡时三策略均返回空集（不产生越权决策）");
        check(fifo.select(List.of(), 4, tenantUsed).isEmpty()
                        && priority.select(List.of(), 4, tenantUsed).isEmpty()
                        && backfill.select(List.of(), 4, tenantUsed).isEmpty(),
                "空队列时三策略均不产生决策");

        System.out.println("S1 队列: " + s1);
        System.out.println("S1 决策: FIFO=" + fifoOnS1 + " | PRIORITY=" + priorityOnS1 + " | BACKFILL=" + backfillOnS1);
        System.out.println("S2 队列: " + s2);
        System.out.println("S2 决策: FIFO=" + fifoOnS2 + " | PRIORITY=" + priorityOnS2 + " | BACKFILL=" + backfillOnS2);
        System.out.println("ALL PASS: " + passed + "/" + total);
        if (passed != total) {
            System.exit(1);
        }
    }

    private static int gpusOf(List<SchedJob> queue, String id) {
        return queue.stream().filter(j -> j.id().equals(id)).findFirst().orElseThrow().gpus();
    }

    private static void check(boolean ok, String label) {
        total++;
        if (ok) {
            passed++;
        }
        System.out.println((ok ? "PASS " : "FAIL ") + label);
    }
}
