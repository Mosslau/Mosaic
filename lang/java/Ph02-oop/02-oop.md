# Java 面向对象 OOP 阶段

> 面向企业级后端、微服务、高并发系统和车联网数据平台，建立类设计、封装、继承、多态与接口解耦的建模能力。

## 1. 概述

Java 面向对象 OOP 阶段的目标是：**能设计清晰的类模型，理解封装、继承、多态，能用接口解耦依赖，并掌握 record 与 sealed class 的现代写法**。本阶段是 Java 企业级开发的根基——Spring 的 IOC、AOP、Repository 模式全部建立在 OOP 与接口之上。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 类与对象 | `class`、对象创建、`field`、`method` |
| 构造与关键字 | 构造方法、`this`、`static`、`final` |
| 三大特性 | 封装、继承、多态 |
| 抽象机制 | `abstract class`、`interface` |
| 方法关系 | 重写（Override）与重载（Overload） |
| 现代特性 | `record`（Java 16+）、`sealed class`（Java 17+） |

本阶段不涉及泛型、注解、反射与设计模式。

## 2. 来源与演变

OOP 思想起源于 1960 年代的 Simula，成熟于 Smalltalk。C++ 在 C 的基础上引入类与多重继承，而 Java 选择了一种更"纯化"的路线：单继承 + 接口，一切代码都必须写在类中。

| 语言 | 关键贡献 |
|------|---------|
| Simula（1967） | 提出类、对象、继承 |
| Smalltalk（1972） | 一切皆对象、消息传递、动态分派 |
| C++（1985） | 多重继承、构造/析构、访问控制 |
| Java（1995） | 单继承 + 接口、GC、引用语义、跨平台字节码 |

Java 的 OOP 取舍：单继承避免 C++ 菱形问题；接口多实现保留行为组合能力；GC 自动回收降低内存风险；引用语义让变量统一指向堆上对象。

## 3. 语法与参数

### 3.1 类与对象

类是对象的模板，定义状态（字段）和行为（方法）。

```java
public class Student {
    String name;
    int age;

    void introduce() {
        System.out.println("我叫 " + name + "，今年 " + age + " 岁");
    }
}

Student s = new Student();  // 创建对象
s.name = "Alice";
s.introduce();
```

### 3.2 构造方法、this 与构造方法链

构造方法在创建对象时初始化状态，方法名与类名相同，无返回值。

```java
public class Motor {
    String model;
    int powerKw;

    Motor() {
        this("Unknown", 0);  // 调用同类其他构造，必须第一行
    }

    Motor(String model, int powerKw) {
        this.model = model;
        this.powerKw = powerKw;
    }
}
```

- `this` 指代当前对象，区分同名字段与参数
- `this(...)` 调用同类其他构造，减少重复初始化逻辑

### 3.3 static 与实例

实例成员属于对象，`static` 成员属于类，通过 `类名.成员` 访问。

```java
public class Counter {
    int instanceCount = 0;      // 实例变量
    static int staticCount = 0; // 类变量，全实例共享

    Counter() {
        instanceCount++;
        staticCount++;
    }
}
```

`static` 方法中不能直接使用 `this` 和实例字段。

### 3.4 final 的三种用法

| 用法 | 含义 | 示例 |
|------|------|------|
| `final` 变量 | 只能赋值一次 | `final int MAX = 100;` |
| `final` 方法 | 不能被子类重写 | `final void run() {}` |
| `final` 类 | 不能被继承 | `final class MathUtils {}` |

### 3.5 封装

封装通过访问修饰符隐藏内部状态。`private` 仅限同类；`protected` 允许子类与同包；默认同包；`public` 任意可见。标准做法：字段 `private`，提供 `public` getter/setter，并在 setter 中校验不变量。

```java
public class Battery {
    private int level;  // 0 ~ 100

    public int getLevel() { return level; }

    public void setLevel(int level) {
        if (level < 0 || level > 100) {
            throw new IllegalArgumentException("电量必须在 0-100 之间");
        }
        this.level = level;
    }
}
```

### 3.6 继承

继承表达 **is-a** 关系，Java 使用 `extends`，只支持单继承。

```java
public class Vehicle {
    protected String vin;
    public void start() { System.out.println("Vehicle starting"); }
}

public class ElectricCar extends Vehicle {
    public void charge() { System.out.println(vin + " 正在充电"); }
}
```

