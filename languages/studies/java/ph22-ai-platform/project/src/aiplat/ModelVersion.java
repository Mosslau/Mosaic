// project/src/aiplat/ModelVersion.java —— 模型版本：语义化版本 + 阶段 + 血缘
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

/**
 * 模型版本（主文档 3.4）：模型不是一堆文件，而是<b>带血缘的台账条目</b>。
 *
 * <p>四个字段各回答一个值班问题：
 * <ul>
 *   <li>{@code semver} —— 线上是哪个版本（语义化比较：2.10.0 &gt; 2.9.0，不能靠字符串比）；</li>
 *   <li>{@code datasetVersion} —— 用哪份数据训的（数据可追溯是模型可靠性的前提，3.6）；</li>
 *   <li>{@code jobId} —— 哪次训练产出的（通常存产物的 artifactId，能一路追回任务与审计）；</li>
 *   <li>{@code metric} —— 评估指标（晋级门槛的比较依据）。</li>
 * </ul>
 */
public record ModelVersion(String model, int major, int minor, int patch, Stage stage,
                           String datasetVersion, String jobId, double metric)
        implements Comparable<ModelVersion> {

    /** 版本阶段：唯一 PROD 是纪律，灰度期由推理服务的流量切换承担（3.5）。 */
    public enum Stage { STAGING, PROD, ARCHIVED }

    public ModelVersion {
        if (model == null || model.isBlank()) {
            throw new IllegalArgumentException("model 必填");
        }
        if (major < 0 || minor < 0 || patch < 0) {
            throw new IllegalArgumentException("语义化版本号不能为负");
        }
        if (stage == null) {
            throw new IllegalArgumentException("stage 必填");
        }
        if (Double.isNaN(metric) || Double.isInfinite(metric)) {
            throw new IllegalArgumentException("metric 必须是有限数值");
        }
    }

    /** 语义化版本文本，如 "2.10.0"。 */
    public String semver() {
        return major + "." + minor + "." + patch;
    }

    /** 全局唯一的版本引用，用于运维一屏与审计，如 "detector:2.10.0"。 */
    public String ref() {
        return model + ":" + semver();
    }

    public ModelVersion withStage(Stage next) {
        return new ModelVersion(model, major, minor, patch, next, datasetVersion, jobId, metric);
    }

    /** 按 (模型名, 主版本, 次版本, 修订号) 比较——字符串比较会让 "2.10.0" < "2.9.0"，是经典事故。 */
    @Override
    public int compareTo(ModelVersion o) {
        int c = model.compareTo(o.model);
        if (c != 0) return c;
        c = Integer.compare(major, o.major);
        if (c != 0) return c;
        c = Integer.compare(minor, o.minor);
        if (c != 0) return c;
        return Integer.compare(patch, o.patch);
    }
}
