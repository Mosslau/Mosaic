// languages/java/ph22-ai-platform/examples/ex06-data-versioning/DatasetVersion.java —— 数据集版本台账条目：名字 + 版本 + 内容校验和 + 行数 + 产出者
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph22-ex06 *.java && java -cp /tmp/ph22-ex06 DataVersionDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：8/8 PASS）

/**
 * 数据集版本不是「一个目录」，而是台账里的一行。
 * 其中唯一有约束力的字段是 checksum：有了它，「训练任务当时读到的数据」与「台账登记的数据」
 * 才可比对，从而排除「数据被就地覆盖、实验再也跑不出来」这类事故（见 DataVersionRegistry.assertSnapshot）。
 * rowCount/createdBy 不参与判定，但它们是复盘时最先被问到的两列，所以一并留在台账里。
 */
public record DatasetVersion(String name, String version, String checksum, long rowCount, String createdBy) {

    public DatasetVersion {
        requireText(name, "name");
        requireText(version, "version");
        requireText(checksum, "checksum");
        requireText(createdBy, "createdBy");
        if (rowCount < 0) {
            throw new IllegalArgumentException("rowCount 不能为负：" + rowCount);
        }
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " 不能为空");
        }
    }
}
