// 来源：languages/java/ph02-oop/02-oop.md 第 6 章 示例 3
// 说明：接口解耦——readSensor 只依赖 Sensor 接口，不关心具体传感器类型
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex03-sensor.java
// 运行：java SensorDemo
// 验证状态：已验证：OpenJDK 17.0.16
class SensorDemo {
    public static void main(String[] args) {
        readSensor(new TemperatureSensor());
        readSensor(new PressureSensor());
    }

    static void readSensor(Sensor sensor) {
        System.out.println("读数: " + sensor.read());
    }
}

interface Sensor {
    double read();
}

class TemperatureSensor implements Sensor {
    @Override
    public double read() { return 36.5; }
}

class PressureSensor implements Sensor {
    @Override
    public double read() { return 101.3; }
}
