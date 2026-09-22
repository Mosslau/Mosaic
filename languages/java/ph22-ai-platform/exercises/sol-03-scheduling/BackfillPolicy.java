// exercises/sol-03-scheduling/BackfillPolicy.java —— 优先级 + 回填：队头被卡时用小任务换利用率
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol03 *.java && java -cp /tmp/ph22-sol03 Sol03Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 回填（backfill）：如果队头任务放不下，就允许**放得下、且预估时长短于队头等待窗口**的小任务插队。
 *
 * 两条纪律（对应 22-ai-platform.md 4.1）：
 * ① 队头位置不变——回填只是「填空闲」，绝不把队头换成别的任务，也不把它从队列里移除；
 * ② 回填有边界——预估时长超过队头等待窗口（这里取队头自身的预估时长）的任务不允许插队，
 *    否则「回填」就变成了「推迟大任务」。预估不准是这项策略的固有代价。
 */
public final class BackfillPolicy implements Policy {

    @Override
    public String name() { return "PRIORITY+BACKFILL"; }

    @Override
    public List<String> select(List<SchedJob> queue, int freeGpus, Map<String, Integer> tenantUsed) {
        List<SchedJob> ordered = Policy.priorityOrder(queue);
        if (ordered.isEmpty()) {
            return List.of();
        }
        int free = freeGpus;
        List<String> selected = new ArrayList<>();
        SchedJob head = ordered.get(0);

        if (head.gpus() <= free) {
            // 队头放得下：先放队头（优先级得到尊重），剩余卡再按优先级贪心
            selected.add(head.id());
            free -= head.gpus();
            for (int i = 1; i < ordered.size(); i++) {
                SchedJob job = ordered.get(i);
                if (job.gpus() <= free) {
                    selected.add(job.id());
                    free -= job.gpus();
                }
            }
            return List.copyOf(selected);
        }

        // 队头被卡住：队头等待窗口 = 它自身的预估时长（这段时间里跑得完的小任务可以插队）
        long headWindowSeconds = head.estimatedSeconds();
        for (int i = 1; i < ordered.size(); i++) {
            SchedJob job = ordered.get(i);
            if (job.gpus() <= free && job.estimatedSeconds() <= headWindowSeconds) {
                selected.add(job.id());
                free -= job.gpus();
            }
        }
        return List.copyOf(selected);
    }
}
