// examples/ex07-trajectory-query/GpsPoint.java —— 轨迹采样点(record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
record GpsPoint(String vin, long atEpochSec, double lat, double lon, double speedKmh) { }
