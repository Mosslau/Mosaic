// languages/java/ph22-ai-platform/examples/ex04-model-registry/ModelVersion.java —— 模型版本：语义化版本 + 血缘 + 发布阶段
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex04 *.java && java -cp /tmp/ph22-ex04 ModelRegistryDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
//
// 为什么模型版本是「带血缘的台账条目」而不是一堆文件：
//   线上事故的第一问往往是「这个模型是哪次训练、用了哪份数据」——所以 datasetVersion
//   与 jobId 和版本号一样是必填字段，缺失就拒绝登记（见 ModelRegistry.register）。
// 为什么 compareTo 用语义化而不是字符串：字符串比较会得出 "2.10.0" < "2.9.0"，
//   于是「禁止版本倒退」的规则会被悄悄绕过；必须逐段比数值。
import java.util.Comparator;

/**
 * 一个模型版本的不可变台账条目。
 *
 * @param model          模型名（台账按此分区，同一模型的 PROD 唯一）
 * @param major/minor/patch 语义化版本号，逐段数值比较
 * @param stage          当前发布阶段：STAGING → PROD → ARCHIVED
 * @param datasetVersion 血缘：训练所用数据集版本（必填）
 * @param jobId          血缘：产出该版本的任务 id（必填）
 * @param metric         评估指标，数值越大越好（晋级门槛据此比较）
 */
public record ModelVersion(String model, int major, int minor, int patch, Stage stage,
                           String datasetVersion, String jobId, double metric)
        implements Comparable<ModelVersion> {

    /** 发布阶段。顺序即晋级方向：STAGING → PROD → ARCHIVED。 */
    public enum Stage { STAGING, PROD, ARCHIVED }

    public ModelVersion {
        if (model == null || model.isBlank()) {
            throw new IllegalArgumentException("model 必填");
        }
        if (stage == null) {
            throw new IllegalArgumentException("stage 必填");
        }
        if (major < 0 || minor < 0 || patch < 0) {
            throw new IllegalArgumentException(
                    "版本号不能为负: " + major + "." + minor + "." + patch);
        }
        if (datasetVersion == null || datasetVersion.isBlank()) {
            throw new IllegalArgumentException("血缘缺失：datasetVersion 必填");
        }
        if (jobId == null || jobId.isBlank()) {
            throw new IllegalArgumentException("血缘缺失：jobId 必填");
        }
    }

    public String tag() {
        return model + "@" + major + "." + minor + "." + patch;
    }

    /** 语义化比较：主版本 → 次版本 → 修订号逐段数值比较，最后用阶段保证全序。 */
    @Override
    public int compareTo(ModelVersion other) {
        return Comparator.comparingInt(ModelVersion::major)
                .thenComparingInt(ModelVersion::minor)
                .thenComparingInt(ModelVersion::patch)
                .thenComparing(v -> v.stage().ordinal())
                .compare(this, other);
    }

    /** 换个阶段（record 不可变，返回新实例——晋级是「登记新阶段」而不是改旧条目）。 */
    public ModelVersion withStage(Stage next) {
        return new ModelVersion(model, major, minor, patch, next, datasetVersion, jobId, metric);
    }
}
