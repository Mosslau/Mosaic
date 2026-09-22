/*
 * examples/ex07-gc-log-demo/GcLogDemo.java
 * GC 日志演示程序：周期性制造「存活少量 + 大量可回收对象」，配合 -Xlog 观察 G1 的 young gc /
 * mixed gc / 停顿时间与堆占用曲线。程序本身只打印分配节奏，分析靠 GC 日志文件（见本目录 README）。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew），G1（17 默认收集器）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls GcLogDemo.java
 * 运行：java -Xms48m -Xmx48m -Xlog:gc*:file=/tmp/gc-demo.log,filecount=1,filesize=8m \
 *          -cp /tmp/tl20-cls GcLogDemo
 * 本机已实测：编译通过；运行后 /tmp/gc-demo.log 生成，含多轮 young gc 记录（样例见 README）
 */
import java.util.ArrayList;
import java.util.List;

public class GcLogDemo {

    /** 循环制造可回收的大对象，保留少量存活对象模拟「正常服务内存曲线」。 */
    public static void main(String[] args) throws InterruptedException {
        byte[][] keepAlive = new byte[8][];          // 少量长期存活，制造点 old 区占用
        int keepIdx = 0;
        long start = System.currentTimeMillis();
        for (int round = 0; round < 60; round++) {
            List<byte[]> garbage = new ArrayList<>();
            for (int i = 0; i < 12; i++) {
                garbage.add(new byte[1024 * 1024]);  // 每轮 12MB 一次性垃圾
            }
            // 让上一轮 garbage 自然失去引用（出了循环体就被回收）
            if (round % 6 == 0) {
                keepAlive[keepIdx++ % keepAlive.length] = new byte[512 * 1024];   // 每 6 轮留 0.5MB 存活
            }
            System.out.printf("[%5dms] round %02d alloc 12MB done%n",
                    System.currentTimeMillis() - start, round);
            Thread.sleep(10);                        // 放慢节奏，让 GC 日志可读
        }
        long kept = 0;
        for (byte[] a : keepAlive) {
            if (a != null) {
                kept += a.length;
            }
        }
        System.out.println("DONE. keepAlive 约 " + kept / 1024 + "KB。请查看 GC 日志文件分析回收过程。");
    }
}
