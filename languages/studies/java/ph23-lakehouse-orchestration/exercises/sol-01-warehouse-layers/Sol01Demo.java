// exercises/sol-01-warehouse-layers/Sol01Demo.java —— 练习 1 验收入口：四层依赖纪律 + 口径唯一源 + 口径对账
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-sol01 *.java && java -cp /tmp/ph23-sol01 Sol01Demo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：12/12 PASS）

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.TreeMap;

/**
 * 对应 23-lakehouse-orchestration.md 3.1（分层建模与口径）与第 7 章练习 1（sol-01）。
 * 断言是「依赖方向纪律 / 口径唯一源 / 口径对账」三条纪律的可执行形式：
 * 反向依赖与口径重复定义必须抛异常；同一指标跨表对账必须给出差异分区与两侧数值。
 */
public final class Sol01Demo {

    private static int passed = 0;
    private static int total = 0;

    public static void main(String[] args) {
        // ---- 0) 分层职责与依赖方向：层级序号即纪律（上游 <= 下游）----
        check(Layer.ODS.rank() < Layer.DWD.rank()
                        && Layer.DWD.rank() < Layer.DWS.rank()
                        && Layer.DWS.rank() < Layer.ADS.rank(),
                "四层层级有序：ODS(0) < DWD(1) < DWS(2) < ADS(3)");

        // ---- 1) 合法依赖（上游层级 <= 下游层级）----
        TableRef ods = new TableRef("ods_instance_event", Layer.ODS);
        TableRef dwd = new TableRef("dwd_instance_fact", Layer.DWD);
        TableRef dws = new TableRef("dws_daily_active", Layer.DWS);
        TableRef ads = new TableRef("ads_instance_dashboard", Layer.ADS);

        DependencyValidator validator = new DependencyValidator();
        boolean legal = true;
        legal &= validator.isValid(dwd, ads);
        legal &= validator.isValid(dws, ads);
        legal &= validator.isValid(ods, dwd);
        legal &= validator.isValid(ods, ads);
        legal &= validator.isValid(dwd, dws);
        check(legal && validator.checkedCount() == 5,
                "合法依赖全部通过：ODS→DWD/DWS/ADS、DWD→DWS、DWS→ADS（5 条）");

        // ---- 2) 反向依赖被拒（DWD 直接读 ADS 是口径失控的开始）----
        boolean reverseRejected = false;
        String reverseMessage = "";
        try {
            validator.validate(ads, dwd);
        } catch (IllegalStateException e) {
            reverseRejected = true;
            reverseMessage = e.getMessage();
        }
        check(reverseRejected
                        && reverseMessage.contains("反向依赖")
                        && reverseMessage.contains("DWD")
                        && reverseMessage.contains("ADS"),
                "反向依赖被拒：DWD 依赖 ADS（" + reverseMessage + "）");

        boolean reverseAdsRejected = false;
        try {
            validator.validate(ads, dws);
        } catch (IllegalStateException e) {
            reverseAdsRejected = true;
        }
        check(reverseAdsRejected && validator.checkedCount() == 5,
                "反向依赖被拒时不计入校验数：ADS→DWS 被拒，成功校验仍为 5 条");

        boolean selfRejected = false;
        try {
            validator.validate(dws, dws);
        } catch (IllegalStateException e) {
            selfRejected = true;
        }
        check(selfRejected, "自依赖被拒：DWS 依赖 DWS（不做业务解释的层也不会自己绕自己）");

        // ---- 3) 口径唯一源：同一指标只允许在 DWS 定义 ----
        MetricCatalog catalog = new MetricCatalog();
        boolean registered = true;
        try {
            catalog.register("daily_active_instance", "count(distinct instance_id)", dws);
            catalog.register("order_amount", "sum(pay_amount)", dws);
        } catch (RuntimeException e) {
            registered = false;
        }
        check(registered
                        && catalog.definitionOf("daily_active_instance").orElseThrow().table().table().equals("dws_daily_active")
                        && catalog.metrics().equals(Set.of("order_amount", "daily_active_instance")),
                "口径唯一源登记成功：daily_active_instance 唯一定义在 DWS dws_daily_active");

        boolean dupRejected = false;
        String dupMessage = "";
        try {
            catalog.register("daily_active_instance", "count(distinct instance_id)", dws);
        } catch (IllegalStateException e) {
            dupRejected = true;
            dupMessage = e.getMessage();
        }
        check(dupRejected
                        && dupMessage.contains("口径重复定义")
                        && dupMessage.contains("DWS")
                        && catalog.metrics().size() == 2,
                "口径重复定义被拒：同一指标第二次定义（" + dupMessage + "）");

        boolean adsRejected = false;
        String adsMessage = "";
        try {
            catalog.register("daily_active_instance", "count(distinct instance_id)", ads);
        } catch (IllegalStateException e) {
            adsRejected = true;
            adsMessage = e.getMessage();
        }
        check(adsRejected && adsMessage.contains("ADS"),
                "口径不允许写在 ADS：ADS 只能做展示态加工（" + adsMessage + "）");

        boolean conflict = catalog.definitionsConsistent("daily_active_instance");
        MetricCatalog other = new MetricCatalog();
        other.register("daily_active_instance", "count(instance_id)", dws);
        check(conflict
                        && !catalog.definitionsConsistent("daily_active_instance", other)
                        && catalog.firstConflict("daily_active_instance", other)
                                .map(MetricCatalog.Conflict::diffText)
                                .orElse("")
                                .contains("!="),
                "口径表达式一致性可校验：同表达式一致、count(distinct) 与 count 被判为冲突");

        // ---- 4) 口径对账：同一指标、同一分区逐分区比对 ----
        ReconcileDemo reconcile = new ReconcileDemo();
        reconcile.put("dws_daily_active", "daily_active_instance", 20240601L, 1000);
        reconcile.put("dws_daily_active", "daily_active_instance", 20240602L, 1000);
        reconcile.put("dws_daily_active", "daily_active_instance", 20240603L, 1000);
        reconcile.put("ads_instance_dashboard", "daily_active_instance", 20240601L, 1000);
        reconcile.put("ads_instance_dashboard", "daily_active_instance", 20240602L, 1000);
        reconcile.put("ads_instance_dashboard", "daily_active_instance", 20240603L, 1000);

        ReconcileResult same = reconcile.reconcile(
                "dws_daily_active", "ads_instance_dashboard", "daily_active_instance", partitions());
        check(same.pass()
                        && same.compared() == 3
                        && same.diffs().isEmpty()
                        && same.status().equals("PASS"),
                "对账一致通过：3 个分区逐分区数值相同（" + same.status() + "）");

        ReconcileDemo drifted = new ReconcileDemo();
        drifted.put("dws_daily_active", "daily_active_instance", 20240601L, 1000);
        drifted.put("dws_daily_active", "daily_active_instance", 20240602L, 1000);
        drifted.put("dws_daily_active", "daily_active_instance", 20240603L, 1000);
        drifted.put("ads_instance_dashboard", "daily_active_instance", 20240601L, 1000);
        drifted.put("ads_instance_dashboard", "daily_active_instance", 20240602L, 880);
        drifted.put("ads_instance_dashboard", "daily_active_instance", 20240603L, 1000);

        ReconcileResult mismatch = drifted.reconcile(
                "dws_daily_active", "ads_instance_dashboard", "daily_active_instance", partitions());
        Value diffValue = mismatch.diffs().get(0);
        check(!mismatch.pass()
                        && mismatch.status().equals("FAIL")
                        && mismatch.compared() == 3
                        && mismatch.diffs().size() == 1
                        && diffValue.partition() == 20240602L
                        && diffValue.value() == 1000
                        && diffValue.rightValue() == 880
                        && mismatch.diffText().contains("partition=20240602")
                        && mismatch.diffText().contains("dws_daily_active=1000")
                        && mismatch.diffText().contains("ads_instance_dashboard=880"),
                "对账不一致能报出差异分区与两侧数值（" + mismatch.diffText() + "）");

        boolean missingReported = false;
        String missingText = "";
        try {
            drifted.reconcile("dws_daily_active", "ads_instance_dashboard",
                    "daily_active_instance", List.of(20240731L));
        } catch (IllegalStateException e) {
            missingReported = true;
            missingText = e.getMessage();
        }
        check(missingReported
                        && missingText.contains("20240731")
                        && missingText.contains("无法对账"),
                "对账缺口显式暴露：某侧缺分区时拒绝静默通过（" + missingText + "）");

        System.out.println("分层依赖校验: " + validator.checkedCount() + " 条合法依赖，0 条反向依赖被放行");
        System.out.println("口径唯一源: " + catalog.definitions());
        System.out.println("口径对账: " + same.status() + " / " + mismatch.status());
        System.out.println("ALL PASS: " + passed + "/" + total);
        if (passed != total) {
            System.exit(1);
        }
    }

