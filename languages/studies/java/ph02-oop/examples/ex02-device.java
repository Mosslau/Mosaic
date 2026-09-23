// 来源：languages/java/ph02-oop/02-oop.md 第 6 章 示例 2
// 说明：继承、多态与重写——abstract 父类 + 两个子类重写 start()，父类数组统一调用
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex02-device.java
// 运行：java DeviceDemo
// 验证状态：已验证：OpenJDK 17.0.16
class DeviceDemo {
    public static void main(String[] args) {
        Device[] devices = {
            new ElectricCar("EV-001", 75),
            new GasCar("GAS-002", 2.0)
        };

        for (Device v : devices) {
            v.start();  // 动态分派到子类实现
        }
    }
}

abstract class Device {
    protected String device_id;
    Device(String device_id) { this.device_id = device_id; }
    abstract void start();
}

class ElectricCar extends Device {
    private int componentCapacity;
    ElectricCar(String device_id, int componentCapacity) {
        super(device_id);
        this.componentCapacity = componentCapacity;
    }
    @Override
    void start() {
        System.out.println(device_id + " 电动设备启动，部件 " + componentCapacity + " kWh");
    }
}

class GasCar extends Device {
    private double engineDisplacement;
    GasCar(String device_id, double engineDisplacement) {
        super(device_id);
        this.engineDisplacement = engineDisplacement;
    }
    @Override
    void start() {
        System.out.println(device_id + " 燃油设备启动，排量 " + engineDisplacement + " L");
    }
}
