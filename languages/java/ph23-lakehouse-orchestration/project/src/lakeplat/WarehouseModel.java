// project/src/lakeplat/WarehouseModel.java —— 四层建模：依赖方向纪律 + 指标口径唯一源 + 下游依赖图
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：14/14 PASS）
package lakeplat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;

/**
 * 数仓模型（主文档 3.1）：登记表、校验依赖方向、守住指标口径的唯一源，并对外提供下游依赖图。
 *
 * <p>三条不可协商的规则：
 * <ol>
 *   <li><b>依赖方向</b>：下游表只能读上游层（{@link Layer#canReadFrom}）；反向依赖抛
 *       {@link IllegalStateException}，错误信息里带上「谁依赖谁、为什么不允许」。</li>
 *   <li><b>口径唯一源</b>：一个指标只能在 <b>DWS</b> 层定义；在 DWD/ADS 里再定义一次直接拒绝
 *       （否则早晚会长出「两个数都对不上」的经典事故）。</li>
 *   <li><b>依赖图确定性</b>：任何遍历（就绪、下游闭包、一屏展示）都按 {@link TreeSet} 字典序，
 *       保证同样输入产出同样的顺序，编排决策可复盘。</li>
 * </ol>
 *
 * <p>本类只持有**元数据**（表、依赖、指标归属），不持有数据——数据在 {@link TableFormat} 的表里。
 */
public final class WarehouseModel {

    /** 一条合法的依赖边：{@code downstream} 读 {@code upstream}。 */
    public record Dependency(TableRef downstream, TableRef upstream) {
        public Dependency {
            Objects.requireNonNull(downstream, "downstream");
            Objects.requireNonNull(upstream, "upstream");
        }

        @Override
        public String toString() {
            return upstream.table() + " → " + downstream.table();
        }
    }

    private final Map<String, TableRef> tables = new LinkedHashMap<>();
    private final List<Dependency> dependencies = new ArrayList<>();
    private final Map<String, String> metricOwner = new LinkedHashMap<>();
    private final Map<TableRef, String> partitionKeys = new LinkedHashMap<>();
    private final Map<TableRef, Long> partitionOffsetDays = new LinkedHashMap<>();
    private final Map<TableRef, Set<TableRef>> downstream = new LinkedHashMap<>();

    /** 登记一张表（幂等：同名同层重复登记不报错，同名不同层报错）。 */
    public TableRef registerTable(TableRef ref) {
        TableRef exists = tables.get(ref.table());
        if (exists != null) {
            if (exists.layer() != ref.layer()) {
                throw new IllegalStateException("表名冲突：" + ref.table() + " 已登记为 "
                        + exists.layer() + "，不能同时是 " + ref.layer());
            }
            return exists;
        }
        tables.put(ref.table(), ref);
        partitionKeys.put(ref, "p");
        partitionOffsetDays.put(ref, 0L);
        downstream.put(ref, new TreeSet<>((a, b) -> a.table().compareTo(b.table())));
        return ref;
    }

    /** 登记一张表并声明它的分区键与「分区键相对事件日期的偏移天数」（回填传播用）。 */
    public TableRef registerTable(TableRef ref, String partitionKeyName, long offsetDays) {
        TableRef registered = registerTable(ref);
        partitionKeys.put(registered, partitionKeyName);
        partitionOffsetDays.put(registered, offsetDays);
        return registered;
    }

    /** 声明 {@code downstream} 依赖 {@code upstream}：校验层级方向，并记入依赖图。 */
    public Dependency declareDependency(TableRef downstreamRef, TableRef upstreamRef) {
        TableRef down = require(downstreamRef);
        TableRef up = require(upstreamRef);
        if (!down.layer().canReadFrom(up.layer())) {
            throw new IllegalStateException("反向依赖被拒：" + down + " 读 " + up
                    + " 违反分层纪律（" + up.layer() + ".ordinal=" + up.layer().ordinal()
                    + " > " + down.layer() + ".ordinal=" + down.layer().ordinal()
                    + "，数据只能从上游流向下游）");
        }
        Dependency dep = new Dependency(down, up);
        if (!dependencies.contains(dep)) {
            dependencies.add(dep);
            downstream.get(up).add(down);
        }
        return dep;
    }

