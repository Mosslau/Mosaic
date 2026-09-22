# ph02 面向对象 OOP 示例

> 每个示例是主文档 02-oop.md 第 6 章对应示例的完整可运行版。验证环境：OpenJDK 17.0.16。

**命名说明**：为保持 `ex0X-主题` 文件名，每个文件的入口类（含 `main`）声明为**非 public**——Java 强制「public 类名与文件名一致」，非 public 类不受此限制。因此编译用文件名、运行用类名：

```bash
# 1. 编译（用文件名）
javac ex01-student.java

# 2. 运行（用入口类名）
java StudentDemo
```

| 文件 | 说明 | 入口类 | 编译 | 运行 |
|------|------|--------|------|------|
| ex01-student.java | 封装：private 字段 + getter/setter 校验不变量 | StudentDemo | `javac ex01-student.java` | `java StudentDemo` |
| ex02-vehicle.java | 继承与多态：abstract 父类 + 子类重写 start() | VehicleDemo | `javac ex02-vehicle.java` | `java VehicleDemo` |
| ex03-sensor.java | 接口解耦：readSensor 只依赖 Sensor 接口 | SensorDemo | `javac ex03-sensor.java` | `java SensorDemo` |
| ex04-record.java | record 不可变数据：withTemperature 返回新实例 | RecordDemo | `javac ex04-record.java` | `java RecordDemo` |
| ex05-sealed.java | sealed class：permits 限定子类 + instanceof 模式匹配 | SealedDemo | `javac ex05-sealed.java` | `java SealedDemo` |

> record 是 Java 16+ 特性、sealed class 是 Java 17 特性，编译运行全部示例需要 JDK 17 及以上。

全部已在本环境编译运行验证（已验证：OpenJDK 17.0.16）。
