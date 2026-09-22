// languages/java/ph22-ai-platform/examples/ex01-training-job/TrainingJobDemo.java —— 训练任务平台主入口：幂等提交 + 状态机 + 重试 + 审计
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex01 *.java && java -cp /tmp/ph22-ex01 TrainingJobDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 场景：一个租户提交 3 个训练任务，其中 1 个是客户端重试导致的重复提交；
// 任务 a 成功并登记产物，任务 b 被取消，任务 c 连续失败 2 次后第 3 次成功。
// 断言覆盖 3.1 的四条纪律：幂等提交、非法迁移拒绝、重试上限、终态不可变、审计完整。
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

public final class TrainingJobDemo {
    public static void main(String[] args) {
        // 提交侧：幂等键 → 任务 id，重复提交直接命中已有任务（不会重复扣配额）
        Map<String, String> byIdempotencyKey = new HashMap<>();
        Map<String, TrainingJob> jobs = new HashMap<>();
        AtomicInteger seq = new AtomicInteger();

        JobSpec specA = new JobSpec("acme", "llm-pretrain", 8, 5, 1_000L, 120);
        JobSpec specB = new JobSpec("acme", "embed-finetune", 1, 3, 1_100L, 20);
        JobSpec specC = new JobSpec("beta", "cv-train", 4, 4, 1_200L, 60);

        TrainingJob a1 = submit(byIdempotencyKey, jobs, seq, specA);
        TrainingJob a2 = submit(byIdempotencyKey, jobs, seq, specA);   // 同一意图重发
        TrainingJob b = submit(byIdempotencyKey, jobs, seq, specB);
        TrainingJob c = submit(byIdempotencyKey, jobs, seq, specC);

        // 任务 a：正常跑完并登记产物
        a1.start("gpu-node-1");
        a1.succeed("model:acme/llm-pretrain@1.0.0");

        // 任务 b：排队中被人工取消
        b.cancel("oncall-alice");

        // 任务 c：失败 → 重试 → 再失败 → 再重试 → 成功（attempt 1→2→3）
        c.start("gpu-node-2");
        c.fail("CUDA OOM at step 1200");
        c.retry("oncall-bob");
        c.start("gpu-node-3");
        c.fail("NCCL timeout");
        c.retry("oncall-bob");
        c.start("gpu-node-4");
        c.succeed("model:beta/cv-train@0.3.1");

        AtomicInteger pass = new AtomicInteger();

        // 1) 幂等提交：同 key 返回同一个对象，且只建了一个任务
        check(pass,
                a1 == a2 && a1.idempotencyKey().equals(a2.idempotencyKey()) && jobs.size() == 3,
                "幂等提交：同 tenant+name+specHash 返回同一任务，任务总数仍为 3");

        // 2) 非法迁移被拒：已成功的终态任务不能再 start / fail / retry
        boolean terminalRejected = false;
        try {
            a1.start("gpu-node-9");
        } catch (IllegalStateException e) {
            terminalRejected = true;
        }
        check(pass, terminalRejected, "SUCCEEDED 终态不可再迁移，start() 抛 IllegalStateException");

        // 3) FAILED 只能重试到 attempt 上限：第 3 次失败后再 retry 必须被拒
        JobSpec specD = new JobSpec("beta", "asr-train", 2, 4, 1_300L, 30);
        TrainingJob d = submit(byIdempotencyKey, jobs, seq, specD);
        d.start("gpu-node-5");
        d.fail("data shard corrupt");
        d.retry("oncall-bob");
        d.start("gpu-node-5");
        d.fail("data shard corrupt again");
        d.retry("oncall-bob");
        d.start("gpu-node-5");
        d.fail("third failure");
        boolean overLimit = false;
        try {
            d.retry("oncall-bob");
        } catch (IllegalStateException e) {
            overLimit = true;
        }
        check(pass, overLimit && d.attempt() == TrainingJob.MAX_ATTEMPT,
                "重试上限：2 次重试后 attempt=3，再 retry 被拒（上限 " + TrainingJob.MAX_ATTEMPT + "）");

        // 4) 非 FAILED 状态不允许重试：RUNNING 中调用 retry 会让两个执行体写同一产物
        JobSpec specE = new JobSpec("acme", "rerank-train", 2, 5, 1_400L, 45);
        TrainingJob e = submit(byIdempotencyKey, jobs, seq, specE);
        e.start("gpu-node-6");
        boolean runningRetryRejected = false;
        try {
            e.retry("oncall-bob");
        } catch (IllegalStateException ex) {
            runningRetryRejected = true;
        }
        check(pass, runningRetryRejected, "RUNNING 状态不允许 retry（只有 FAILED 可重试）");

        // 5) 终态不可变更：已取消的任务既不能开始也不能再取消
        boolean cancelledImmutable = false;
        try {
            b.cancel("oncall-alice");
        } catch (IllegalStateException ex) {
            cancelledImmutable = true;
        }
        check(pass, cancelledImmutable, "CANCELLED 终态不可再次取消，重复 cancel() 被拒");

        // 6) 重试 2 次后成功：attempt=3 且审计条数与迁移次数一致
        //    c 的迁移：submit、start、fail、retry、start、fail、retry、start、succeed = 9 条
        check(pass, c.attempt() == 3 && c.state() instanceof JobState.Succeeded
                        && c.audit().size() == 9,
                "失败任务重试 2 次后成功（attempt=3），审计 9 条 = 9 次迁移");

        // 7) 审计轨迹内容正确：from/to 首尾相接，且每条都有操作人
        boolean auditChained = true;
        for (int i = 1; i < c.audit().size(); i++) {
            if (!c.audit().get(i - 1).to().equals(c.audit().get(i).from())) {
                auditChained = false;
            }
        }
        check(pass, auditChained && c.audit().stream().allMatch(x -> x.operator() != null),
                "审计轨迹首尾相接且每条都记录操作人（谁把任务杀了可查）");

        System.out.println("== 任务 c 的审计轨迹（谁在什么时候把任务推到了哪个状态） ==");
        for (TrainingJob.AuditEntry entry : c.audit()) {
            System.out.printf("  %s  %-9s -> %-9s  reason=%s  by=%s%n",
                    entry.ts(), entry.from(), entry.to(), entry.reason(), entry.operator());
        }
        System.out.printf("ALL PASS: %d/7%n", pass.get());
    }

    /** 模拟应用服务层的提交入口：先查幂等键，命中就返回原任务。 */
    private static TrainingJob submit(Map<String, String> byKey, Map<String, TrainingJob> jobs,
                                      AtomicInteger seq, JobSpec spec) {
        String key = spec.tenant() + "/" + spec.name() + "/" + spec.contentHash();
        String existingId = byKey.get(key);
        if (existingId != null) {
            return jobs.get(existingId);
        }
        String id = "job-" + String.format("%03d", seq.incrementAndGet());
        TrainingJob job = new TrainingJob(id, spec);
        jobs.put(id, job);
        byKey.put(key, id);
        return job;
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
