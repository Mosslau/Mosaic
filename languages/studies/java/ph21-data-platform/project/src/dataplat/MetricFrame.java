// project/src/dataplat/MetricFrame.java —— 指标帧：协议解码 + 校验 + 不可变载体
package dataplat;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/dataplat/*.java
//
// 帧格式(教学用文本协议，Netty 网关按行解码后交给本类)：
//   T|<SOURCE_ID>|<seq>|<cpuPct>|<latencyMs>|<diskTempC>
import java.util.Optional;

public record MetricFrame(String sourceId, long seq, double cpuPct, double latencyMs, double diskTempC) {
    /** 解码一行并做单帧量程校验；格式/越界返回 empty(接入层拒绝)。 */
    public static Optional<MetricFrame> decode(String line) {
        if (line == null || !line.startsWith("T|")) {
            return Optional.empty();
        }
        String[] p = line.split("\\|");
        if (p.length != 6) {
            return Optional.empty();
        }
        try {
            String sourceId = p[1];
            long seq = Long.parseLong(p[2]);
            double soc = Double.parseDouble(p[3]);
            double latencyMs = Double.parseDouble(p[4]);
            double temp = Double.parseDouble(p[5]);
            if (!sourceId.startsWith("LSV") || sourceId.length() != 10
                    || soc < 0.0 || soc > 100.0 || latencyMs < 0.0 || latencyMs > 220.0
                    || temp < -40.0 || temp > 150.0) {
                return Optional.empty();
            }
            return Optional.of(new MetricFrame(sourceId, seq, soc, latencyMs, temp));
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }
}
