// 来源：languages/java/ph02-oop/02-oop.md 第 6 章 示例 2
// 说明：继承、多态与重写——abstract 父类 + 两个子类重写 start()，父类数组统一调用
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex02-vehicle.java
// 运行：java VehicleDemo
// 验证状态：已验证：OpenJDK 17.0.16
class VehicleDemo {
    public static void main(String[] args) {
        Vehicle[] vehicles = {
            new ElectricCar("EV-001", 75),
            new GasCar("GAS-002", 2.0)
        };

        for (Vehicle v : vehicles) {
            v.start();  // 动态分派到子类实现
        }
    }
}

abstract class Vehicle {
    protected String vin;
    Vehicle(String vin) { this.vin = vin; }
    abstract void start();
}

class ElectricCar extends Vehicle {
    private int batteryCapacity;
    ElectricCar(String vin, int batteryCapacity) {
        super(vin);
        this.batteryCapacity = batteryCapacity;
    }
    @Override
    void start() {
        System.out.println(vin + " 电动车启动，电池 " + batteryCapacity + " kWh");
    }
}

class GasCar extends Vehicle {
    private double engineDisplacement;
    GasCar(String vin, double engineDisplacement) {
        super(vin);
        this.engineDisplacement = engineDisplacement;
    }
    @Override
    void start() {
        System.out.println(vin + " 燃油车启动，排量 " + engineDisplacement + " L");
    }
}
