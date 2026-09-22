// languages/java/ph22-ai-platform/examples/ex06-data-versioning/DataVersionRegistry.java —— 数据集/特征版本台账：登记纪律 + 查询 + 一致性断言
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex06 *.java && java -cp /tmp/ph22-ex06 DataVersionDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 版本台账的三条纪律（都是「把不可复现挡在登记口」而不是事后排查）：
 *   ① 同一 (name, version) 只能对应一个 checksum——否则「v3 到底是哪份数据」会有两个答案；
 *   ② 版本号单调递增——防止有人用旧版本号覆盖已经在跑的线上数据集；
 *   ③ 一致性必须能被主动断言——快照一致与训练/推理特征一致都是 assert 方法，靠人肉 review 必然漏。
 * 重复登记同一 (版本, 校验和) 是幂等的：客户端重试是常态，返回台账原条目即可，不该报错、也不该重复追加。
 */
public final class DataVersionRegistry {

    private final Map<String, List<DatasetVersion>> datasets = new LinkedHashMap<>();
    private final Map<String, FeatureVersion> features = new LinkedHashMap<>();

    /** 登记数据集版本；返回台账中的权威条目（重复登记时返回原有条目）。 */
    public synchronized DatasetVersion registerDataset(DatasetVersion next) {
        List<DatasetVersion> history = datasets.get(next.name());
        if (history == null) {
            history = new ArrayList<>();
            datasets.put(next.name(), history);
        }
        for (DatasetVersion old : history) {
            if (old.version().equals(next.version())) {
                if (!old.checksum().equals(next.checksum())) {
                    throw new IllegalStateException("数据集版本冲突：" + next.name() + " " + next.version()
                            + " 已登记 checksum=" + old.checksum() + "，本次 checksum=" + next.checksum()
                            + "（同一版本号不允许两种内容，否则无法复现）");
                }
                return old;   // 幂等：同版本同内容 → 返回台账原条目
            }
        }
        if (!history.isEmpty()) {
            DatasetVersion latest = history.get(history.size() - 1);
            if (versionOrdinal(next.version()) <= versionOrdinal(latest.version())) {
                throw new IllegalStateException("数据集版本必须单调递增：" + next.name()
                        + " 已登记到 " + latest.version() + "，不能登记 " + next.version());
            }
        }
        history.add(next);
        return next;
    }

    /** 登记特征版本；同一版本号不允许偷偷改计算逻辑（改逻辑必须升版本，否则就是 skew 的温床）。 */
    public synchronized FeatureVersion registerFeature(FeatureVersion next) {
        FeatureVersion old = features.get(next.featureSet());
        if (old != null && old.version().equals(next.version()) && !old.transformHash().equals(next.transformHash())) {
            throw new IllegalStateException("特征版本冲突：" + next.featureSet() + " " + next.version()
                    + " 的 transformHash 被改过（" + old.transformHash() + " → " + next.transformHash()
                    + "）：改计算逻辑必须升级版本号，否则训练/推理会读到不同特征");
        }
        features.put(next.featureSet(), next);
        return next;
    }

    /** 快照一致性：任务实际读到的 checksum 必须与登记版本一致，否则拒绝（数据被就地覆盖了）。 */
    public void assertSnapshot(DatasetVersion expected, String actualChecksum) {
        if (!expected.checksum().equals(actualChecksum)) {
            throw new IllegalStateException("快照不一致：" + expected.name() + " " + expected.version()
                    + " 登记 checksum=" + expected.checksum() + "，实际读到 checksum=" + actualChecksum
                    + "（数据被就地覆盖，本次训练结果不可复现）");
        }
    }

    /**
     * 训练-推理一致性（training-serving skew 防护）：特征集、版本号、计算逻辑指纹三者全等才放行。
     * 只比版本号会漏掉「版本号没变但逻辑改了」，只比 transformHash 会漏掉「逻辑一样但版本跨越了回填」，
     * 所以三项都要比。
     */
    public void assertTrainServeConsistent(FeatureVersion train, FeatureVersion serve) {
        if (!train.featureSet().equals(serve.featureSet())) {
            throw new IllegalStateException("特征集不一致：train=" + train.featureSet() + " serve=" + serve.featureSet());
        }
        if (!train.version().equals(serve.version())) {
            throw new IllegalStateException("训练/推理特征版本不一致（training-serving skew）：train=" + train.version()
                    + " serve=" + serve.version() + "，特征集=" + train.featureSet());
        }
        if (!train.transformHash().equals(serve.transformHash())) {
            throw new IllegalStateException("训练/推理特征计算逻辑不一致（training-serving skew）：transformHash train="
                    + train.transformHash() + " serve=" + serve.transformHash()
                    + "（版本号相同也不放行，逻辑变了必须升版本）");
        }
    }

    /** 按 (name, version) 精确查询。 */
    public synchronized Optional<DatasetVersion> dataset(String name, String version) {
        List<DatasetVersion> history = datasets.getOrDefault(name, List.of());
        return history.stream().filter(v -> v.version().equals(version)).findFirst();
    }

    /** 按名字取全部历史（登记顺序 = 版本递增顺序，可直接拿去复盘）。 */
    public synchronized List<DatasetVersion> history(String name) {
        return List.copyOf(datasets.getOrDefault(name, List.of()));
    }

    public synchronized Optional<FeatureVersion> feature(String featureSet) {
        return Optional.ofNullable(features.get(featureSet));
    }

    /** 版本号形如 v1/v2/v3（也接受纯数字）；比较必须按数值，字符串比较会得出 "v10" < "v9"。 */
    static int versionOrdinal(String version) {
        String digits = version.startsWith("v") || version.startsWith("V") ? version.substring(1) : version;
        try {
            return Integer.parseInt(digits);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("版本号形如 v1/v2/v3，无法比较：" + version);
        }
    }
}
