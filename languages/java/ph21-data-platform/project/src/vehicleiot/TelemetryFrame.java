// project/src/vehicleiot/TelemetryFrame.java —— 遥测帧：协议解码 + 校验 + 不可变载体
package vehicleiot;
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-proj src/vehicleiot/*.java
//
// 帧格式(教学用文本协议，Netty 网关按行解码后交给本类)：
//   T|<VIN>|<seq>|<socPct>|<kmh>|<motorTempC>
import java.util.Optional;

public record TelemetryFrame(String vin, long seq, double socPct, double kmh, double motorTempC) {
    /** 解码一行并做单帧量程校验；格式/越界返回 empty(接入层拒绝)。 */
    public static Optional<TelemetryFrame> decode(String line) {
        if (line == null || !line.startsWith("T|")) {
            return Optional.empty();
        }
        String[] p = line.split("\\|");
        if (p.length != 6) {
            return Optional.empty();
        }
        try {
            String vin = p[1];
            long seq = Long.parseLong(p[2]);
            double soc = Double.parseDouble(p[3]);
            double kmh = Double.parseDouble(p[4]);
            double temp = Double.parseDouble(p[5]);
            if (!vin.startsWith("LSV") || vin.length() != 10
                    || soc < 0.0 || soc > 100.0 || kmh < 0.0 || kmh > 220.0
                    || temp < -40.0 || temp > 150.0) {
                return Optional.empty();
            }
            return Optional.of(new TelemetryFrame(vin, seq, soc, kmh, temp));
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }
}
