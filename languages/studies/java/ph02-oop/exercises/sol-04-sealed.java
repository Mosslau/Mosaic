// 来源：languages/java/ph02-oop/exercises/README.md 练习 4
// 说明：sealed class 设备状态层次——permits 限定三个子类，instanceof 模式匹配分派
// 验证环境：OpenJDK 17.0.16（sealed class 需 Java 17）
// 编译：javac sol-04-sealed.java
// 运行：java SealedMain
// 验证状态：已验证：OpenJDK 17.0.16
sealed class DeviceState permits OnlineState, OfflineState, FaultState {}

final class OnlineState extends DeviceState {
    double speed;
    OnlineState(double speed) { this.speed = speed; }
}

final class OfflineState extends DeviceState {}

non-sealed class FaultState extends DeviceState {
    String code;
    FaultState(String code) { this.code = code; }
}

// 层次之外的类无法继承 DeviceState：
// class HackedState extends DeviceState {}  // 编译错误：不允许的扩展

class SealedMain {
    static void describe(DeviceState state) {
        if (state instanceof OnlineState s) {
            System.out.println("在线，速度 " + s.speed);
        } else if (state instanceof OfflineState) {
            System.out.println("离线");
        } else if (state instanceof FaultState s) {
            System.out.println("故障，代码 " + s.code);
        }
    }

    public static void main(String[] args) {
        describe(new OnlineState(60.0));
        describe(new OfflineState());
        describe(new FaultState("E123"));
    }
}
