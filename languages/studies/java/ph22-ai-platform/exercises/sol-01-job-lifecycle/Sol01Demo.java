// exercises/sol-01-job-lifecycle/Sol01Demo.java —— 练习 1 验收入口：状态机 + 幂等提交 + 重试上限 + 审计
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

/**
 * 对应 22-ai-platform.md 3.1（聚合根与状态机）与第 7 章练习 1。
 * 断言全部是「幂等 / 非法迁移 / 重试上限 / 审计一致性」四类纪律的可执行形式。
 */
public final class Sol01Demo {

    private static int passed = 0;
    private static int total = 0;

    public static void main(String[] args) {
        JobService service = new JobService(3);
        JobSpec spec = new JobSpec("team-nlp", "llm-sft", 4, "img/llm:1.0");

        // ---- 1) 幂等提交 ----
        TrainingJob first = service.submit(spec);
        TrainingJob second = service.submit(spec);
        check(first == second, "幂等提交：重复提交（同 tenant+name+specHash）返回同一任务实例 " + first.jobId());
        check(first.state() instanceof Queued && first.attempt() == 1 && first.auditSize() == 0,
                "新任务初始为 QUEUED、attempt=1、审计为空");

        TrainingJob other = service.submit(new JobSpec("team-nlp", "llm-sft", 8, "img/llm:1.0"));
        check(other != first && service.jobCount() == 2,
                "specHash 改变（4→8 卡）视为新任务：幂等键含 tenant+name+specHash，任务总数=" + service.jobCount());

        // ---- 2) 合法迁移链 + 审计一致性 ----
        first.transition(new Running(), "scheduler assigned 4 gpus", "scheduler");
        first.transition(new Failed("CUDA out of memory"), "exit code 137", "runner");
        check(first.state() instanceof Failed && first.auditSize() == 2,
                "合法迁移 QUEUED→RUNNING→FAILED 各写一条审计（2 条）");

        first.retry("operator-zhang");
        check(first.state() instanceof Queued && first.attempt() == 2 && first.auditSize() == 3,
                "FAILED→QUEUED 重试：attempt 1→2 且写审计（3 条）");

        first.transition(new Running(), "retry scheduled", "scheduler");
        first.transition(new Succeeded(), "exit code 0", "runner");
        check(first.state() instanceof Succeeded && first.auditSize() == 5,
                "迁移 5 次 → 审计恰好 5 条（条数与成功迁移次数一致）");

        // ---- 3) 非法迁移被拒且不写审计 ----
        boolean terminalGuarded = false;
        try {
            first.transition(new Queued(), "pull back finished job", "someone");
        } catch (IllegalStateException e) {
            terminalGuarded = true;
        }
        check(terminalGuarded && first.state() instanceof Succeeded && first.auditSize() == 5,
                "终态不可变：SUCCEEDED→QUEUED 被拒且审计仍为 5 条（被拒迁移不留痕）");

        boolean skipGuarded = false;
        String skipMessage = "";
        try {
            other.transition(new Succeeded(), "skip running", "someone");
        } catch (IllegalStateException e) {
            skipGuarded = true;
            skipMessage = e.getMessage();
        }
        check(skipGuarded && other.auditSize() == 0 && skipMessage.contains("QUEUED → SUCCEEDED"),
                "跳过 RUNNING 直接成功被拒：" + skipMessage);

        // ---- 4) 重试上限 3 ----
        TrainingJob flaky = service.submit(new JobSpec("team-cv", "detr-train", 2, "img/cv:2.1"));
        for (int i = 0; i < 3; i++) {
            flaky.transition(new Running(), "attempt " + flaky.attempt(), "scheduler");
            flaky.transition(new Failed("node lost"), "exit code 1", "runner");
            if (i < 2) {
                flaky.retry("operator-li");
            }
        }
        boolean capGuarded = false;
        String capMessage = "";
        try {
            flaky.retry("operator-li");
        } catch (IllegalStateException e) {
            capGuarded = true;
            capMessage = e.getMessage();
        }
        check(capGuarded && flaky.attempt() == 3 && flaky.state() instanceof Failed,
                "重试上限 3 生效：第 4 次重试被拒、attempt 停在 3（" + capMessage + "）");

        // ---- 5) 取消（终态）与审计可读性 ----
        TrainingJob cancelled = service.submit(new JobSpec("team-nlp", "llm-eval", 1, "img/llm:1.0"));
        cancelled.transition(new Cancelled("user cancelled"), "superseded by llm-sft rerun", "operator-wang");
        check(cancelled.state() instanceof Cancelled
                        && cancelled.audit().get(0).from().equals("QUEUED")
                        && cancelled.audit().get(0).to().equals("CANCELLED")
                        && cancelled.audit().get(0).operator().equals("operator-wang"),
                "QUEUED→CANCELLED 合法且审计记录 from/to/operator/reason");

        boolean auditComplete = service.all().stream()
                .allMatch(job -> job.audit().stream()
                        .allMatch(e -> !e.operator().isBlank() && !e.reason().isBlank() && e.at() != null));
        check(auditComplete && flaky.auditSize() == 8,
                "全部审计条目含时间/原因/operator；重试任务迁移 8 次 → 审计 8 条");

        System.out.println("任务台账: " + service.all());
        System.out.println("ALL PASS: " + passed + "/" + total);
        if (passed != total) {
            System.exit(1);
        }
    }

    private static void check(boolean ok, String label) {
        total++;
        if (ok) {
            passed++;
        }
        System.out.println((ok ? "PASS " : "FAIL ") + label);
    }
}
