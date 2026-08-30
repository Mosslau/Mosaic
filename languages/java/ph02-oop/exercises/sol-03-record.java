// 来源：languages/java/ph02-oop/exercises/README.md 练习 3
// 说明：record 设备状态——不可变快照，isOverheated 判断，"修改"返回新实例
// 验证环境：OpenJDK 17.0.16（record 需 Java 16+）
// 编译：javac sol-03-record.java
// 运行：java RecordMain
// 验证状态：已验证：OpenJDK 17.0.16
record DeviceStatus(String deviceId, double temperature, long timestamp) {
    boolean isOverheated(double threshold) {
        return temperature > threshold;
    }

    DeviceStatus withTemperature(double newTemp) {
        return new DeviceStatus(deviceId, newTemp, timestamp);
    }
}

class RecordMain {
    public static void main(String[] args) {
        DeviceStatus status = new DeviceStatus("EV-001", 85.0, 0L);
        System.out.println("过热(阈值80): " + status.isOverheated(80.0));  // true

        DeviceStatus updated = status.withTemperature(60.0);
        System.out.println("新实例: " + updated);
        System.out.println("原实例温度不变: " + status.temperature());  // 85.0
    }
}
