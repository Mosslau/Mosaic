// exercises/sol-03-memory-leak-demo.java —— 练习 3 参考实现：静态集合内存泄漏 + jmap 定位
// 验证环境：OpenJDK 17.0.18；诊断工具 jstat/jmap/jcmd 为 JDK 自带
// 编译：javac sol-03-memory-leak-demo.java
// 运行：java -Xms128m -Xmx128m MemoryLeakDemoSol 40
//       （40 = 分配到 40MB 后保持存活约 60 秒供诊断，然后继续分配直至 OOM；不传则默认 40。
//        实测 128m 堆下 cap 设 80 会在 ~60MB 提前 OOM、到不了保持档位，故默认取 40）
// 验证状态：已验证：OpenJDK 17.0.18（jmap -histo 实测 byte[] 实例数/字节数远超其他类, 见 README 与下方注释）
// 运行前提：本程序故意泄漏（静态集合持有对象, 永不释放）, 仅供诊断练习; 验证完 kill 清理进程与 hprof
import java.util.ArrayList;
import java.util.List;

class MemoryLeakDemoSol {
    // 静态集合: 静态字段是 GC Root, add 进去的对象永远可达、GC 永远回收不了 → 经典内存泄漏
    static final List<byte[]> CACHE = new ArrayList<>();

    public static void main(String[] args) throws Exception {
        int capMB = args.length > 0 ? Integer.parseInt(args[0]) : 40;
        int i = 0;
        while (true) {
            CACHE.add(new byte[1024 * 1024]);          // 每轮 1MB, 一直被静态集合持有
            i++;
            if (i % 5 == 0) {
                System.out.println("已累计 " + i + " MB (pid=" + ProcessHandle.current().pid() + ")");
            }
            if (i >= capMB) {
                // 达到上限后保持存活约 60 秒: 留出时间做 jstat/jmap -histo/堆 dump 诊断（不设这一档会很快 OOM, 来不及观察）
                System.out.println("达到 " + capMB + " MB, 保持存活供诊断（jstat / jmap -histo / 堆 dump）…");
                for (int s = 0; s < 60; s++) Thread.sleep(1000);
                System.out.println("继续分配, 即将 OOM…");
            }
            Thread.sleep(50);
        }
        // 修复思路: 静态集合换局部变量（方法结束后可回收）/ 定期清理 / 换带淘汰策略的缓存;
        // 线上排查: jstat -gcutil 看老年代持续上涨 → jmap -histo 看 byte[] 突出 → 堆 dump + MAT 沿引用链找持有者
    }
}
