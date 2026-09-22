// 来源：languages/java/ph02-oop/02-oop.md 第 6 章 示例 4
// 说明：record 表达设备状态——不可变数据，withTemperature 返回新实例而非修改原实例
// 验证环境：OpenJDK 17.0.16（record 是 Java 16+ 特性，需 16 及以上）
// 编译：javac ex04-record.java
// 运行：java RecordDemo
// 验证状态：已验证：OpenJDK 17.0.16
class RecordDemo {
    public static void main(String[] args) {
        DeviceStatus status = new DeviceStatus("EV-001", 36.5, 1_700_000_000_000L);
        System.out.println(status);
        System.out.println("设备 ID: " + status.deviceId());

        DeviceStatus updated = status.withTemperature(37.2);
        System.out.println(updated);
        System.out.println("原实例不变: " + status.temperature());  // 36.5，record 不可变
    }
}

record DeviceStatus(String deviceId, double temperature, long timestamp) {
    DeviceStatus withTemperature(double newTemp) {
        return new DeviceStatus(deviceId, newTemp, timestamp);
    }
}
