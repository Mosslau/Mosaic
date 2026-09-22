// languages/java/ph22-ai-platform/examples/ex01-training-job/JobSpec.java —— 任务不可变定义（提交后不再改）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex01 *.java && java -cp /tmp/ph22-ex01 TrainingJobDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 为什么把定义与生命周期拆开：JobSpec 是「用户提交的不可变意图」，TrainingJob 是
// 「平台维护的可变状态」。幂等键只由定义算出，所以同一份定义重复提交必然命中同一任务；
// 若把 gpuCount 这类字段放进可变部分，幂等语义就无从谈起。
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * 训练任务定义。
 *
 * @param tenant      租户（幂等键的一部分：不同租户可提交同名任务）
 * @param name        任务名（租户内用于幂等去重）
 * @param gpuCount    申请卡数
 * @param priority    调度权重，数值越大越优先
 * @param submitTs    提交时间（FIFO 的依据；显式传入而非取 now，保证示例可复现）
 * @param estMinutes  预估运行分钟数，供回填策略判断「插队任务能否在队头等待窗口内跑完」
 */
record JobSpec(String tenant, String name, int gpuCount, int priority, long submitTs,
               int estMinutes) {

    JobSpec {
        if (tenant == null || tenant.isBlank()) {
            throw new IllegalArgumentException("tenant 必填");
        }
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("name 必填");
        }
        if (gpuCount <= 0) {
            throw new IllegalArgumentException("gpuCount 必须为正: " + gpuCount);
        }
        if (estMinutes <= 0) {
            throw new IllegalArgumentException("estMinutes 必须为正: " + estMinutes);
        }
    }

    /**
     * 定义内容哈希：只取「影响资源与调度」的字段，submitTs 刻意排除在外——
     * 同一份意图晚一秒重发仍是同一次提交，否则客户端重试会重复扣配额。
     */
    String contentHash() {
        String canonical = tenant + "|" + name + "|" + gpuCount + "|" + priority + "|" + estMinutes;
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(canonical.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder();
            for (int i = 0; i < 8; i++) {          // 取前 8 字节足够做示例级指纹
                hex.append(String.format("%02x", digest[i]));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("JDK 必须提供 SHA-256", e);
        }
    }
}