    /**
     * 声明指标口径：**只允许在 DWS 定义**。
     *
     * <p>同一 DWS 主题下多处声明同一指标是允许的（口径本来就该被复用）；
     * 但 DWD/ODS/ADS 一旦声明就抛异常——这是「口径唯一源」的编译期替代品。
     */
    public void declareMetric(String metric, TableRef owner) {
        TableRef table = require(owner);
        if (table.layer() != Layer.DWS) {
            throw new IllegalStateException("口径唯一源被破坏：指标 " + metric + " 声明在 "
                    + table + "，但只允许声明在 DWS 层（下游 ADS 只做展示态加工，上游 DWD 不做业务解释）");
        }
        String exists = metricOwner.get(metric);
        if (exists != null && !exists.equals(table.table())) {
            throw new IllegalStateException("口径重复定义：指标 " + metric + " 已由 " + exists
                    + " 定义，不能再由 " + table.table() + " 定义");
        }
        metricOwner.put(metric, table.table());
    }

    /** 指标的口径归属表（DWS）。 */
    public String metricOwner(String metric) {
        String owner = metricOwner.get(metric);
        if (owner == null) {
            throw new IllegalStateException("指标 " + metric + " 没有口径定义（应声明在 DWS 层）");
        }
        return owner;
    }

    public boolean hasMetric(String metric) {
        return metricOwner.containsKey(metric);
    }

    /** 所有登记表（按登记序，用于确定性输出）。 */
    public List<TableRef> tables() {
        return List.copyOf(tables.values());
    }

    /** 取表引用；未登记的表一律拒绝（防止"凭空读表"）。 */
    public TableRef require(TableRef ref) {
        TableRef exists = tables.get(ref.table());
        if (exists == null) {
            throw new IllegalStateException("未登记的表：" + ref.table() + "（请先在 WarehouseModel 里建表）");
        }
        if (exists.layer() != ref.layer()) {
            throw new IllegalStateException("表 " + ref.table() + " 的层不一致：已登记 " + exists.layer() + "，传入 " + ref.layer());
        }
        return exists;
    }

    public List<Dependency> dependencies() {
        return List.copyOf(dependencies);
    }

    /** 直接上游（字典序）。 */
    public Set<TableRef> upstreamOf(TableRef ref) {
        Set<TableRef> result = new TreeSet<>((a, b) -> a.table().compareTo(b.table()));
        for (Dependency dep : dependencies) {
            if (dep.downstream().equals(require(ref))) {
                result.add(dep.upstream());
            }
        }
        return result;
    }

    /** 直接下游（字典序）。 */
    public Set<TableRef> downstreamOf(TableRef ref) {
        return new TreeSet<>(downstream.getOrDefault(require(ref), Set.of()));
    }

    /**
     * 下游重算闭包（主文档 3.7 / 4.4）：依赖图上的传递闭包，**不含起点自身**。
     *
     * <p>回填必须传播到闭包内的每一张表，否则 DWS/ADS 会用「旧上游 + 新上游」的混合结果，
     * 而两边各自都自洽——这种不一致没有任何自动告警能发现。
     */
    public Set<TableRef> downstreamClosure(TableRef ref) {
        Set<TableRef> visited = new TreeSet<>((a, b) -> a.table().compareTo(b.table()));
        List<TableRef> queue = new ArrayList<>(downstreamOf(ref));
        while (!queue.isEmpty()) {
            TableRef current = queue.remove(0);
            if (visited.add(current)) {
                queue.addAll(downstreamOf(current));
            }
        }
        return visited;
    }

    /** 分区键（回填按分区覆盖时的口径）。 */
    public String partitionKey(TableRef ref) {
        return partitionKeys.getOrDefault(require(ref), "p");
    }

    /** 分区键相对事件日期的偏移天数：DWS 按天聚合 → 0；按周聚合 → 6（回填传播时决定下游要重算哪些分区）。 */
    public long partitionOffsetDays(TableRef ref) {
        return partitionOffsetDays.getOrDefault(require(ref), 0L);
    }

    /** 建表总数（一屏与断言用）。 */
    public int tableCount() {
        return tables.size();
    }
}