    private static List<Long> partitions() {
        return List.of(20240601L, 20240602L, 20240603L);
    }

    /** 分层：枚举序号即层级，数字小的在上游。 */
    public enum Layer {
        ODS(0), DWD(1), DWS(2), ADS(3);

        private final int rank;

        Layer(int rank) {
            this.rank = rank;
        }

        public int rank() {
            return rank;
        }

        /** 上游层级必须 <= 下游层级，否则是反向依赖。 */
        public static void checkDirection(Layer upstream, Layer downstream) {
            if (upstream.rank > downstream.rank) {
                throw new IllegalStateException("反向依赖：" + upstream + " 是 " + downstream
                        + " 的上游层级，但 " + upstream + " 在下游（只允许 上游层级 <= 下游层级）");
            }
        }
    }

    /** 表引用：表名 + 所在层。 */
    public record TableRef(String table, Layer layer) {
        public TableRef {
            if (table == null || table.isBlank()) {
                throw new IllegalArgumentException("表名不能为空");
            }
            if (layer == null) {
                throw new IllegalArgumentException("分层不能为空");
            }
        }
    }

    /** 依赖方向校验器：非法依赖抛异常且不计入成功校验数。 */
    public static final class DependencyValidator {

        private int checked = 0;

        /** @param upstream 提供数据的上游表 @param downstream 消费数据的下游表 */
        public void validate(TableRef upstream, TableRef downstream) {
            if (upstream.equals(downstream)) {
                throw new IllegalStateException("自依赖：" + upstream.table() + " 不能依赖自己");
            }
            Layer.checkDirection(upstream.layer(), downstream.layer());
            checked++;
        }

