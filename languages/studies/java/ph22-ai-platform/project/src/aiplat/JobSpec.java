// project/src/aiplat/JobSpec.java —— 训练任务的不可变定义 + 幂等键
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

/**
 * 一次训练提交的「不可变定义」（主文档 3.1）：任务是什么、要多少卡、多急、多久。
 *
 * <p>为什么把定义与生命周期拆开：定义不可变，生命周期才有唯一权威的解释——
 * 「这个任务被改小了」这类事永远不该发生，要改就重新提交一个新 spec。
 *
 * <p>为什么幂等键不含 submitTs：客户端重发时时间戳几乎一定会变（重试发生在几秒后），
 * 但业务意图完全一样。幂等键只认业务定义（租户 + 名称 + 规格），这样重发才能真正被识别为重复。
 */
public record JobSpec(String tenant, String name, int gpuCount, int priority, int estMinutes, long submitTs) {

    /** 紧凑构造器：不可变定义要在入口挡住脏数据，否则脏数据会流进台账与配额计算。 */
    public JobSpec {
        if (tenant == null || tenant.isBlank()) {
            throw new IllegalArgumentException("tenant 必填：多租户平台没有「无主任务」");
        }
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("name 必填：幂等键与产物路径都依赖它");
        }
        if (gpuCount <= 0) {
            throw new IllegalArgumentException("gpuCount 必须为正：0 卡任务不该进 GPU 队列");
        }
        if (priority < 0) {
            throw new IllegalArgumentException("priority 不能为负：负优先级需要老化规则兜底，本阶段不引入");
        }
        if (estMinutes <= 0) {
            throw new IllegalArgumentException("estMinutes 必须为正：回填策略靠它判断「插队是否推迟队头」");
        }
    }

    /** 调度与产物命名用的人类可读标识。 */
    public String ref() {
        return tenant + "/" + name;
    }

    /**
     * 幂等键 = 租户 + 名称 + 规格指纹（主文档 3.1）。
     *
     * <p>用显式 FNV-1a 而不是 String.hashCode：FNV 的算法写在代码里、跨进程跨版本稳定，
     * 而 hashCode 是实现细节（虽然当前稳定），审计与对账不该依赖它。
     */
    public String idempotencyKey() {
        return tenant + "/" + name + "/" + specHash();
    }

    /** 规格指纹：把决定「是不是同一个任务」的字段按固定顺序拼成规范串后哈希。 */
    public String specHash() {
        String canonical = tenant + "|" + name + "|" + gpuCount + "|" + priority + "|" + estMinutes;
        long h = 0xcbf29ce484222325L;          // FNV-1a 64 位偏移基
        for (int i = 0; i < canonical.length(); i++) {
            h ^= canonical.charAt(i);
            h *= 0x100000001b3L;               // FNV 素数
        }
        return Long.toHexString(h);
    }
}
