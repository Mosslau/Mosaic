// languages/java/ph23-lakehouse-orchestration/examples/ex04-compaction/DataFile.java —— 待合并的分区文件（与 ex03 同构：各自目录独立编译，不跨示例引用）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex04 *.java && java -cp /tmp/ph23-ex04 CompactionDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 为什么这里重新声明一份 DataFile 而不是复用 ex03 的类型：本阶段的每个示例都要求「独立目录、
// 独立编译、零依赖」，跨目录引用会把示例变成必须按顺序编译的整体，破坏「单目录一键复现」的验证纪律。
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