继承表达 is-a，组合表达 has-a；组合通常更灵活，优先使用组合减少耦合。

### 3.7 多态

多态允许子类对象被当作父类使用，运行时根据实际类型调用方法。

```java
Vehicle v = new ElectricCar();
v.start();  // 实际执行 ElectricCar 的 start（若重写）
```

### 3.8 重写（Override）与重载（Overload）

| 特性 | 重载（Overload） | 重写（Override） |
|------|-----------------|-----------------|
| 位置 | 同一类中 | 父子类之间 |
| 参数列表 | 必须不同 | 必须相同 |
| 返回类型 | 可以不同 | 相同或协变返回 |
| 访问权限 | 无限制 | 子类不能缩小权限 |
| 绑定方式 | 编译期静态绑定 | 运行期动态绑定 |

```java
public class Demo {
    int add(int a, int b) { return a + b; }
    double add(double a, double b) { return a + b; }

    @Override
    public String toString() { return "Demo instance"; }
}
```

重写方法建议加 `@Override`，编译器会检查签名。

### 3.9 抽象类与接口

| 特性 | `abstract class` | `interface` |
|------|-----------------|-------------|
| 构造方法 | 有 | 没有 |
| 字段 | 可有实例字段 | 默认 `public static final` |
| 方法实现 | 可有具体方法 | Java 8+ 支持 default/static |
| 继承/实现 | 单继承 | 多实现 |
| 设计意图 | 模板，共享代码 | 能力边界，解耦依赖 |

```java
public interface Sensor {
    double read();
}

public abstract class Device {
    protected String id;
    public Device(String id) { this.id = id; }
    public abstract void report();
    public void ping() { System.out.println(id + " online"); }
}
```

### 3.10 record：不可变数据类

`record` 是 Java 16 正式引入的不可变数据类，编译器自动生成构造方法、访问器、`equals`、`hashCode`、`toString`。

```java
public record DeviceStatus(String deviceId, double temperature, long timestamp) {}
```

```java
DeviceStatus ds = new DeviceStatus("EV-001", 36.5, System.currentTimeMillis());
System.out.println(ds.deviceId());  // 访问器方法
System.out.println(ds);
```

record 字段为 `private final`，不能继承其他类（隐式 `final`），但可实现接口，适合表达 DTO、状态快照、事件数据。

### 3.11 sealed class：受控继承

`sealed class` 是 Java 17 正式引入的受控继承机制，父类用 `permits` 明确限定允许的子类。

```java
public abstract sealed class VehicleState
        permits OnlineState, OfflineState, FaultState {}

public final class OnlineState extends VehicleState {
    public double speed;
}

public final class OfflineState extends VehicleState {}

public non-sealed class FaultState extends VehicleState {
    public String code;
}
```

子类必须是 `final`、`sealed` 或 `non-sealed` 之一，适合状态机、表达式树等封闭类型层次。

## 4. 底层原理

### 4.1 对象在堆上，引用在栈上

```java
ElectricCar car = new ElectricCar();
```

- `new ElectricCar()` 在堆上创建对象实例
- `car` 是栈上的引用变量，保存对象地址
- 方法传参传递的是引用拷贝，对象本身不会被复制

Java 对象赋值/传参总是操作引用，与 C++ 值语义形成对比。

### 4.2 构造链执行顺序

创建子类对象时：父类静态初始化（一次）→ 子类静态初始化（一次）→ 父类实例字段初始化 + 父类构造 → 子类实例字段初始化 + 子类构造。

```java
class Parent {
    Parent() { System.out.println("Parent"); }
}

class Child extends Parent {
    Child() {
        System.out.println("Child");
    }
}
```

### 4.3 动态分派

多态方法调用在字节码层通过 `invokevirtual`（类）或 `invokeinterface`（接口）实现。JVM 根据对象实际类型查找方法表，运行时绑定具体实现。

```java
Sensor s = new TemperatureSensor();
s.read();  // 运行时绑定到 TemperatureSensor.read()
```

动态分派让"依赖接口而不是实现"成为可能，是 Spring IOC、策略模式、插件架构的基础。

## 5. 使用场景

