// examples/ex02-fake-source-ingest/FakeSource.java —— 模拟采集端：按协议持续生成上行帧
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 教学点：故障注入 —— 每个数据源每 50 帧故意重发上一帧(模拟采集端重传/链路重复投递)，
// 供接入层做「按 SOURCE_ID+seq 去重」验证；每个数据源还会在中间注入 2 条格式坏帧。
import java.util.concurrent.atomic.AtomicLong;

public final class FakeSource implements Runnable {
    private final String sourceId;
    private final int totalFrames;
    private final IngestService ingest;
    private final AtomicLong dupSent = new AtomicLong();

    public FakeSource(String sourceId, int totalFrames, IngestService ingest) {
        this.sourceId = sourceId;
        this.totalFrames = totalFrames;
        this.ingest = ingest;
    }

    @Override
    public void run() {
        for (long seq = 1; seq <= totalFrames; seq++) {
            String line = "T|" + sourceId + "|" + seq + "|" + (60 + seq % 40) + "|" + (seq % 80)
                    + "|" + (35 + seq % 20);
            ingest.submit(line);               // 正常帧
            if (seq % 50 == 0) {
                ingest.submit(line);           // 重复帧：接入层应识别为 dup
                dupSent.incrementAndGet();
            }
            if (seq == 25 || seq == 75) {
                ingest.submit("T|" + sourceId + "|bad|not|a|frame");   // 坏帧：解析层应拒绝
            }
        }
    }

    public long dupSent() { return dupSent.get(); }
    public String sourceId()   { return sourceId; }
}
