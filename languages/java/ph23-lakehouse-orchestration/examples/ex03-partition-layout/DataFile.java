// languages/java/ph23-lakehouse-orchestration/examples/ex03-partition-layout/DataFile.java —— 分区内的一个数据文件（物理布局的最小单位）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex03 *.java && java -cp /tmp/ph23-ex03 PartitionLayoutDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 为什么把 partition 单独存成字段而不是「从 path 里解析」：分区是查询裁剪的判据，必须是一等元数据。
// 从路径字符串反解分区，等于把布局约定写死在代码里——一旦目录规范变了（或大小写/补零不一致），
// 裁剪就会静默失效，查询变成全表扫描而没人发现。
public record DataFile(String path, String partition, long rows, long bytes) {

    public DataFile {
        if (path == null || path.isBlank()) {
            throw new IllegalArgumentException("path 必填");
        }
        if (partition == null || partition.isBlank()) {
            throw new IllegalArgumentException("partition 必填");
        }
        if (rows < 0) {
            throw new IllegalArgumentException("rows 不能为负: " + rows);
        }
        if (bytes < 0) {
            throw new IllegalArgumentException("bytes 不能为负: " + bytes);
        }
    }
}
