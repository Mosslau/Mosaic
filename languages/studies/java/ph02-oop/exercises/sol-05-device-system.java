// 来源：languages/java/ph02-oop/exercises/README.md 练习 5
// 说明：设备管理系统——abstract 基类 + 接口 + 注册表，组合本阶段全部知识点
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-05-device-system.java
// 运行：java DeviceSystemMain
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.ArrayList;
import java.util.List;

interface Sensor {
    double read();
}

abstract class Device {
    private final String id;
    private final String name;

    Device(String id, String name) {
        this.id = id;
        this.name = name;
    }

    public String getId() { return id; }
    public String getName() { return name; }

    abstract void report();
}

class TemperatureSensor extends Device implements Sensor {
    private double temperature;

    TemperatureSensor(String id, String name, double temperature) {
        super(id, name);
        this.temperature = temperature;
    }

    @Override
    public double read() { return temperature; }

    @Override
    void report() {
        System.out.println("[" + getId() + "] " + getName() + " 温度读数: " + read() + " °C");
    }
}

class PressureDevice extends Device {
    private double pressureKpa;

    PressureDevice(String id, String name, double pressureKpa) {
        super(id, name);
        this.pressureKpa = pressureKpa;
    }

    @Override
    void report() {
        System.out.println("[" + getId() + "] " + getName() + " 压力: " + pressureKpa + " kPa");
    }
}

class DeviceRegistry {
    private final List<Device> devices = new ArrayList<>();

    void add(Device device) {
        devices.add(device);
    }

    void reportAll() {
        for (Device d : devices) {
            d.report();  // 多态：运行时绑定子类实现
        }
    }
}

class DeviceSystemMain {
    public static void main(String[] args) {
        DeviceRegistry registry = new DeviceRegistry();
        registry.add(new TemperatureSensor("T-001", "部件温度传感器", 36.5));
        registry.add(new TemperatureSensor("T-002", "电机温度传感器", 58.2));
        registry.add(new PressureDevice("P-001", "胎压监测", 250.0));
        registry.reportAll();
    }
}