        public boolean isValid(TableRef upstream, TableRef downstream) {
            try {
                validate(upstream, downstream);
                return true;
            } catch (IllegalStateException e) {
                return false;
            }
        }

        public int checkedCount() {
            return checked;
        }
    }

    /** 口径定义：指标名 + 表达式 + 唯一定义所在表（口径唯一源）。 */
    public record MetricDef(String name, String expression, TableRef table) {
        public MetricDef {
            if (name == null || name.isBlank()) {
                throw new IllegalArgumentException("指标名不能为空");
            }
            if (expression == null || expression.isBlank()) {
                throw new IllegalArgumentException("口径表达式不能为空：" + name);
            }
            if (table == null) {
                throw new IllegalArgumentException("口径必须绑定到具体表：" + name);
            }
        }

        public String diffText() {
            return name + ": " + table.table() + " [" + table.layer() + "] " + expression;
        }
    }

    /**
     * 口径目录：口径的唯一源是 DWS。同一指标第二次登记（无论写在哪一层）都要被拦下，
     * 因为「两个数都对不上」的事故都是从这里开始的。
     */
    public static final class MetricCatalog {

        private final Map<String, MetricDef> defs = new TreeMap<>();

        /** 注册口径；重复登记抛 {@link IllegalStateException}。 */
        public void register(String metric, String expression, TableRef owner) {
            if (owner.layer() != Layer.DWS) {
                throw new IllegalStateException("口径只能定义在 DWS：" + metric
                        + " 被写在 " + owner.layer() + "（" + owner.table() + "）");
            }
            MetricDef previous = defs.get(metric);
            if (previous != null) {
                throw new IllegalStateException("口径重复定义：" + metric + " 已在 "
                        + previous.table().table() + " [" + previous.table().layer() + "] 定义为 "
                        + previous.expression() + "，不允许在 " + owner.table()
                        + " [" + owner.layer() + "] 再定义一遍");
            }
            defs.put(metric, new MetricDef(metric, expression, owner));
        }

        public Optional<MetricDef> definitionOf(String metric) {
            return Optional.ofNullable(defs.get(metric));
        }

        /** 定义是否在本目录内前后一致（同一指标不允许出现两个表达式）。 */
        public boolean definitionsConsistent(String metric) {
            return defs.containsKey(metric);
        }

        /** 两个目录对同一指标的定义是否一致（表达式逐字相同）。 */
        public boolean definitionsConsistent(String metric, MetricCatalog other) {
            MetricDef mine = defs.get(metric);
            MetricDef theirs = other.defs.get(metric);
            return mine != null && theirs != null && mine.expression().equals(theirs.expression());
        }

