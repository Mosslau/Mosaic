// exercises/sol-02-pool-quota/Sol02Demo.java —— 练习 2 验收入口：台账不变量 + 配额拒绝（而非排队）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol02 *.java && java -cp /tmp/ph22-sol02 Sol02Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：13/13 PASS）

/**
 * 对应 22-ai-platform.md 3.2（资源池台账）与 3.7（多租户配额）以及第 7 章练习 2。
 */
public final class Sol02Demo {

    private static int passed = 0;
    private static int total = 0;

    public static void main(String[] args) {
        GpuPool pool = new GpuPool(8);

        // ---- 1) 台账初值与不变量 ----
        check(pool.total() == 8 && pool.allocatedTotal() == 0 && pool.free() == 8 && pool.checkInvariant()
                        && pool.snapshot().isEmpty(),
                "初始台账：total=8 allocated=0 free=8，不变量 allocated+free==total 成立");

        // ---- 2) 正常分配 ----
        pool.allocate("job-a", 4);
        pool.allocate("job-b", 2);
        check(pool.allocatedTotal() == 6 && pool.free() == 2 && pool.checkInvariant(),
                "分配 4+2 卡后 allocated=6 free=2，不变量仍然成立");

        // ---- 3) 重复分配被拒（覆盖会把一张卡记成两次） ----
        boolean dupGuarded = false;
        String dupMessage = "";
        try {
            pool.allocate("job-a", 1);
        } catch (IllegalStateException e) {
            dupGuarded = true;
            dupMessage = e.getMessage();
        }
        check(dupGuarded && pool.allocatedTotal() == 6 && pool.checkInvariant(),
                "重复分配同一 jobId 被拒且账本不变：" + dupMessage);

        // ---- 4) 释放不存在的分配被拒 ----
        boolean releaseGuarded = false;
        String releaseMessage = "";
        try {
            pool.release("job-ghost");
        } catch (IllegalStateException e) {
            releaseGuarded = true;
            releaseMessage = e.getMessage();
        }
        check(releaseGuarded && pool.checkInvariant(),
                "释放不存在的分配被拒：" + releaseMessage);

        // ---- 5) 超量申请被拒且不部分占用 ----
        boolean overGuarded = false;
        try {
            pool.allocate("job-c", 4); // 空闲只有 2
        } catch (IllegalStateException e) {
            overGuarded = true;
        }
        check(overGuarded && pool.allocatedTotal() == 6 && pool.free() == 2 && pool.snapshot().size() == 2,
                "超量申请（4 卡 > 空闲 2 卡）被拒，账本保持原样（不部分占用）");

        // ---- 6) 回收后可复用 ----
        int reclaimed = pool.release("job-a");
        check(reclaimed == 4 && pool.allocatedTotal() == 2 && pool.free() == 6 && pool.checkInvariant()
                        && !pool.snapshot().containsKey("job-a"),
                "回收 job-a 归还 4 卡：free 2→6，持有者列表中已移除");

        // ---- 7) 租户配额：额度内准入 ----
        QuotaGuard guard = new QuotaGuard(new Quota(6, 2));
        AdmissionDecision ok = guard.reserve("team-nlp", 4);
        check(ok.granted() && guard.usedGpus("team-nlp") == 4,
                "配额额度内准入：team-nlp 已用 " + guard.usedGpus("team-nlp") + "/6（" + ok.reason() + "）");

        // ---- 8) 租户配额：超限拒绝且原因可读 ----
        AdmissionDecision denied = guard.reserve("team-nlp", 4);
        check(!denied.granted() && denied.reason().contains("配额不足") && denied.reason().contains("8/6")
                        && guard.usedGpus("team-nlp") == 4,
                "超限拒绝（4+4 > 6）：已用额度不变，原因为可读文案「" + denied.reason() + "」");

        // ---- 9) 拒绝而非排队 ----
        check(guard.pendingTotal() == 0 && guard.queuedJobs("team-nlp") == 0 && guard.rejections().size() == 1,
                "拒绝而非排队：被拒请求不进入任何等待队列（排队数=0，拒绝日志=" + guard.rejections().size() + " 条）");

        // ---- 10) 回收后额度归零 ----
        guard.release("team-nlp", 4);
        check(guard.usedGpus("team-nlp") == 0,
                "回收 4 卡后已用额度归零（0/6），配额账目与资源池同向变化");

        // ---- 11) 回收后可复用 ----
        AdmissionDecision reuse = guard.reserve("team-nlp", 6);
        check(reuse.granted() && reuse.usedAfter() == 6 && guard.usedGpus("team-nlp") == 6,
                "回收后可复用：释放后申请 6 卡（原先被拒的量级）变为满额准入（" + reuse.reason() + "）");

        // ---- 12) 排队任务数配额 ----
        boolean enq1 = guard.enqueue("team-nlp").granted();
        boolean enq2 = guard.enqueue("team-nlp").granted();
        AdmissionDecision enq3 = guard.enqueue("team-nlp");
        check(enq1 && enq2 && !enq3.granted() && enq3.reason().contains("排队")
                        && guard.queuedJobs("team-nlp") == 2,
                "排队配额 2 生效：第 3 个入队被拒（" + enq3.reason() + "）");

        // ---- 12) 释放超过持有量被拒 ----
        boolean overReleaseGuarded = false;
        try {
            guard.release("team-nlp", 8); // 仅持有 6
        } catch (IllegalStateException e) {
            overReleaseGuarded = true;
        }
        check(overReleaseGuarded && guard.usedGpus("team-nlp") == 6,
                "释放超过持有量（6 卡持有者释放 8 卡）被拒，配额账目不变");

        System.out.println("GPU 台账: " + pool);
        System.out.println("配额守卫: " + guard);
        System.out.println("拒绝日志: " + guard.rejections());
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
