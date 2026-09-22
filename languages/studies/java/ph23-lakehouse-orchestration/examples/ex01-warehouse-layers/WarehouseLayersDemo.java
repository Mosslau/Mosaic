// languages/java/ph23-lakehouse-orchestration/examples/ex01-warehouse-layers/WarehouseLayersDemo.java —— 四层建模主入口：依赖方向纪律 + 口径唯一源
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/ph23-ex01 *.java && java -cp /tmp/ph23-ex01 WarehouseLayersDemo
// 验证状态：已验证（OpenJDK 17.0.18 本机实测：7/7 PASS）
//
// 场景：一张订单事实链（ods_order → dwd_order/dwd_user → dws_user_day → ads_dashboard）。
// 断言覆盖 3.1 的四条纪律：① 依赖只能上游->下游；② 反向依赖被拒；③ 口径只写在 DWS；
// ④ 同一口径不能跨层重复定义。拓扑序要求两次运行一致——编排决策要能复盘。
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;

public final class WarehouseLayersDemo {

    private static final int TOTAL = 7;

    public static void main(String[] args) {
        // 四层各一张表：ODS 原始订单 → DWD 明细 → DWS 汇总 → ADS 看板
        TableRef odsOrder = new TableRef("ods_order", Layer.ODS);
        TableRef dwdOrder = new TableRef("dwd_order", Layer.DWD);
        TableRef dwdUser = new TableRef("dwd_user", Layer.DWD);
        TableRef dwsUserDay = new TableRef("dws_user_day", Layer.DWS);
        TableRef adsDashboard = new TableRef("ads_dashboard", Layer.ADS);

        WarehouseModel model = new WarehouseModel();
        for (TableRef t : List.of(odsOrder, dwdOrder, dwdUser, dwsUserDay, adsDashboard)) {
            model.addTable(t);
        }

        // 六条合法依赖：全部满足「上游层号 <= 下游层号」
        model.addDependency(odsOrder, dwdOrder);        // ODS -> DWD
        model.addDependency(odsOrder, dwdUser);         // ODS -> DWD
        model.addDependency(dwdOrder, dwsUserDay);      // DWD -> DWS
        model.addDependency(dwdUser, dwsUserDay);       // DWD -> DWS
        model.addDependency(dwdOrder, adsDashboard);    // DWD -> ADS（允许跨层，只要方向对）
        model.addDependency(dwsUserDay, adsDashboard);  // DWS -> ADS

        AtomicInteger pass = new AtomicInteger();

        // 1) 四层依赖合法：6 条边全部注册成功，且拓扑序的层号单调不减
        List<TableRef> topo = model.topoOrder();
        boolean monotone = true;
        for (int i = 1; i < topo.size(); i++) {
            if (topo.get(i - 1).layer().ordinal() > topo.get(i).layer().ordinal()) {
                monotone = false;
            }
        }
        check(pass, model.tableCount() == 5 && model.dependencyEdgeCount() == 6
                        && topo.size() == 5 && monotone,
                "四层依赖合法：5 张表 / 6 条边全部满足上游层号 <= 下游层号，拓扑序层号单调不减");

        // 2) 反向依赖被拒：ADS 层表作为 DWD 层表的上游 = 让结论回流成输入
        String reverseMessage = "";
        boolean reverseRejected = false;
        try {
            model.addDependency(adsDashboard, dwdOrder);   // ADS -> DWD 的依赖
        } catch (IllegalStateException e) {
            reverseRejected = true;
            reverseMessage = e.getMessage();
        }
        check(pass, reverseRejected && reverseMessage.contains("反向依赖被拒")
                        && model.dependencyEdgeCount() == 6,
                "DWD 依赖 ADS（反向依赖）被拒：抛 IllegalStateException 且没有留下半条边");

        // 3) 口径在 DWS 唯一定义通过：metricOwner 能查到 owner
        model.defineMetric("dau_instance", dwsUserDay);
        Optional<TableRef> owner = model.metricOwner("dau_instance");
        check(pass, owner.isPresent() && owner.get().equals(dwsUserDay)
                        && owner.get().layer() == Layer.DWS,
                "口径在 DWS 唯一定义通过：metricOwner(\"dau_instance\") = DWS.dws_user_day");

        // 4) 口径定义在非 DWS 层被拒：全新口径写进 DWD 也要拦下
        String layerMessage = "";
        boolean layerRejected = false;
        try {
            model.defineMetric("order_cnt", dwdOrder);
        } catch (IllegalStateException e) {
            layerRejected = true;
            layerMessage = e.getMessage();
        }
        check(pass, layerRejected && layerMessage.contains("只允许定义在 DWS 层")
                        && model.metricOwner("order_cnt").isEmpty(),
                "口径定义在 DWD 被拒：只有 DWS 是口径定义层，被拒后不留 owner");

        // 5) 同一口径在 DWD 与 ADS 重复定义被拒（跨层重复 = 口径漂移的起点）
        String dwdMessage = "";
        String adsMessage = "";
        boolean dwdRejected = false;
        boolean adsRejected = false;
        try {
            model.defineMetric("dau_instance", dwdOrder);
        } catch (IllegalStateException e) {
            dwdRejected = true;
            dwdMessage = e.getMessage();
        }
        try {
            model.defineMetric("dau_instance", adsDashboard);
        } catch (IllegalStateException e) {
            adsRejected = true;
            adsMessage = e.getMessage();
        }
        check(pass, dwdRejected && adsRejected
                        && dwdMessage.contains("跨层重复定义口径被拒")
                        && adsMessage.contains("跨层重复定义口径被拒")
                        && model.metricOwner("dau_instance").get().equals(dwsUserDay),
                "同一口径 dau_instance 在 DWD 与 ADS 重复定义均被拒：口径唯一源仍是 DWS.dws_user_day");

        // 6) 依赖查询正确：上游/下游各自的集合与方向
        List<TableRef> dwsUps = model.dependenciesOf(dwsUserDay);
        List<TableRef> adsUps = model.dependenciesOf(adsDashboard);
        List<TableRef> odsDowns = model.dependentsOf(odsOrder);
        boolean queriesOk = dwsUps.equals(List.of(dwdOrder, dwdUser))
                && adsUps.equals(List.of(dwdOrder, dwsUserDay))
                && odsDowns.equals(List.of(dwdOrder, dwdUser));
        check(pass, queriesOk,
                "依赖查询正确：dws_user_day ← {dwd_order,dwd_user}，ads_dashboard ← {dwd_order,dws_user_day}，"
                        + "ods_order → {dwd_order,dwd_user}");

        // 7) 拓扑序确定：同层按表名排序，两次调用结果逐项相同
        List<TableRef> topoAgain = model.topoOrder();
        boolean deterministic = topo.equals(topoAgain)
                && topo.get(0).equals(odsOrder)
                && topo.get(topo.size() - 1).equals(adsDashboard);
        check(pass, deterministic,
                "拓扑序确定：两次运行顺序一致 " + topo + "（起点 ODS、终点 ADS）");

        System.out.println("== 四层依赖图（上游 -> 下游） ==");
        for (TableRef t : topo) {
            List<TableRef> ups = model.dependenciesOf(t);
            System.out.printf("  %-6s %-14s <- %s%n", t.layer(), t.table(),
                    ups.isEmpty() ? "(源表)" : ups);
        }

        if (pass.get() == TOTAL) {
            System.out.printf("ALL PASS: %d/%d%n", pass.get(), TOTAL);
        } else {
            System.out.printf("FAILED: %d/%d（详见上面的 FAIL 行）%n", pass.get(), TOTAL);
            System.exit(1);
        }
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
