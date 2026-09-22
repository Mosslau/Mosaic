# ph04 面向对象 OOP 阶段 练习

> 先自己做，再对照 sol-* 参考实现复盘。每题标注难度（★~★★★）。
> 验证环境：Python 3.13.12。参考实现在对应 `sol-0N-*.py` 文件，做完再看。

## 练习 1：学生类（★）

**目标**：实现 `Student` 类，管理姓名与成绩，支持平均分计算和按平均分排序。

**要求**：
- `__init__(name)` 记录姓名，内部用列表存成绩
- `add_score(score)` 添加成绩（0~100 之外抛 `ValueError`）
- `average()` 返回平均分，无成绩时返回 `0.0`
- 实现 `__lt__`：按平均分比较，让 `sorted(students)` 升序生效
- 实现 `__eq__` / `__hash__`：同名 `Student` 视为同一人，可放入 `set`

**验收**：
- 小明成绩 `[80, 100]` → `average()` 返回 `90.0`
- `sorted([小刚(70), 小明(90)])` 输出小刚在前
- 两个同名 `Student` 对象 `==` 为 `True`，`len({同名, 同名})` 为 `1`

## 练习 2：车辆类（★★）

**目标**：实现 `Vehicle` 基类与 `ElectricVehicle` 子类，演示继承与多态。

**要求**：
- `Vehicle(brand, speed=0)`：`accelerate(delta)`（速度不低于 0）、`describe()` 返回描述字符串
- `ElectricVehicle(brand, battery_cap)` 继承 `Vehicle`，在 `__init__` 中调用 `super().__init__()`
- 子类新增 `range()`（每 kWh 续航 6 km）与 `charge(amount)`（SOC 上限 100%）
- 子类**重写** `describe()`，用 `super().describe()` 复用父类逻辑再追加电池信息
- 写一个 `show_vehicle(v)` 函数：对任何车辆对象调用 `describe()`（多态入口）

**验收**：
- `ElectricVehicle("Tesla", 70).range()` → `420`
- `ElectricVehicle` 的 `describe()` 输出包含父类的速度信息和子类的电池/续航信息
- 同一个 `show_vehicle` 函数传给基类与子类对象，输出各自的 `describe()`

## 练习 3：传感器类（★★）

**目标**：实现 `Sensor` 基类与两个子类，用多态 `read()` 统一采集，用类变量统计数量。

**要求**：
- `Sensor(name, unit)` 基类：`read()` 抛 `NotImplementedError`；`__str__` 输出 `[类型] 名称: 读数单位`
- 类变量 `count` 统计已创建的传感器总数，在 `__init__` 中通过 `Sensor.count` 自增
- `TemperatureSensor`（单位 `°C`）与 `VoltageSensor`（单位 `V`）子类各自实现 `read()`
- 写 `collect_all(sensors)`：遍历调用 `read()` 打印（多态入口）

**验收**：
- `collect_all([温度(25.5), 电压(12.8)])` 输出两类读数，格式正确
- 创建 3 个传感器对象后 `Sensor.count == 3`

## 练习 4：配置管理类（★★★）

**目标**：实现 `Config` 类，用 `@property` 做不可变与范围校验，支持 dict 导出导入。

**要求**：
- `Config(api_key, timeout=30)`：`api_key` 只读（只写 getter，不写 setter）
- `timeout` 用 `@property` + setter 校验，必须在 5~300 之间，否则抛 `ValueError`
- `to_dict()` 导出 `{"api_key": ..., "timeout": ...}`；`@classmethod from_dict(data)` 重建对象
- 实现 `__eq__` / `__hash__`：`api_key` 相同即相等

**验收**：
- `cfg.timeout = 10` 成功；`cfg.timeout = 400` 抛 `ValueError`
- `cfg.api_key = "hacked"` 抛 `AttributeError`（只读）
- `Config.from_dict(cfg.to_dict()) == cfg` 为 `True`
- 提示：`__init__` 里写私有字段 `self._timeout = value` 可直接赋值，再显式调用一次 setter 路径完成首轮校验

完成 4 题后，进入阶段项目（见 `04-oop.md` 第 7 章或 `project/`）。
