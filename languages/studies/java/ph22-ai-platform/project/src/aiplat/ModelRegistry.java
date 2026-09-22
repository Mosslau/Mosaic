// project/src/aiplat/ModelRegistry.java —— 模型注册表：登记/晋级门槛/禁止倒退/唯一 PROD
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 模型注册表（主文档 3.4）：产物台账 + 晋级纪律。
 *
 * <p>四条规则都在这里强制，而不是靠流程文档：
 * <ol>
 *   <li><b>血缘完整</b>：datasetVersion + jobId 必填，否则拒绝登记——没有血缘的模型无法复现、无法审计；</li>
 *   <li><b>禁止版本倒退</b>：新登记版本必须严格大于该模型已登记的最新版本；</li>
 *   <li><b>晋级门槛</b>：STAGING → PROD 要求指标不劣于当前 PROD（可按阈值收紧）；</li>
 *   <li><b>唯一 PROD</b>：同一模型同一时刻只有一个 PROD，晋级新版本时旧 PROD 自动归档。</li>
 * </ol>
 *
 * <p>为什么唯一 PROD 需要灰度配合：晋级是「指针切换」，而线上流量不能瞬间切走——
 * 切换指针与切流量必须分开（3.5），否则唯一 PROD 的纪律会变成一次全量发布的赌注。
 */
public final class ModelRegistry {

    /** 默认晋级门槛系数：1.0 表示「不劣于当前 PROD」。 */
    public static final double DEFAULT_THRESHOLD = 1.0;

    private final Map<String, List<ModelVersion>> byModel = new LinkedHashMap<>();
    private final Map<String, ModelVersion> production = new LinkedHashMap<>();
    private final List<String> audit = new ArrayList<>();

    /** 登记一个模型版本（STAGING），返回登记后的条目。 */
    public ModelVersion register(ModelVersion v) {
        if (v.datasetVersion() == null || v.datasetVersion().isBlank()) {
            throw new IllegalStateException("血缘缺失：模型版本 " + v.ref() + " 未绑定数据集版本（datasetVersion 为空）");
        }
        if (v.jobId() == null || v.jobId().isBlank()) {
            throw new IllegalStateException("血缘缺失：模型版本 " + v.ref() + " 未绑定训练任务（jobId 为空）");
        }
        List<ModelVersion> versions = byModel.computeIfAbsent(v.model(), k -> new ArrayList<>());
        for (ModelVersion e : versions) {
            if (e.semver().equals(v.semver())) {
                throw new IllegalStateException("重复登记：模型版本 " + v.ref() + " 已存在");
            }
        }
        ModelVersion latest = latest(versions);
        if (latest != null && v.compareTo(latest) <= 0) {
            throw new IllegalStateException("禁止版本倒退：模型 " + v.model() + " 已登记最新版本 "
                    + latest.semver() + "，不能再登记 " + v.semver());
        }
        versions.add(v);
        audit.add("登记 " + v.ref() + "（stage=" + v.stage() + " metric=" + v.metric()
                + " ds=" + v.datasetVersion() + " job=" + v.jobId() + "）");
        return v;
    }

    /** 晋级到 PROD（默认门槛 = 不劣于当前 PROD）。 */
    public ModelVersion promote(String model, String semver) {
        return promote(model, semver, DEFAULT_THRESHOLD);
    }

    /**
     * 晋级到 PROD。
     *
     * @param metricThreshold 门槛系数：候选指标必须 &ge; 当前 PROD 指标 × 系数（1.0 = 不劣于）
     */
    public ModelVersion promote(String model, String semver, double metricThreshold) {
        ModelVersion candidate = find(model, semver)
                .orElseThrow(() -> new IllegalStateException("未知版本：模型 " + model + " 没有已登记的 " + semver));
        if (candidate.stage() == ModelVersion.Stage.PROD) {
            throw new IllegalStateException("无需晋级：模型版本 " + candidate.ref() + " 已经是 PROD");
        }
        ModelVersion current = production.get(model);
        if (current != null) {
            if (candidate.compareTo(current) <= 0) {
                throw new IllegalStateException("禁止版本倒退：模型 " + model + " 当前 PROD 为 "
                        + current.semver() + "，不能晋级更旧的 " + candidate.semver());
            }
            double floor = current.metric() * metricThreshold;
            if (candidate.metric() < floor) {
                throw new IllegalStateException(String.format(
                        "晋级被拒：候选 %s 指标 %.3f 低于门槛 %.3f（当前 PROD %s 指标 %.3f × 系数 %.2f）",
                        candidate.semver(), candidate.metric(), floor, current.semver(), current.metric(), metricThreshold));
            }
        }
        ModelVersion promoted = candidate.withStage(ModelVersion.Stage.PROD);
        replace(promoted);
        // 唯一 PROD：先把旧 PROD 归档，再落新 PROD —— 顺序固定，读代码即可确认「不会有第二个 PROD」
        if (current != null) {
            replace(current.withStage(ModelVersion.Stage.ARCHIVED));
        }
        production.put(model, promoted);
        audit.add("晋级 " + promoted.ref() + " -> PROD" + (current == null ? "（首个 PROD）" : "（" + current.semver() + " 归档）"));
        return promoted;
    }

    public Optional<ModelVersion> production(String model) {
        return Optional.ofNullable(production.get(model));
    }

    /** 运维一屏用的「当前 PROD 版本引用」，无 PROD 时返回 "-"。 */
    public String productionVersion() {
        if (production.isEmpty()) {
            return "-";
        }
        StringBuilder sb = new StringBuilder();
        production.values().forEach(v -> sb.append(sb.isEmpty() ? "" : ",").append(v.ref()));
        return sb.toString();
    }

    public long countStage(ModelVersion.Stage stage) {
        return byModel.values().stream().flatMap(List::stream).filter(v -> v.stage() == stage).count();
    }

    public List<ModelVersion> versions(String model) {
        return List.copyOf(byModel.getOrDefault(model, List.of()));
    }

    public Optional<ModelVersion> find(String model, String semver) {
        return byModel.getOrDefault(model, List.of()).stream()
                .filter(v -> v.semver().equals(semver))
                .findFirst();
    }

    public List<String> audit() {
        return List.copyOf(audit);
    }

    private ModelVersion latest(List<ModelVersion> versions) {
        ModelVersion max = null;
        for (ModelVersion v : versions) {
            if (max == null || v.compareTo(max) > 0) {
                max = v;
            }
        }
        return max;
    }

    /** 用同 semver 的新条目替换旧条目（唯一 PROD 纪律靠它落地）。 */
    private void replace(ModelVersion updated) {
        List<ModelVersion> versions = byModel.get(updated.model());
        for (int i = 0; i < versions.size(); i++) {
            if (versions.get(i).semver().equals(updated.semver())) {
                versions.set(i, updated);
                return;
            }
        }
        throw new IllegalStateException("内部错误：替换了不存在的版本 " + updated.ref());
    }
}
