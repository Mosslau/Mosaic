// examples/ex02-fake-source-ingest/IngestDemo.java —— 接入层吞吐演示主入口
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：
//   javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//   java -cp /tmp/tl21-cls IngestDemo
//
// 场景一(正常负载)：队列容量充足，10 个数据源 × 300 帧，期望零背压丢弃、坏帧与重复帧被精确拦截；
// 场景二(过载压测)：同一引擎换小队列，涌入量远超消费能力，验证「队满丢弃」计数成立。
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class IngestDemo {
    public static void main(String[] args) throws InterruptedException {
        // ---- 场景一：正常负载，容量够用 ----
        int sources = 10;
        int framesPerSource = 300;
        IngestService ingest = new IngestService(/*laneCount*/ 4, /*queuePerLane*/ 25_000);
        ingest.start();
        List<Thread> sims = new ArrayList<>();
        List<FakeSource> fakes = new ArrayList<>();
        for (int i = 1; i <= sources; i++) {
            FakeSource v = new FakeSource("LSV" + String.format("%07d", i), framesPerSource, ingest);
            fakes.add(v);
            Thread t = new Thread(v, "source-" + i);
            sims.add(t);
            t.start();
        }
        long t0 = System.nanoTime();
        for (Thread t : sims) {
            t.join();                     // 等待全部采集端上报完成
        }
        long t1 = System.nanoTime();
        ingest.shutdown();

        double seconds = (t1 - t0) / 1e9;
        long dupSent = fakes.stream().mapToLong(FakeSource::dupSent).sum();   // 每 50 帧重复一次
        long badSent = (long) sources * 2;                                    // 每个数据源 2 条坏帧
        System.out.printf("场景一 正常负载：10 个数据源×%d 帧，接收端有效=%d，去重=%d，坏帧拒绝=%d，背压丢弃=%d，"
                + "吞吐≈%.0f 帧/s%n", framesPerSource, ingest.accepted(), ingest.duplicates(),
                ingest.rejected(), ingest.backlogDropped(), ingest.accepted() / seconds);

        AtomicInteger pass = new AtomicInteger();
        check(pass, ingest.accepted() == (long) sources * framesPerSource,
                "正常负载：有效帧 = 10×300(重复与坏帧都被拦截)");
        check(pass, ingest.rejected() == badSent, "正常负载：坏帧全部被量程/格式校验拒绝");
        check(pass, ingest.duplicates() == dupSent, "正常负载：重传帧全部被 SOURCE_ID+seq 去重");
        check(pass, ingest.backlogDropped() == 0, "正常负载：队列容量充足，零背压丢弃");

        // ---- 场景二：过载压测，单 SOURCE_ID 打满单 lane ----
        IngestService overload = new IngestService(/*laneCount*/ 1, /*queuePerLane*/ 64);
        overload.start();
        List<Thread> burst = new ArrayList<>();
        for (int i = 1; i <= sources; i++) {
            Thread t = new Thread(() -> {
                for (long seq = 1; seq <= 5000; seq++) {
                    overload.submit("T|LSV0000999|" + seq + "|60|40|50");   // 单 SOURCE_ID 快速连发
                }
            }, "burst-" + i);
            burst.add(t);
            t.start();
        }
        for (Thread t : burst) {
            t.join();
        }
        Thread.sleep(300);        // 留出消费时间
        overload.shutdown();
        long accounted = overload.accepted() + overload.duplicates() + overload.backlogDropped();
        check(pass, overload.backlogDropped() > 0, "过载压测：队满丢弃=" + overload.backlogDropped() + " > 0(背压信号)");
        check(pass, accounted == (long) sources * 5000, "过载压测：帧计数守恒(每帧要么入队处理要么丢弃计数，无一漏记)");
        System.out.println("场景二 过载：背压丢弃=" + overload.backlogDropped() + "，有效=" + overload.accepted());
        System.out.printf("ALL PASS: %d/6%n", pass.get());
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