        /** 取出第一次口径冲突的明细（谁、在哪一层、什么表达式不同）。 */
        public Optional<Conflict> firstConflict(String metric, MetricCatalog other) {
            MetricDef mine = defs.get(metric);
            MetricDef theirs = other.defs.get(metric);
            if (mine == null || theirs == null || mine.expression().equals(theirs.expression())) {
                return Optional.empty();
            }
            return Optional.of(new Conflict(mine, theirs));
        }

        public Set<String> metrics() {
            return new LinkedHashSet<>(defs.keySet());
        }

        public Map<String, MetricDef> definitions() {
            return new TreeMap<>(defs);
        }

        /** 口径冲突明细：两张表对同一指标写了两套表达式。 */
        public record Conflict(MetricDef mine, MetricDef theirs) {
            public String diffText() {
                return mine.diffText() + " != " + theirs.diffText();
            }
        }
    }

    /** 对账比对用的单值：分区 → 两侧数值（差异明细用得上两张表的数）。 */
    public record Value(long partition, long value, long rightValue) {
    }

    /** 对账结果：状态 + 已比对分区数 + 差异明细。 */
    public record ReconcileResult(String leftTable, String rightTable, String metric,
                                  String status, int compared, List<Value> diffs) {

        public ReconcileResult {
            diffs = List.copyOf(diffs);
        }

        public static ReconcileResult passed(String leftTable, String rightTable, String metric,
                                             int compared) {
            return new ReconcileResult(leftTable, rightTable, metric, "PASS", compared, List.of());
        }

        public static ReconcileResult failed(String leftTable, String rightTable, String metric,
                                             int compared, List<Value> diffs) {
            return new ReconcileResult(leftTable, rightTable, metric, "FAIL", compared, diffs);
        }

        public boolean pass() {
            return "PASS".equals(status);
        }

        /** 差异明细的可读形态：哪个分区、两侧各是多少。 */
        public String diffText() {
            if (diffs.isEmpty()) {
                return leftTable + " == " + rightTable + "（" + metric + "，无差异）";
            }
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < diffs.size(); i++) {
                Value v = diffs.get(i);
                if (i > 0) {
                    sb.append("; ");
                }
                sb.append("partition=").append(v.partition())
                        .append(" ").append(leftTable).append("=").append(v.value())
                        .append(" ").append(rightTable).append("=").append(v.rightValue());
            }
            return sb.toString();
        }
    }

    /**
     * 口径对账：给定两张表（例如 DWS 与 ADS）的同一指标，按同一分区逐分区比对。
     * 差异不是「打个日志」，而是给出分区与两侧数值——这是值班能直接采取动作的粒度。
     */
    public static final class ReconcileDemo {

        private final Map<String, Map<String, Map<Long, Long>>> store = new HashMap<>();

        public void put(String table, String metric, long partition, long value) {
            store.computeIfAbsent(table, k -> new HashMap<>())
                    .computeIfAbsent(metric, k -> new HashMap<>())
                    .put(partition, value);
        }

        public ReconcileResult reconcile(String leftTable, String rightTable, String metric,
                                         List<Long> partitions) {
            List<Value> diffs = new ArrayList<>();
            int compared = 0;
            for (long partition : partitions) {
                Long left = lookup(leftTable, metric, partition);
                Long right = lookup(rightTable, metric, partition);
                if (left == null || right == null) {
                    throw new IllegalStateException("对账数据缺失，无法对账：partition=" + partition
                            + " " + leftTable + "=" + (left == null ? "<缺分区>" : left)
                            + " " + rightTable + "=" + (right == null ? "<缺分区>" : right));
                }
                compared++;
                if (left.longValue() != right.longValue()) {
                    diffs.add(new Value(partition, left, right));
                }
            }
            if (diffs.isEmpty()) {
                return ReconcileResult.passed(leftTable, rightTable, metric, compared);
            }
            return ReconcileResult.failed(leftTable, rightTable, metric, compared, diffs);
        }

        public boolean reconciled(String leftTable, String rightTable, String metric,
                                  List<Long> partitions) {
            return reconcile(leftTable, rightTable, metric, partitions).pass();
        }

        private Long lookup(String table, String metric, long partition) {
            Map<String, Map<Long, Long>> byMetric = store.get(table);
            if (byMetric == null) {
                return null;
            }
            Map<Long, Long> byPartition = byMetric.get(metric);
            return byPartition == null ? null : byPartition.get(partition);
        }
    }

    private static void check(boolean ok, String label) {
        total++;
        if (ok) {
            passed++;
        }
        System.out.println((ok ? "PASS " : "FAIL ") + label);
    }
}
