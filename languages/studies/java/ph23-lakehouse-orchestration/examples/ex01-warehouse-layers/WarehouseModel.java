// languages/java/ph23-lakehouse-orchestration/examples/ex01-warehouse-layers/WarehouseModel.java —— 分层依赖图 + 反向依赖拦截 + 口径唯一源校验
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex01 *.java && java -cp /tmp/ph23-ex01 WarehouseLayersDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 为什么把「依赖方向」和「口径唯一源」做成建模期的硬校验：口径漂移（同一指标在多层各算一遍）是
// 数仓最经典的事故——两个数都对不上，却没人知道以哪个为准。等对账时才发现就已经晚了，成本已经
// 扩散到全部下游。所以把两条纪律固化成 addDependency / defineMetric 的入参约束：错误在建模阶段就
// 抛 IllegalStateException，而不是推迟到下游任务运行时才炸。
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.PriorityQueue;
import java.util.Set;

public final class WarehouseModel {

    /**
     * 排序即确定性：同层先按层号、再按表名。拓扑序必须可复盘——同样的图，两次运行要给出同一个顺序，
     * 否则「昨天为什么慢」永远查不清（与 ph22 调度的确定性纪律同源）。
     */
    private static final Comparator<TableRef> TABLE_ORDER =
            Comparator.comparingInt((TableRef t) -> t.layer().ordinal()).thenComparing(TableRef::table);

    /** 下游表 -> 它的上游集合：边的方向与数据流向一致（key 依赖 value）。 */
    private final Map<TableRef, Set<TableRef>> upstreams = new LinkedHashMap<>();

    /** 口径 -> 当前定义的 owner 表。 */
    private final Map<String, TableRef> metricOwners = new LinkedHashMap<>();

    /** 口径 -> 曾经声明过它的层集合：用来识别「同一口径被写在两个不同层」。 */
    private final Map<String, Set<Layer>> metricLayers = new LinkedHashMap<>();

    /** 注册一张表（幂等）。建依赖前必须先注册，避免依赖图里出现「幽灵节点」。 */
    public void addTable(TableRef table) {
        upstreams.putIfAbsent(table, new LinkedHashSet<>());
    }

    public int tableCount() {
        return upstreams.size();
    }

    public int dependencyEdgeCount() {
        return upstreams.values().stream().mapToInt(Set::size).sum();
    }

    /**
     * 注册一条依赖：upstream 是数据来源，downstream 是消费方。
     * 上游层号必须 <= 下游层号，否则是「反向依赖」——ADS 的结论回流到 DWD 是口径失控的开始。
     */
    public void addDependency(TableRef upstream, TableRef downstream) {
        requireRegistered(upstream);
        requireRegistered(downstream);
        if (upstream.layer().ordinal() > downstream.layer().ordinal()) {
            throw new IllegalStateException("反向依赖被拒: " + upstream.layer() + " 层表 " + upstream.table()
                    + " 不能作为 " + downstream.layer() + " 层表 " + downstream.table()
                    + " 的上游——数据只能从上游层流向下游层，下游结论不允许回流成上游输入");
        }
        upstreams.get(downstream).add(upstream);
    }

    /** 该表的上游（数据来源），按层号+表名的确定顺序返回。 */
    public List<TableRef> dependenciesOf(TableRef table) {
        requireRegistered(table);
        return upstreams.get(table).stream().sorted(TABLE_ORDER).toList();
    }

    /** 该表的下游（消费方），按层号+表名的确定顺序返回。 */
    public List<TableRef> dependentsOf(TableRef table) {
        requireRegistered(table);
        List<TableRef> out = new ArrayList<>();
        for (Map.Entry<TableRef, Set<TableRef>> e : upstreams.entrySet()) {
            if (e.getValue().contains(table)) {
                out.add(e.getKey());
            }
        }
        out.sort(TABLE_ORDER);
        return List.copyOf(out);
    }

    /**
     * 定义口径列：只允许落在 DWS，且同一口径不能在两个不同层各定义一次。
     * 先查跨层重复、再查层限制：这样「换一层再定义一次」的错误信息能直接指出冲突双方，
     * 而不是笼统地说「不在这层」。
     */
    public void defineMetric(String metric, TableRef table) {
        if (metric == null || metric.isBlank()) {
            throw new IllegalArgumentException("metric 必填");
        }
        requireRegistered(table);

        Set<Layer> layers = metricLayers.get(metric);
        if (layers != null && layers.stream().anyMatch(l -> l != table.layer())) {
            throw new IllegalStateException("跨层重复定义口径被拒: 口径 " + metric + " 已定义在 " + layers
                    + "，不能在 " + table.layer() + " 层的 " + table.table()
                    + " 再定义一次——口径必须有唯一源，否则同一指标会出现两个都对不上的数");
        }
        if (!table.layer().isMetricLayer()) {
            throw new IllegalStateException("口径列只允许定义在 DWS 层: 口径 " + metric
                    + " 试图定义在 " + table.layer() + " 层的 " + table.table()
                    + "（DWD 只做明细、ADS 只做展示态加工，口径写在 DWS 才能被多张看板复用）");
        }

        metricOwners.put(metric, table);
        metricLayers.computeIfAbsent(metric, k -> new LinkedHashSet<>()).add(table.layer());
    }

    /** 口径的 owner 表；未定义返回 empty——调用方必须显式处理「没有唯一源」的情况。 */
    public Optional<TableRef> metricOwner(String metric) {
        return Optional.ofNullable(metricOwners.get(metric));
    }

    /**
     * 确定性拓扑序：Kahn 算法 + 同层按表名排序的优先队列。
     * 依赖图理论上不可能有环（边只能从低层指向高层），仍保留环检测——建模期的错误要立刻暴露。
     */
    public List<TableRef> topoOrder() {
        Map<TableRef, Integer> indegree = new HashMap<>();
        upstreams.forEach((t, ups) -> indegree.put(t, ups.size()));

        PriorityQueue<TableRef> ready = new PriorityQueue<>(TABLE_ORDER);
        indegree.forEach((t, d) -> {
            if (d == 0) {
                ready.add(t);
            }
        });

        List<TableRef> order = new ArrayList<>();
        while (!ready.isEmpty()) {
            TableRef t = ready.poll();
            order.add(t);
            for (TableRef down : dependentsOf(t)) {
                if (indegree.merge(down, -1, Integer::sum) == 0) {
                    ready.add(down);
                }
            }
        }
        if (order.size() != upstreams.size()) {
            throw new IllegalStateException("依赖图存在环，无法给出拓扑序");
        }
        return List.copyOf(order);
    }

    private void requireRegistered(TableRef table) {
        if (!upstreams.containsKey(table)) {
            throw new IllegalArgumentException("表未注册: " + table.layer() + " " + table.table()
                    + "（先 addTable 再建依赖，避免依赖图出现幽灵节点）");
        }
    }
}
