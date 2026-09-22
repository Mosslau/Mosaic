// 来源：languages/java/ph02-oop/02-oop.md 第 6 章 示例 5
// 说明：sealed class 限制状态继承——permits 限定子类范围，instanceof 模式匹配遍历封闭层次
// 验证环境：OpenJDK 17.0.16（sealed class 是 Java 17 特性，需 17 及以上）
// 编译：javac ex05-sealed.java
// 运行：java SealedDemo
// 验证状态：已验证：OpenJDK 17.0.16
class SealedDemo {
    public static void main(String[] args) {
        describe(new OnlineState(60.0));
        describe(new OfflineState());
        describe(new FaultState("E123"));
    }

    static void describe(VehicleState state) {
        if (state instanceof OnlineState s) {
            System.out.println("在线，速度 " + s.speed);
        } else if (state instanceof OfflineState) {
            System.out.println("离线");
        } else if (state instanceof FaultState s) {
            System.out.println("故障，代码 " + s.code);
        } else {
            throw new IllegalStateException("未知状态");
        }
    }
}

abstract sealed class VehicleState
        permits OnlineState, OfflineState, FaultState {}

final class OnlineState extends VehicleState {
    double speed;
    OnlineState(double speed) { this.speed = speed; }
}

final class OfflineState extends VehicleState {}

non-sealed class FaultState extends VehicleState {
    String code;
    FaultState(String code) { this.code = code; }
}
