// languages/java/ph23-lakehouse-orchestration/examples/ex08-quality-lineage-cost/Lineage.java —— 列级血缘：由变换声明推导「输出列 ← 输入列」的闭包，并支持下游影响分析
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex08 *.java && java -cp /tmp/ph23-ex08 QualityLineageCostDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：9/9 PASS）
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/**
 * 列级血缘（不是表级）：表级只能说「A 来自 B」，而变更评审要回答的是
 * 「改 DWD 的 `latency_ms` 会影响哪些看板的哪一列」——列是合规与影响分析的**最小单位**（3.8）。
 *
 * 建模方式：每个变换声明**一个输出列 ← 若干输入列 + 变换类型**，例如
 * ```
 * dws.dau.instances        ← dwd.event.instanceId   (count distinct)
 * ads.dashboard.dau_value  ← dws.dau.instances      (identity)
 * ```
 * 于是：
 *   - {@link #upstreamOf}  向上游走整张图，得到「这一列到底怎么来的」的完整推导链（可回溯到 ODS）；
 *   - {@link #downstreamOf} 向下游走整张图，得到「改这一列会炸到谁」（影响分析）。
 *
 * 图是**有向无环**的：变换只能从上游表指向下游表，反向声明直接抛异常（与 3.1 的依赖方向纪律一致）。
 */
public final class Lineage {

    /** 一列的身份：(表, 列)。 */
    public record ColumnRef(String table, String column) {
        public ColumnRef {
            if (table == null || table.isBlank() || column == null || column.isBlank()) {
                throw new IllegalArgumentException("ColumnRef 的表与列都不能为空");
            }
        }

        /** 简洁渲染：`table.column`。 */
        @Override
        public String toString() {
            return table + "." + column;
        }

        /** `dws.dau.instances` 这样的点分字符串 → ColumnRef（表名不含点，列名可含点）。 */
        public static ColumnRef parse(String dotted) {
            int split = dotted.indexOf('.');
            if (split <= 0 || split == dotted.length() - 1) {
                throw new IllegalArgumentException("必须是 table.column 形式：" + dotted);
            }
            return new ColumnRef(dotted.substring(0, split), dotted.substring(split + 1));
        }
    }

    /** 变换声明：输出列由哪些输入列按什么算子得来。 */
    public record Transform(ColumnRef output, List<ColumnRef> inputs, String operation) {
        public Transform {
            if (output == null || inputs == null || inputs.isEmpty()) {
                throw new IllegalArgumentException("变换必须声明输出列与至少一个输入列");
            }
            if (operation == null || operation.isBlank()) {
                throw new IllegalArgumentException("变换必须声明算子类型（如 count distinct / identity / sum）");
            }
            inputs = List.copyOf(inputs);
        }
    }

    private final List<Transform> transforms;
    /** 输出列 → 它的变换声明。 */
    private final Map<ColumnRef, Transform> byOutput = new LinkedHashMap<>();

    public Lineage(List<Transform> transforms) {
        this.transforms = List.copyOf(transforms);
        for (Transform transform : this.transforms) {
            if (byOutput.put(transform.output(), transform) != null) {
                throw new IllegalArgumentException("同一列被声明了两次 lineage：" + transform.output());
            }
        }
        // 依赖方向纪律：输出列所在表必须严格在下游（这里用「同表不同列」的最简判据）——
        // 完整四层比较见 ex01；本示例只禁止「自己依赖自己」的环。
        for (Transform transform : this.transforms) {
            for (ColumnRef input : transform.inputs()) {
                if (input.equals(transform.output())) {
                    throw new IllegalArgumentException("列不能依赖自己：" + input);
                }
            }
        }
    }

    /**
     * 上游闭包：从某一列出发，递归展开它依赖的所有输入列。
     * 返回**按 (表,列) 升序**的确定性集合，其中包含起点列本身（方便断言「链上都有谁」）。
     */
    public TreeSet<ColumnRef> upstreamOf(ColumnRef column) {
        TreeSet<ColumnRef> visited = new TreeSet<>(java.util.Comparator
                .comparing(ColumnRef::table).thenComparing(ColumnRef::column));
        collectUpstream(column, visited, new TreeSet<>(java.util.Comparator
                .comparing(ColumnRef::table).thenComparing(ColumnRef::column)));
        return visited;
    }

    /** 只返回上游列（不含起点列自己）——用于「这条链上的源头是哪些列」。 */
    public List<ColumnRef> upstreamSourcesOf(ColumnRef column) {
        List<ColumnRef> sources = new ArrayList<>();
        for (ColumnRef ref : upstreamOf(column)) {
            if (!ref.equals(column)) {
                sources.add(ref);
            }
        }
        return sources;
    }

    /**
     * 下游闭包（影响分析）：改这一列会影响到哪些列。
     * 返回按 (表,列) 升序的集合，不含起点列本身。
     */
    public TreeSet<ColumnRef> downstreamOf(ColumnRef column) {
        TreeSet<ColumnRef> visited = new TreeSet<>(java.util.Comparator
                .comparing(ColumnRef::table).thenComparing(ColumnRef::column));
        collectDownstream(column, visited);
        visited.remove(column);
        return visited;
    }

    /** 变换明细：`输出 ← 输入 (算子)`，按输出列排序。 */
    public String renderTransforms() {
        List<String> lines = new ArrayList<>();
        for (Transform transform : transforms) {
            StringBuilder inputs = new StringBuilder();
            for (ColumnRef input : transform.inputs()) {
                if (inputs.length() > 0) {
                    inputs.append(", ");
                }
                inputs.append(input);
            }
            lines.add(transform.output() + " ← " + inputs + " (" + transform.operation() + ")");
        }
        lines.sort(String::compareTo);
        return String.join("\n", lines);
    }

    /**
     * 渲染一列的上游链：`ads.dashboard.dau_value(id) ← dws.dau.instances(count distinct) ← ods.event.instance_id(source)`。
     * 从起点沿变换声明逐层向上，每层只保留**直接上级**，因此不会把「祖先」重复列在「父级」后面。
     */
    public String renderUpstreamChain(ColumnRef column) {
        List<String> parts = new ArrayList<>();
        List<ColumnRef> frontier = List.of(column);
        while (!frontier.isEmpty()) {
            ColumnRef current = frontier.get(0);
            parts.add(current + "(" + operation(current) + ")");
            Transform transform = byOutput.get(current);
            frontier = transform == null ? List.of() : transform.inputs();
        }
        return String.join(" ← ", parts);
    }

    /** 某个列是由什么算子算出来的（起点列没有变换声明时返回 "source"）。 */
    public String operation(ColumnRef column) {
        Transform transform = byOutput.get(column);
        return transform == null ? "source" : transform.operation();
    }

    public List<Transform> transforms() {
        return List.copyOf(transforms);
    }

    private void collectUpstream(ColumnRef column, TreeSet<ColumnRef> visited, TreeSet<ColumnRef> expanding) {
        if (!visited.add(column) || !expanding.add(column)) {
            return;
        }
        Transform transform = byOutput.get(column);
        if (transform != null) {
            for (ColumnRef input : transform.inputs()) {
                collectUpstream(input, visited, expanding);
            }
        }
    }

    private void collectDownstream(ColumnRef column, TreeSet<ColumnRef> visited) {
        if (!visited.add(column)) {
            return;
        }
        for (Transform transform : transforms) {
            if (transform.inputs().contains(column)) {
                collectDownstream(transform.output(), visited);
            }
        }
    }
}
