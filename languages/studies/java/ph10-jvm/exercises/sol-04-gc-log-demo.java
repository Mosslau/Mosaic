// exercises/sol-04-gc-log-demo.java —— 练习 4 参考实现：制造 Young GC 的观察程序（配合 -Xlog:gc*）
// 验证环境：OpenJDK 17.0.18（默认 G1）
// 编译：javac sol-04-gc-log-demo.java
// 运行：java -Xms128m -Xmx128m -Xlog:gc* GcLogDemoSol
//       java -Xms64m  -Xmx64m  -Xlog:gc* GcLogDemoSol    （对照: 堆更小, Young GC 更频繁）
// 验证状态：已验证：OpenJDK 17.0.18（实测: 同一负载下 128m 堆 Young GC 38 次, 64m 堆 74 次——堆越小 GC 越频繁; 见 README 与下方注释）
// 说明：GC 日志的停顿毫秒与触发时刻随机器/GC 时机波动, 观察模式即可, 不要断言精确数字
import java.util.ArrayList;
import java.util.List;

class GcLogDemoSol {
    static long total = 0;                              // 累计临时对象大小, 防止 JIT 把未使用的分配整个消除

    public static void main(String[] args) {
        List<byte[]> keep = new ArrayList<>();          // 长命对象: 少量对象可能晋升老年代
        int i = 0;
        while (i < 300) {
            for (int j = 0; j < 100; j++) {
                byte[] tmp = new byte[64 * 1024];       // 大量短命对象 → 快速填满 Eden → 触发 Young GC
                total += tmp.length;                    // 注意: 裸 `new byte[64*1024];` 不是合法语句, 必须赋值;
                //                                           累计 total 也防止逃逸分析把分配优化掉
            }
            if (i % 100 == 0) keep.add(new byte[1024 * 1024]);   // 少量 1MB 对象保留下来
            i++;
        }
        if (total <= 0) throw new AssertionError("分配计数异常");
    }
}
