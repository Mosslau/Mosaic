// examples/ex02-fake-vehicle-ingest/FrameCodec.java —— 协议编解码 + 单帧校验
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
//
// 教学点：真实车端协议(见主文档 2 章)多为二进制 + 校验和，接入网关(Netty)负责把它还原成
// 「一行一帧」的文本；本 codec 站在网关之后做业务校验。校验失败计数 = 数据质量第一道闸。
import java.util.Optional;

public final class FrameCodec {
    private FrameCodec() { }

    /** 解析一行协议文本，格式：T|VIN|seq|soc|kmh|motTempC */
    public static Optional<TelemetryFrame> decode(String line) {
        if (line == null || line.isBlank() || !line.startsWith("T|")) {
            return Optional.empty();
        }
        String[] parts = line.split("\\|");
        if (parts.length != 6) {
            return Optional.empty();
        }
        try {
            String vin = parts[1];
            long seq = Long.parseLong(parts[2]);
            double soc = Double.parseDouble(parts[3]);
            double kmh = Double.parseDouble(parts[4]);
            double temp = Double.parseDouble(parts[5]);
            if (!vin.startsWith("LSV") || vin.length() != 10) return Optional.empty();
            if (soc < 0.0 || soc > 100.0) return Optional.empty();        // 物理量程校验
            if (kmh < 0.0 || kmh > 220.0) return Optional.empty();
            if (temp < -40.0 || temp > 150.0) return Optional.empty();
            return Optional.of(TelemetryFrame.of(vin, seq, soc, kmh, temp));
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }
}
