# ph02 面向对象 OOP 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.16。编译统一用 `javac <文件名>.java`，运行用 `java <入口类名>`。

## 练习 1：学生类建模（★）

**目标**：用封装建一个学生类。
**要求**：字段 `name`、`age`、`score` 全部 `private`；提供构造方法初始化；`setScore` 校验分数必须在 0~100，越界抛 `IllegalArgumentException`；重写 `toString` 返回 `Student{name='Alice', age=20, score=92.5}` 格式。
**验收**：创建 `Student("Alice", 20)`、`setScore(92.5)` 后打印输出 `Student{name='Alice', age=20, score=92.5}`；`setScore(120)` 被拦截并打印错误信息。

## 练习 2：车辆与电机建模（★★）

**目标**：用继承 + 多态建模车辆层次，并用构造方法链建模电机。
**要求**：
- 抽象类 `Vehicle`（字段 `vin`，抽象方法 `start()`），子类 `ElectricCar` 和 `GasCar` 各自重写 `start()`；用 `Vehicle[]` 数组统一调用 `start()` 展示多态。
- 类 `Motor`（字段 `model`、`powerKw`）：无参构造通过 `this(...)` 委托给双参构造，演示构造方法链。
**验收**：数组中电动车输出「EV-001 电动车启动」，燃油车输出「GAS-002 燃油车启动」；`new Motor()` 打印委托构造的痕迹（默认 model 为 "Unknown"）。

## 练习 3：用 record 定义设备状态（★★）

**目标**：用 `record` 表达不可变的设备状态快照。
**要求**：定义 `record DeviceStatus(String deviceId, double temperature, long timestamp)`；添加一个 `isOverheated(double threshold)` 方法判断温度是否超阈值；演示「修改」状态时返回新 record 实例而非改原实例。
**验收**：`new DeviceStatus("EV-001", 85.0, 0L).isOverheated(80.0)` 返回 `true`；原实例的 `temperature()` 不受「修改」影响。

## 练习 4：用 sealed class 限制状态继承层次（★★★）

**目标**：用 `sealed class` + `permits` 建一个封闭的设备状态层次。
**要求**：`sealed` 父类 `DeviceState` 只允许 `OnlineState`、`OfflineState`、`FaultState` 三个子类（子类用 `final` 或 `non-sealed`）；写一个方法接收 `DeviceState`，用 `instanceof` 模式匹配分别处理三种状态并打印描述。
**验收**：传入 `new FaultState("E123")` 输出「故障，代码 E123」；层次之外的类无法继承 `DeviceState`（可写一行注释说明编译报错）。

## 练习 5：设备管理系统（★★★）

**目标**：组合前四题的知识，写一个内存版设备管理系统。
**要求**：`Device` 抽象基类（`id`、`name`，抽象方法 `report()`）；`Sensor` 接口（`double read()`）；至少两个具体设备类（如 `TemperatureSensor`、`PressureDevice`）分别体现继承与接口实现；用一个 `DeviceRegistry` 类管理设备列表，支持「添加设备」「遍历全部设备调用 report()」。
**验收**：注册 3 台设备后遍历输出每台设备的 report 信息；`TemperatureSensor` 的 report 中包含 `read()` 的读数。
