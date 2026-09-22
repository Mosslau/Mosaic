// examples/ex07-trajectory-query/JobRecord.java —— 作业历史采样点(record)
// 验证环境：OpenJDK 17.0.18(Homebrew)，命令：javac -encoding UTF-8 -d /tmp/tl21-cls *.java
record JobRecord(String sourceId, long atEpochSec, double lat, double lon, double speedKmh) { }
