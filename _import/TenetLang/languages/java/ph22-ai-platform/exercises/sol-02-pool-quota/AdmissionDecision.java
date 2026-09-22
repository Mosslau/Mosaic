// exercises/sol-02-pool-quota/AdmissionDecision.java —— 配额准入结论（拒绝时携带可读原因）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol02 *.java && java -cp /tmp/ph22-sol02 Sol02Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：13/13 PASS）

/**
 * 准入结论。granted=false 时原因必须是「用户能读懂、能据此改动作」的一句话——
 * 例如「配额不足：GPU 8/6（已用 4，申请 4）」，而不是一个错误码。
 */
public record AdmissionDecision(boolean granted, String reason, String tenant, int requestedGpus, int usedAfter) {

    public static AdmissionDecision granted(String tenant, int gpus, int usedAfter, int maxGpus) {
        return new AdmissionDecision(true, "准入通过：GPU " + usedAfter + "/" + maxGpus, tenant, gpus, usedAfter);
    }

    public static AdmissionDecision denied(String tenant, int gpus, int usedAfter, String reason) {
        return new AdmissionDecision(false, reason, tenant, gpus, usedAfter);
    }

    @Override
    public String toString() {
        return (granted ? "GRANTED " : "DENIED  ") + tenant + " gpus=" + requestedGpus + " :: " + reason;
    }
}
