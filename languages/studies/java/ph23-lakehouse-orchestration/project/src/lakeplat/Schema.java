// project/src/lakeplat/Schema.java —— 表 schema 的列定义（schema 演进兼容性的校验对象）
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 列式 schema（主文档 3.2 的 schema 演进校验对象）。
 *
 * <p>用有序 map 而不是无序集合，因为「哪一列被删、哪一列类型改了」的报错必须逐列可读——
 * 表格式层若允许静默通过，错误会推迟到下游任务运行时才炸，而那时数据可能已经被写进 ADS。
 */
public record Schema(Map<String, String> columns) {

    public Schema {
        columns = java.util.Collections.unmodifiableMap(new LinkedHashMap<>(columns));
    }

    /** 便捷构造：`col:type` 交替传入。 */
    public static Schema of(String... columnAndType) {
        if (columnAndType.length % 2 != 0) {
            throw new IllegalArgumentException("schema 必须按 (列名, 类型) 成对给出");
        }
        Map<String, String> map = new LinkedHashMap<>();
        for (int i = 0; i < columnAndType.length; i += 2) {
            map.put(columnAndType[i], columnAndType[i + 1]);
        }
        return new Schema(map);
    }

    /** 在末尾追加列（`ALTER TABLE ADD COLUMN` 语义）。 */
    public Schema plus(String column, String type) {
        Map<String, String> map = new LinkedHashMap<>(columns);
        if (map.containsKey(column)) {
            throw new IllegalStateException("列已存在：" + column);
        }
        map.put(column, type);
        return new Schema(map);
    }

    /** 去掉一列（用于演示不兼容变更被拒）。 */
    public Schema minus(String column) {
        Map<String, String> map = new LinkedHashMap<>(columns);
        if (map.remove(column) == null) {
            throw new IllegalStateException("列不存在：" + column);
        }
        return new Schema(map);
    }

    /** 改一列的类型（用于演示不兼容变更被拒）。 */
    public Schema withType(String column, String type) {
        Map<String, String> map = new LinkedHashMap<>(columns);
        if (!map.containsKey(column)) {
            throw new IllegalStateException("列不存在：" + column);
        }
        map.put(column, type);
        return new Schema(map);
    }

    public List<String> names() {
        return List.copyOf(columns.keySet());
    }

    public boolean has(String column) {
        return columns.containsKey(column);
    }

    /** 紧凑展示：`event_id:long, instance_id:string, ...`。 */
    public String label() {
        List<String> parts = new ArrayList<>();
        columns.forEach((column, type) -> parts.add(column + ":" + type));
        return String.join(", ", parts);
    }
}
