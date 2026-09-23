// 来源：languages/java/ph02-oop/exercises/README.md 练习 2
// 说明：设备继承 + 多态（Device/ElectricCar/GasCar）与电机构造方法链（this(...) 委托）
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-02-device-motor.java
// 运行：java DeviceMotorMain
// 验证状态：已验证：OpenJDK 17.0.16
abstract class Device {
    protected String device_id;
    Device(String device_id) { this.device_id = device_id; }
    abstract void start();
}

class ElectricCar extends Device {
    ElectricCar(String device_id) { super(device_id); }
    @Override
    void start() { System.out.println(device_id + " 电动设备启动"); }
}

class GasCar extends Device {
    GasCar(String device_id) { super(device_id); }
    @Override
    void start() { System.out.println(device_id + " 燃油设备启动"); }
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

class DeviceMotorMain {
    public static void main(String[] args) {
        Device[] devices = { new ElectricCar("EV-001"), new GasCar("GAS-002") };
        for (Device v : devices) {
            v.start();  // 多态：运行时绑定子类实现
        }

        Motor m = new Motor();  // 走构造方法链
        System.out.println("Motor model=" + m.getModel() + ", powerKw=" + m.getPowerKw());
    }
}
