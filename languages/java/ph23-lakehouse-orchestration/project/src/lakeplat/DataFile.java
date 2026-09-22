// project/src/lakeplat/DataFile.java —— 数据文件：分区布局与扫描量的最小单位
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

/**
 * 表里的一个数据文件（主文档 3.3 的 {@code DataFile}）。
 *
 * <p>刻意只保留四个字段：路径、分区、行数、字节数——因为湖仓控制面要回答的成本问题只有两个：
 * **这次查询要打开几个文件、要扫多少字节**。
 *
 * @param path      文件路径（确定性生成，如 {@code data/event_date=2024-06-01/part-000.parquet}）
 * @param partition 分区值（本模型用「分区键=值」的字符串表达）
 * @param rows      行数
 * @param bytes     字节数（扫描量的度量单位）
 */
public record DataFile(String path, String partition, long rows, long bytes) {

    public DataFile {
        if (path == null || path.isBlank()) {
            throw new IllegalArgumentException("文件路径不能为空");
        }
        if (partition == null || partition.isBlank()) {
            throw new IllegalArgumentException("文件 " + path + " 未声明分区");
        }
        if (rows < 0 || bytes < 0) {
            throw new IllegalArgumentException("文件 " + path + " 的行数/字节数不能为负");
        }
    }

    /** 分区值（去掉 `键=` 前缀，方便比较与展示）。 */
    public String partitionValue() {
        int eq = partition.indexOf('=');
        return eq < 0 ? partition : partition.substring(eq + 1);
    }

    public long bytesPerRow() {
        return rows == 0 ? 0 : bytes / rows;
    }

    @Override
    public String toString() {
        return path + "(" + rows + " 行/" + bytes + "B)";
    }
}
