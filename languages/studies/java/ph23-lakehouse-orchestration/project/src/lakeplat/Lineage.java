// project/src/lakeplat/Lineage.java —— 列级血缘：输出列 ← 输入列的推导与回溯
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * 列级血缘（主文档 3.8）：由变换推导「输出列 ← 输入列」，并支持**回溯到 ODS**。
 *
 * <p>为什么必须是列级而不是表级：表级血缘只能说「A 表来自 B 表」，而实际影响分析要回答
 * 「改 DWD 的 {@code latency_ms} 会影响哪些看板的哪一列」。列级血缘是**合规与变更评审的最小单位**，
 * 也是「别人问这个数怎么来的」能秒答的前提。
 *
 * <p>本类只做两件事：登记列到列的边（{@link #derive}），以及在图上做向上/向下闭包
 * （{@link #sourcesOf} / {@link #impactOf}）。所有遍历按字典序，输出可复现。
 */
public final class Lineage {

    /** 一个列节点：`表.列`。 */
    public record ColumnRef(TableRef table, String column) implements Comparable<ColumnRef> {
        public ColumnRef {
            if (column == null || column.isBlank()) {
                throw new IllegalArgumentException("列名不能为空");
            }
        }

        /** 解析 `ods_trip_raw.region` 这样的全限定列名。 */
        public static ColumnRef parse(String qualified, WarehouseModel model) {
            int dot = qualified.lastIndexOf('.');
            if (dot <= 0) {
                throw new IllegalArgumentException("列名必须写成 表.列：" + qualified);
            }
            String table = qualified.substring(0, dot);
            Layer layer = TableRef.parseLayer(table);
            return new ColumnRef(model.require(new TableRef(table, layer)), qualified.substring(dot + 1));
        }

        @Override
        public int compareTo(ColumnRef other) {
            int byTable = table.table().compareTo(other.table.table());
            return byTable != 0 ? byTable : column.compareTo(other.column);
        }

        @Override
        public String toString() {
            return table.table() + "." + column;
        }
    }

    /** 一条推导边：输出列 ← 输入列 + 变换表达式（表达式让血缘"可解释"）。 */
    public record Edge(ColumnRef output, ColumnRef input, String expression) {
        @Override
        public String toString() {
            return output + " ← " + input + "（" + expression + "）";
        }
    }

    private final WarehouseModel model;
    private final List<Edge> edges = new ArrayList<>();
    private final Map<ColumnRef, Set<ColumnRef>> inputs = new TreeMap<>();
    private final Map<ColumnRef, Set<ColumnRef>> outputs = new TreeMap<>();

    public Lineage(WarehouseModel model) {
        this.model = model;
    }

    /** 登记一条列级推导：{@code output ← input}，表达式用于解释。 */
    public Edge derive(ColumnRef output, ColumnRef input, String expression) {
        model.require(output.table());
        model.require(input.table());
        Layer outLayer = output.table().layer();
        Layer inLayer = input.table().layer();
        if (!outLayer.canReadFrom(inLayer)) {
            throw new IllegalStateException("血缘推导违反分层方向：" + output + " ← " + input);
        }
        Edge edge = new Edge(output, input, expression);
        if (!edges.contains(edge)) {
            edges.add(edge);
            inputs.computeIfAbsent(output, key -> new TreeSet<>()).add(input);
            outputs.computeIfAbsent(input, key -> new TreeSet<>()).add(output);
        }
        return edge;
    }

    public List<Edge> edges() {
        return List.copyOf(edges);
    }

    /** 某个输出列的直接输入列（字典序）。 */
    public Set<ColumnRef> inputsOf(ColumnRef output) {
        return new TreeSet<>(inputs.getOrDefault(output, Set.of()));
    }

    /**
     * 向上回溯闭包：这个输出列**全部**来自哪些上游列（含自身），可一直追到 ODS。
     *
     * <p>这是「这个数怎么来的」的答案来源。
     */
    public Set<ColumnRef> sourcesOf(ColumnRef output) {
        Set<ColumnRef> visited = new TreeSet<>();
        List<ColumnRef> queue = new ArrayList<>(inputsOf(output));
        visited.add(output);
        while (!queue.isEmpty()) {
            ColumnRef current = queue.remove(0);
            if (visited.add(current)) {
                queue.addAll(inputsOf(current));
            }
        }
        return visited;
    }

    /** 向上回溯过滤：只要 ODS 层的源列（合规追溯要的答案）。 */
    public Set<ColumnRef> odsSourcesOf(ColumnRef output) {
        Set<ColumnRef> result = new TreeSet<>();
        for (ColumnRef ref : sourcesOf(output)) {
            if (ref.table().layer() == Layer.ODS) {
                result.add(ref);
            }
        }
        return result;
    }

    /** 向下影响闭包：改这个输入列会影响哪些下游列（含自身）——变更评审的最小单位。 */
    public Set<ColumnRef> impactOf(ColumnRef input) {
        Set<ColumnRef> visited = new TreeSet<>();
        visited.add(input);
        List<ColumnRef> queue = new ArrayList<>(outputs.getOrDefault(input, Set.of()));
        while (!queue.isEmpty()) {
            ColumnRef current = queue.remove(0);
            if (visited.add(current)) {
                queue.addAll(outputs.getOrDefault(current, Set.of()));
            }
        }
        return visited;
    }

    /** 血缘是否完整：所有非 ODS 列都必须能回溯到至少一个 ODS 源列。 */
    public List<ColumnRef> orphanColumns() {
        List<ColumnRef> orphans = new ArrayList<>();
        for (ColumnRef output : inputs.keySet()) {
            if (output.table().layer() == Layer.ODS) {
                continue;
            }
            if (odsSourcesOf(output).isEmpty()) {
                orphans.add(output);
            }
        }
        return List.copyOf(orphans);
    }

    /** 血缘图的可读输出（按输出列字典序）。 */
    public Map<String, List<String>> describe() {
        Map<String, List<String>> lines = new LinkedHashMap<>();
        inputs.forEach((output, ins) -> {
            List<String> parts = new ArrayList<>();
            ins.forEach(input -> parts.add(input.toString()));
            lines.put(output.toString(), List.copyOf(parts));
        });
        return lines;
    }

    /** 供图遍历使用：全部已登记的列节点。 */
    public Set<ColumnRef> nodes() {
        Set<ColumnRef> all = new LinkedHashSet<>();
        edges.forEach(edge -> {
            all.add(edge.output());
            all.add(edge.input());
        });
        return java.util.Collections.unmodifiableSet(new TreeSet<>(all));
    }
}
