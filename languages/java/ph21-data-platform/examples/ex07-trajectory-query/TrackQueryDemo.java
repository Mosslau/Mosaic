// examples/ex07-trajectory-query/TrackQueryDemo.java —— 轨迹查询演示
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：
//   javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//   java -cp /tmp/tl21-cls TrackQueryDemo
// 期望：两车各写入 10 个点；时间窗查询只回该窗口内的点；latest 是最末采样点。
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class TrackQueryDemo {
    public static void main(String[] args) {
        TrackStore store = new TrackStore();
        String v1 = "LSV0000001";
        String v2 = "LSV0000002";

        // 每车 10 个点：1 分钟一个点(沿经度匀速东行，模拟城市行驶)
        long base = 1_700_000_000L;
        for (int i = 0; i < 10; i++) {
            store.append(new GpsPoint(v1, base + i * 60L, 31.2304, 121.4737 + i * 0.001, 30 + i));
            store.append(new GpsPoint(v2, base + i * 60L, 39.9042, 116.4074 - i * 0.001, 20 + i * 2));
        }

        // 查询：只取 3~6 分钟之间 4 个点
        List<GpsPoint> window = store.queryWindow(v1, base + 3 * 60L, base + 6 * 60L);

        AtomicInteger pass = new AtomicInteger();
        check(pass, store.totalPoints() == 20, "两车共 20 个轨迹点入库");
        check(pass, window.size() == 4, "时间窗查询精确返回 4 个点(3~6 分钟)");
        check(pass, store.latest(v1).speedKmh() == 39, "latest(v1) 是最末采样点(速度 39km/h)");
        check(pass, store.latest(v1).lon() > store.latest(v2).lon(),
                "v1 在上海向东(经度增)、v2 在北京向西(经度减)——latest 语义正确");
        System.out.println("v1 时间窗点: " + window.size() + " 个, 首点 lon=" + window.get(0).lon());
        System.out.printf("ALL PASS: %d/4%n", pass.get());
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
