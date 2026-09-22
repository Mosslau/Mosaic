// exercises/sol-01-job-lifecycle/JobService.java —— 幂等提交：IdempotencyKey 判重，重复提交返回原任务
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-sol01 *.java && java -cp /tmp/ph22-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：11/11 PASS）

import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 提交入口。客户端重试是常态，所以「按幂等键判重」必须发生在创建任务之前——
 * 重复提交返回同一个 TrainingJob 实例，而不是创建一个等价的新任务（否则会重复扣配额、重复排队）。
 */
public final class JobService {

    /** 重试上限 3：无上限重试会吃掉整个池子（见 22-ai-platform.md 3.1）。 */
    public static final int DEFAULT_MAX_ATTEMPTS = 3;

    private final Map<String, TrainingJob> byIdempotencyKey = new LinkedHashMap<>();
    private final Map<String, TrainingJob> byJobId = new LinkedHashMap<>();
    private final int maxAttempts;
    private int seq = 0;

    public JobService() {
        this(DEFAULT_MAX_ATTEMPTS);
    }

    public JobService(int maxAttempts) {
        this.maxAttempts = maxAttempts;
    }

    /** 幂等键 = tenant + name + specHash。 */
    public static String idempotencyKey(JobSpec spec) {
        return spec.tenant() + "|" + spec.name() + "|" + spec.specHash();
    }

    /** 提交任务：已见过同一幂等键则原样返回已有任务。 */
    public synchronized TrainingJob submit(JobSpec spec) {
        String key = idempotencyKey(spec);
        TrainingJob existing = byIdempotencyKey.get(key);
        if (existing != null) {
            return existing;
        }
        TrainingJob created = new TrainingJob("job-" + (++seq), spec, maxAttempts);
        byIdempotencyKey.put(key, created);
        byJobId.put(created.jobId(), created);
        return created;
    }

    public synchronized TrainingJob byId(String jobId) {
        TrainingJob job = byJobId.get(jobId);
        if (job == null) {
            throw new IllegalArgumentException("任务不存在: " + jobId);
        }
        return job;
    }

    public synchronized int jobCount() { return byJobId.size(); }

    public synchronized Collection<TrainingJob> all() {
        return Collections.unmodifiableCollection(new LinkedHashMap<>(byJobId).values());
    }
}
