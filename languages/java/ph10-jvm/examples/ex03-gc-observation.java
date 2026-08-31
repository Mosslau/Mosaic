// examples/ex03-gc-observation.java —— GC 观察：制造 Minor GC 与对象晋升，配合 -Xlog:gc 解读真实日志
// 对应主文档 6. 示例 3：短命对象触发 Young GC；少量对象被长期持有并晋升老年代
// 验证环境：OpenJDK 17.0.18（默认 G1）
// 编译：javac ex03-gc-observation.java
// 运行（观察 GC 日志）：java -Xms64m -Xmx64m -Xlog:gc* Ex03GcObservation
// 运行（观察晋升, 推荐）：java -Xms64m -Xmx64m -Xlog:gc*,gc+promotion=debug Ex03GcObservation
// 验证状态：已验证：OpenJDK 17.0.18
// 说明：GC 日志的停顿毫秒数、触发时刻随机器与 GC 时机波动，观察「模式」（GC 类型/回收前后用量）即可，
//       不要断言精确数字；本程序只断言「跑完 N 轮且全程无 OOM」
import java.util.ArrayList;
import java.util.List;

class Ex03GcObservation {
    public static void main(String[] args) {
        List<byte[]> keep = new ArrayList<>();   // 长命对象：撑老年代，让少量对象晋升
        long total = 0;
        for (int round = 0; round < 200; round++) {
            // 每轮 200 个 32KB 短命对象：Eden 快速填满 → 触发 Young GC（大部分被回收）
            for (int i = 0; i < 200; i++) {
                byte[] tmp = new byte[32 * 1024];
                total += tmp.length;             // 防止逃逸分析把分配整个优化掉
            }
            // 每 40 轮留 1 个 1MB 对象：熬过多次 Young GC 后晋升老年代
            if (round % 40 == 0) keep.add(new byte[1024 * 1024]);
            if (round % 50 == 0) {
                System.out.println("第 " + round + " 轮完成 (临时对象累计 " + (total / 1024 / 1024) + " MB, 长命对象 " + keep.size() + " 个)");
            }
        }
        System.out.println("GC 观察完成：200 轮分配结束，无 OOM；上面的 -Xlog:gc 输出记录了本进程的全部 GC");
        if (total <= 0) throw new AssertionError("分配计数异常");
    }
}
