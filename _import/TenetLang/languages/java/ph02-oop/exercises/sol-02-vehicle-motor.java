// 来源：languages/java/ph02-oop/exercises/README.md 练习 2
// 说明：车辆继承 + 多态（Vehicle/ElectricCar/GasCar）与电机构造方法链（this(...) 委托）
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-02-vehicle-motor.java
// 运行：java VehicleMotorMain
// 验证状态：已验证：OpenJDK 17.0.16
abstract class Vehicle {
    protected String vin;
    Vehicle(String vin) { this.vin = vin; }
    abstract void start();
}

class ElectricCar extends Vehicle {
    ElectricCar(String vin) { super(vin); }
    @Override
    void start() { System.out.println(vin + " 电动车启动"); }
}

class GasCar extends Vehicle {
    GasCar(String vin) { super(vin); }
    @Override
    void start() { System.out.println(vin + " 燃油车启动"); }
}

class Motor {
    private String model;
    private int powerKw;

    Motor() {
        this("Unknown", 0);  // 委托双参构造，必须第一行
        System.out.println("无参构造委托完成，model=" + model);
    }

    Motor(String model, int powerKw) {
        this.model = model;
        this.powerKw = powerKw;
    }

    public String getModel() { return model; }
    public int getPowerKw() { return powerKw; }
}

class VehicleMotorMain {
    public static void main(String[] args) {
        Vehicle[] vehicles = { new ElectricCar("EV-001"), new GasCar("GAS-002") };
        for (Vehicle v : vehicles) {
            v.start();  // 多态：运行时绑定子类实现
        }

        Motor m = new Motor();  // 走构造方法链
        System.out.println("Motor model=" + m.getModel() + ", powerKw=" + m.getPowerKw());
    }
}