| 场景 | 推荐做法 |
|------|---------|
| 建模业务实体 | 类 + 封装 |
| 扩展已有类型 | 继承 + 重写 |
| 解耦模块依赖 | 接口 + 多态 |
| 不可变数据/封闭层次 | `record` / `sealed class` |

纯算法工具函数直接用 `static` 工具类；为复用而深继承（超过 3 层）通常意味着设计问题。

## 6. 代码示例

### 示例 1：封装与学生类

```java
public class StudentDemo {
    public static void main(String[] args) {
        Student s = new Student("Alice", 20);
        s.setAge(21);
        System.out.println(s);
    }
}

class Student {
    private String name;
    private int age;

    Student(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public String getName() { return name; }
    public int getAge() { return age; }

    public void setAge(int age) {
        if (age < 0 || age > 150) {
            throw new IllegalArgumentException("年龄不合法");
        }
        this.age = age;
    }

    @Override
    public String toString() {
        return "Student{name='" + name + "', age=" + age + "}";
    }
}
```

### 示例 2：继承、多态与重写

```java
public class VehicleDemo {
    public static void main(String[] args) {
        Vehicle[] vehicles = {
            new ElectricCar("EV-001", 75),
            new GasCar("GAS-002", 2.0)
        };

        for (Vehicle v : vehicles) {
            v.start();
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
```

### 示例 3：接口解耦

```java
public class SensorDemo {
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
```

### 示例 4：record 表达设备状态

```java
public class RecordDemo {
    public static void main(String[] args) {
        DeviceStatus status = new DeviceStatus("EV-001", 36.5, 1_700_000_000_000L);
        System.out.println(status);
        System.out.println("设备 ID: " + status.deviceId());

        DeviceStatus updated = status.withTemperature(37.2);
        System.out.println(updated);
    }
}

record DeviceStatus(String deviceId, double temperature, long timestamp) {
    DeviceStatus withTemperature(double newTemp) {
        return new DeviceStatus(deviceId, newTemp, timestamp);
    }
}
```

### 示例 5：sealed class 限制状态继承

```java
public class SealedDemo {
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
```

## 7. 总结

### 关键要点

1. **对象是状态与行为的组合**——类定义模板，`new` 创建实例
2. **封装保护不变量**——字段私有化，通过受控接口访问
3. **继承表达 is-a，组合常常更灵活**——优先组合，谨慎深继承
4. **多态依赖动态分派**——父类/接口引用指向子类对象，运行时绑定实现
5. **重写必须加 `@Override`**——编译器会校验签名
6. **`record` 适合不可变数据**——自动生成构造、访问器、`equals`、`hashCode`、`toString`
7. **`sealed class` 让继承可控**——用 `permits` 明确限定子类范围
8. **Java 是引用语义 + GC**——对象在堆上，变量存引用，无需手动析构

### 与其他语言的 OOP 对比

| 特性 | Java | C++ |
|------|------|-----|
| 继承 | 单继承 + 接口多实现 | 多重继承 |
| 对象语义 | 引用语义 | 值语义或引用语义 |
| 内存管理 | GC 自动回收 | 手动 / RAII / 智能指针 |
| 抽象机制 | `abstract class` + `interface` | 纯虚类、抽象类 |
| 运行时多态 | `invokevirtual` 动态分派 | 虚函数表 |
| 重写标记 | `@Override` 注解 | `override` 关键字 |

### 阶段验收标准

- 能设计清晰的类模型，字段私有化并提供 getter/setter
- 能用 `record` 表达不可变数据
- 能解释重载和重写的区别
- 能用接口解耦依赖
- 能用 `sealed class` 限制继承层次

### 进入下一阶段前

确保能完成以下练习：
- 学生类：封装字段，提供构造方法与 getter/setter
- 车辆与电动车/燃油车子类：继承 + 多态 + 方法重写
- 电机类：构造方法链、`this` 使用
- 用 `record` 定义设备状态：不可变数据、自定义方法
- 用 `sealed class` 限制车辆状态层次：`permits` 子类
- 设备管理系统：组合多个类的完整小项目

### 推荐项目

- **学生管理系统**：学生/班级/成绩统计
- **设备管理系统**：设备基类、传感器接口、`record` 状态、`sealed class` 状态层次

### 下一阶段

[Java 常用类阶段](../Ph03-common-classes/03-common-classes.md) — String、StringBuilder、包装类、日期时间 API。
