// project/src/aiplat/DatasetVersion.java —— 数据集版本台账 + 快照校验
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-proj src/aiplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package aiplat;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 数据集版本（主文档 3.6）：模型血缘的另一半。
 *
 * <p>为什么必须有校验和：训练任务「读到的数据」与「登记的版本」必须是同一份。
 * 没有校验和，数据集被就地覆盖后没人能发现——模型不可复现，而且这种事故往往在几个月后
 * 才以「指标对不上」的形式暴露。
 *
 * <p>特征版本的纪律同样落在这条台账上：训练与推理必须引用同一个 datasetVersion，
 * 否则就是 training-serving skew。
 */
public record DatasetVersion(String name, String version, String checksum, long rowCount, String createdBy) {

    public DatasetVersion {
        if (name == null || name.isBlank()) throw new IllegalArgumentException("数据集 name 必填");
        if (version == null || version.isBlank()) throw new IllegalArgumentException("数据集 version 必填");
        if (checksum == null || checksum.isBlank()) throw new IllegalArgumentException("checksum 必填：没有校验和就无法证明快照一致");
        if (rowCount < 0) throw new IllegalArgumentException("rowCount 不能为负");
    }

    /** 版本引用，模型血缘字段存的就是它（如 "nlp-corpus:1.0.0"）。 */
    public String ref() {
        return name + ":" + version;
    }

    /** 数据集版本台账：只追加，重复登记同一 ref 直接拒绝。 */
    public static final class Ledger {

        private final Map<String, DatasetVersion> byRef = new LinkedHashMap<>();

        public DatasetVersion register(DatasetVersion v) {
            if (byRef.putIfAbsent(v.ref(), v) != null) {
                throw new IllegalStateException("重复登记：数据集版本 " + v.ref() + " 已存在（版本号必须单调新增）");
            }
            return v;
        }

        public Optional<DatasetVersion> find(String name, String version) {
            return Optional.ofNullable(byRef.get(name + ":" + version));
        }

        /**
         * 快照校验：版本存在<b>且</b>校验和一致才通过。
         *
         * <p>未知版本也返回 false（fail-closed）：校验方法不该有「查不到就放过」的第三条路径。
         */
        public boolean verifySnapshot(String name, String version, String checksum) {
            return find(name, version).map(d -> d.checksum().equals(checksum)).orElse(false);
        }

        public List<DatasetVersion> all() {
            return List.copyOf(byRef.values());
        }

        public int size() {
            return byRef.size();
        }
    }
}
