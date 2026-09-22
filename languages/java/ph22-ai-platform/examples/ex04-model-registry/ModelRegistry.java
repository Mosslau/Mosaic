// languages/java/ph22-ai-platform/examples/ex04-model-registry/ModelRegistry.java —— 模型注册表：血缘校验 + 晋级门槛 + 唯一 PROD + 禁止倒退
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex04 *.java && java -cp /tmp/ph22-ex04 ModelRegistryDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
//
// 三条纪律集中在这里，因为它们都是「台账级」不变式，无法靠单个版本对象自证：
//   ① 禁止版本倒退：PROD 指针只能往更大的语义版本走——线上回退靠灰度（3.5），
//      不是靠把注册表指针拨回去；否则「当前线上是哪个版本」将无法解释。
//   ② 晋级有门槛：STAGING → PROD 要求指标不劣于当前 PROD（可配置阈值 MIN_IMPROVEMENT）。
//      没有门槛的注册表只是文件柜，「谁都能上」等于没有发布纪律。
//   ③ 唯一 PROD：同一模型同一时刻只有一个 PROD；旧 PROD 自动转 ARCHIVED，
//      保证 current(model) 永远只有一个答案。灰度期的多版本并存由 3.5 的流量切换处理。
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class ModelRegistry {
    /** 晋级最小指标增量：0 表示「不劣于当前 PROD」即可，>0 表示要求严格提升。 */
    public static final double MIN_IMPROVEMENT = 0.0;

    private final Map<String, ModelVersion> prod = new LinkedHashMap<>();
    private final Map<String, List<ModelVersion>> byModel = new LinkedHashMap<>();

    /**
     * 登记新版本：血缘（datasetVersion + jobId）缺失时由 ModelVersion 的构造器拒绝
     * （参数校验失败抛 IllegalArgumentException，而不是留下一条件「来历不明」的记录）。
     */
    public ModelVersion register(String model, int major, int minor, int patch,
                                 String datasetVersion, String jobId, double metric) {
        ModelVersion version = new ModelVersion(model, major, minor, patch,
                ModelVersion.Stage.STAGING, datasetVersion, jobId, metric);
        for (ModelVersion existing : byModel.getOrDefault(model, List.of())) {
            if (sameSemver(existing, version)) {
                throw new IllegalStateException(
                        "版本已登记: " + version.tag() + "（版本号必须唯一）");
            }
        }
        byModel.computeIfAbsent(model, k -> new ArrayList<>()).add(version);
        return version;
    }

    /**
     * 晋级到 PROD：要求候选版本存在、不是旧版本、指标达标。
     * 晋级成功时旧 PROD 自动转 ARCHIVED（唯一 PROD 的落地方式）。
     */
    public ModelVersion promote(String model, int major, int minor, int patch) {
        ModelVersion candidate = find(model, major, minor, patch)
                .orElseThrow(() -> new IllegalStateException("版本未登记: " + model + "@"
                        + major + "." + minor + "." + patch));
        if (candidate.stage() == ModelVersion.Stage.PROD) {
            throw new IllegalStateException("该版本已是 PROD: " + candidate.tag());
        }
        if (candidate.stage() == ModelVersion.Stage.ARCHIVED) {
            throw new IllegalStateException("ARCHIVED 版本不可晋级: " + candidate.tag());
        }
        ModelVersion currentProd = prod.get(model);
        if (currentProd != null && candidate.compareTo(currentProd) <= 0) {
            throw new IllegalStateException("禁止版本倒退/并列: 候选 " + candidate.tag()
                    + " 不高于当前 PROD " + currentProd.tag());
        }
        if (currentProd != null && candidate.metric() < currentProd.metric() + MIN_IMPROVEMENT) {
            throw new IllegalStateException("指标不达标: 候选 " + candidate.metric()
                    + " 劣于当前 PROD " + currentProd.metric());
        }
        if (currentProd != null) {
            replace(currentProd.withStage(ModelVersion.Stage.ARCHIVED));
        }
        ModelVersion promoted = candidate.withStage(ModelVersion.Stage.PROD);
        replace(promoted);
        prod.put(model, promoted);
        return promoted;
    }

    /** 归档：PROD 归档等于「下线当前线上版本」，必须把指针清掉，否则 current() 会说谎。 */
    public ModelVersion archive(String model, int major, int minor, int patch) {
        ModelVersion target = find(model, major, minor, patch)
                .orElseThrow(() -> new IllegalStateException("版本未登记: " + model + "@"
                        + major + "." + minor + "." + patch));
        if (target.stage() == ModelVersion.Stage.ARCHIVED) {
            throw new IllegalStateException("版本已是 ARCHIVED: " + target.tag());
        }
        ModelVersion archived = target.withStage(ModelVersion.Stage.ARCHIVED);
        replace(archived);
        if (target.stage() == ModelVersion.Stage.PROD) {
            prod.remove(model);
        }
        return archived;
    }

    public ModelVersion current(String model) {
        return prod.get(model);
    }

    /** 该模型的全部版本，按语义化版本升序（台账查询必须有序，否则「哪个更新」要靠人眼比）。 */
    public List<ModelVersion> versions(String model) {
        List<ModelVersion> list = new ArrayList<>(byModel.getOrDefault(model, List.of()));
        list.sort(Comparator.naturalOrder());
        return list;
    }

    private java.util.Optional<ModelVersion> find(String model, int major, int minor, int patch) {
        return byModel.getOrDefault(model, List.of()).stream()
                .filter(v -> v.major() == major && v.minor() == minor && v.patch() == patch)
                .findFirst();
    }

    /** 就地替换同版本号的条目（阶段变了，条目内容跟着变；版本号是它的唯一键）。 */
    private void replace(ModelVersion updated) {
        List<ModelVersion> list = byModel.get(updated.model());
        for (int i = 0; i < list.size(); i++) {
            if (sameSemver(list.get(i), updated)) {
                list.set(i, updated);
                return;
            }
        }
        throw new IllegalStateException("台账中找不到待更新版本: " + updated.tag());
    }

    private static boolean sameSemver(ModelVersion a, ModelVersion b) {
        return a.major() == b.major() && a.minor() == b.minor() && a.patch() == b.patch();
    }
}
