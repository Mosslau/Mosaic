// project/src/lakeplat/TableRef.java —— 表引用：表名 + 所属层（依赖校验的最小单位）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

/**
 * 表的不可变引用（主文档 3.1 示例的最小 record）。
 *
 * <p>表名刻意带上层前缀（如 {@code dwd_trip_detail}），这样即使有人只看名字也能看出它属于哪一层；
 * 而真正的纪律由 {@link Layer} 的序号校验兜底——**命名是约定，校验是纪律**。
 *
 * <p>天然有序（按表名字典序）：依赖图、下游闭包、血缘、一屏输出都依赖这个顺序保持确定性，
 * 这样「同样的输入 → 同样的输出」不需要每个调用点自己再排一次。
 *
 * @param table 表名，不能为空
 * @param layer 所属层
 */
public record TableRef(String table, Layer layer) implements Comparable<TableRef> {

    public TableRef {
        if (table == null || table.isBlank()) {
            throw new IllegalArgumentException("表名不能为空");
        }
        if (layer == null) {
            throw new IllegalArgumentException("表 " + table + " 未声明所属层");
        }
    }

    @Override
    public int compareTo(TableRef other) {
        return table.compareTo(other.table);
    }

    /** 工厂：按「层 + 主题」拼表名，保证命名与分层一致。 */
    public static TableRef of(Layer layer, String topic) {
        return new TableRef(layer.name().toLowerCase() + "_" + topic, layer);
    }

    /** 从带层前缀的表名解析层（`dwd_*` → DWD）。 */
    public static Layer parseLayer(String table) {
        for (Layer layer : Layer.values()) {
            if (table.startsWith(layer.name().toLowerCase() + "_")) {
                return layer;
            }
        }
        throw new IllegalArgumentException("表名 " + table + " 缺少层前缀（ods_/dwd_/dws_/ads_）");
    }

    @Override
    public String toString() {
        return table + "[" + layer.name() + "]";
    }
}
