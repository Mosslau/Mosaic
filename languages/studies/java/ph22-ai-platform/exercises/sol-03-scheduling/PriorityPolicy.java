// exercises/sol-03-scheduling/PriorityPolicy.java —— 优先级：高优先级先拿卡，同级 FIFO
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol03 *.java && java -cp /tmp/ph22-sol03 Sol03Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 优先级策略：优先级降序，同级按提交序号。
 * 与 FIFO 的差别只在**顺序**，不在「能不能凭空造出 GPU」——队头（此处为最高优先级任务）
 * 放不下时同样整轮停住。纯优先级会让低优先级饿死，工业做法是叠加等待时间老化与每租户配额。
 */
public final class PriorityPolicy implements Policy {

    @Override
    public String name() { return "PRIORITY"; }

    @Override
    public List<String> select(List<SchedJob> queue, int freeGpus, Map<String, Integer> tenantUsed) {
        int free = freeGpus;
        List<String> selected = new ArrayList<>();
        for (SchedJob job : Policy.priorityOrder(queue)) {
            if (job.gpus() > free) {
                break; // 高优先级大任务放不下时，后面的低优先级任务也要等
            }
            selected.add(job.id());
            free -= job.gpus();
        }
        return List.copyOf(selected);
    }
}
