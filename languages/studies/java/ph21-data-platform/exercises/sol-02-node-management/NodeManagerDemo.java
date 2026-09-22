// exercises/sol-02-node-management/NodeManagerDemo.java —— 节点管理系统验收演示
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-sol *.java
//   然后 java -cp /tmp/tl21-sol NodeManagerDemo
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class NodeManagerDemo {
    public static void main(String[] args) {
        NodeManager nodes = new NodeManager();
        // 1) 批量注册 5 个数据源
        nodes.registerAll(List.of(
                new NodeManager.Source("LSV0000001", "EV-Sedan", "v1.4.0", NodeManager.Status.REGISTERED),
                new NodeManager.Source("LSV0000002", "EV-Sedan", "v1.4.0", NodeManager.Status.REGISTERED),
                new NodeManager.Source("LSV0000003", "EV-Sedan", "v2.0.0", NodeManager.Status.REGISTERED),
                new NodeManager.Source("LSV0000004", "EV-Truck",  "v2.1.0", NodeManager.Status.REGISTERED),
                new NodeManager.Source("LSV0000005", "EV-Truck",  "v2.1.0", NodeManager.Status.REGISTERED)));

        AtomicInteger pass = new AtomicInteger();
        check(pass, nodes.fleetSize() == 5, "节点集群注册 5 台");

        // 2) 批量上下线：3 台上线、1 台进 版本发布、1 台离线
        nodes.changeStatus("LSV0000001", NodeManager.Status.ONLINE);
        nodes.changeStatus("LSV0000002", NodeManager.Status.ONLINE);
        nodes.changeStatus("LSV0000003", NodeManager.Status.UPDATING);   // 版本发布中
        nodes.changeStatus("LSV0000004", NodeManager.Status.OFFLINE);
        nodes.changeStatus("LSV0000005", NodeManager.Status.ONLINE);

        check(pass, nodes.countByStatus(NodeManager.Status.ONLINE) == 3, "在线 3 台");
        check(pass, nodes.countByStatus(NodeManager.Status.UPDATING) == 1, "版本发布中 1 台");
        check(pass, nodes.countByStatus(NodeManager.Status.OFFLINE) == 1, "离线 1 台");
        check(pass, nodes.listByStatus(NodeManager.Status.ONLINE).stream()
                        .allMatch(v -> v.sourceId().startsWith("LSV")),
                "按状态查询返回全部在线数据源且档案完整");

        // 3) 非法操作拦截：退役后不得复活；未注册 SOURCE_ID 不得操作
        boolean[] guarded = {false, false};
        try {
            nodes.changeStatus("LSV0000001", NodeManager.Status.RETIRED);
            nodes.changeStatus("LSV0000001", NodeManager.Status.ONLINE);     // 复活 → 拒
        } catch (IllegalStateException e) {
            guarded[0] = true;
        }
        try {
            nodes.changeStatus("LSV9999999", NodeManager.Status.ONLINE);    // 不存在 → 拒
        } catch (IllegalArgumentException e) {
            guarded[1] = true;
        }
        check(pass, guarded[0] && guarded[1], "终态复活与操作未注册 SOURCE_ID 均被拦截");

        System.out.println("当前节点集群: " + nodes.fleetSize() + " 台，在线 " + nodes.countByStatus(NodeManager.Status.ONLINE));
        System.out.printf("ALL PASS: %d/6%n", pass.get());
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) { pass.incrementAndGet(); }
    }
}
