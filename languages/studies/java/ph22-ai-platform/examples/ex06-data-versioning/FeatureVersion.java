// languages/java/ph22-ai-platform/examples/ex06-data-versioning/FeatureVersion.java —— 特征版本：特征集名 + 版本号 + 计算逻辑指纹（transformHash）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex06 *.java && java -cp /tmp/ph22-ex06 DataVersionDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）

/**
 * 为什么特征版本要两个字段：版本号管「何时改的」，transformHash 管「改了什么」。
 * 只升版本号不够——真正的 training-serving skew 常常来自「版本号没变、清洗/归一化逻辑被改了」，
 * 训练读旧逻辑、推理读新逻辑，线上指标悄悄漂移。所以两条都要比对（见 assertTrainServeConsistent）。
 */
public record FeatureVersion(String featureSet, String version, String transformHash) {

    public FeatureVersion {
        requireText(featureSet, "featureSet");
        requireText(version, "version");
        requireText(transformHash, "transformHash");
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " 不能为空");
        }
    }
}
