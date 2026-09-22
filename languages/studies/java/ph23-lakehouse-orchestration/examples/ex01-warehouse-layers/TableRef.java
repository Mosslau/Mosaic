// languages/java/ph23-lakehouse-orchestration/examples/ex01-warehouse-layers/TableRef.java —— 表的逻辑引用（表名 + 所在层）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex01 *.java && java -cp /tmp/ph23-ex01 WarehouseLayersDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 为什么把「层」放进表的标识里：分层不是命名约定，而是参与校验的语义。若 TableRef 只有表名，
// 依赖方向就得靠调用方额外传层参数，任何一处漏传都会让「反向依赖」绕过校验；把层并入引用后，
// addDependency 只用两个 TableRef 就能独立完成校验，纪律不可能被漏掉。
public record TableRef(String table, Layer layer) {

    public TableRef {
        if (table == null || table.isBlank()) {
            throw new IllegalArgumentException("table 必填");
        }
        if (layer == null) {
            throw new IllegalArgumentException("layer 必填");
        }
    }
}
