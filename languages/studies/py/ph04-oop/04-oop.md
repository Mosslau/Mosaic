# Python 面向对象 OOP 阶段

> 在函数与模块化之上，掌握 Python 面向对象编程的核心机制：类与对象、继承与多态、property 与封装、魔术方法。能够用类组织业务模型（以设备/服务实体为载体），让代码即业务语义的直接表达。

## 1. 概述

Python OOP 阶段的目标是：**能设计职责清晰的类，理解实例变量与类变量的关键区别，用继承和多态表达"同一接口不同实现"，用 property 封装不变量校验，通过魔术方法让自定义对象像内置类型一样工作**。当函数闭包不足以组织持续变化的状态和行为时，类是最合适的抽象单元。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 类与对象 | `class`、`__init__`、`self` 约定、实例变量、类变量（共享陷阱） |
| 继承体系 | 单继承、`super().__init__()` 调用链、多态、`isinstance`/`issubclass` |
| 封装 | 命名约定（`_`/`__`）、`@property` getter/setter |
| 方法类型 | 实例方法、`@staticmethod`、`@classmethod`（一张表对比） |
| 魔术方法 | `__str__` / `__repr__`、`__eq__` / `__hash__`、`__len__` / `__getitem__` |

**范围边界**：本阶段聚焦 OOP 基础机制，不涉及 `__new__` 与元类、`@dataclass`、抽象基类（`abc`）、多重继承深入。下一阶段为 **文件操作与异常处理阶段**（ph05-file-exception）。

## 2. 来源与演变

Python OOP 融合 Smalltalk（一切皆对象）、C++（运算符重载灵感）和 Modula-3（命名约定访问控制）。关键节点：Python 2.2 新式类统一 `type`/`class`；2.6/3.0 `@property`/`@staticmethod`/`@classmethod` 成熟。Python 不用 `public`/`private`/`protected` 关键字，靠命名约定封装——"我们都是成年用户"哲学。

本文示例以 **Python 3.10+** 为基线（`match` 语句、`|` 类型联合可用），验证解释器 3.13.12。

## 3. 语法与参数

### 3.1 类定义与 `__init__`

```python
class Motor:
    """电机模型：封装转速和启停行为。"""

    def __init__(self, max_speed, brand="Default"):
        self.max_speed = max_speed       # 实例变量：每个对象独立持有
        self.brand = brand
        self._current_speed = 0          # 单下划线：约定为"内部使用"

    def start(self, target_speed):
        self._current_speed = min(target_speed, self.max_speed)
        print(f"{self.brand} 电机启动: {self._current_speed} rpm")

    def stop(self):
        self._current_speed = 0
        print(f"{self.brand} 电机停止")

m1 = Motor(3000, "Bosch")
m2 = Motor(5000, "Siemens")
m1.start(2500)      # Bosch 电机启动: 2500 rpm
m2.start(8000)      # Siemens 电机启动: 5000 rpm（被 max_speed 截断）
print(m1.max_speed)  # 3000
```

`class` 定义类，`__init__` 初始化（非构造器——对象已由 `__new__` 创建）。`self` 指向当前实例，须为第一形参。访问变量统一 `self.attr`。

### 3.2 实例变量与类变量（共享陷阱）

这是 Python OOP 最易踩的坑：**类变量在所有实例间共享**，通过实例读取正常，但通过实例赋值会创建同名实例变量将其遮蔽——修改类变量必须用 `ClassName.attr`。

```python
class Sensor:
    unit = "V"                  # 类变量：所有实例共享
    _count = 0                  # 类变量：统计实例数量

    def __init__(self, name, value):
        self.name = name        # 实例变量
        self.value = value
        Sensor._count += 1      # 必须写 Sensor._count，self._count += 1 会写入实例

s1 = Sensor("温度", 25.0)
s2 = Sensor("电压", 12.5)
print(s1.unit, s2.unit)        # V V —— 共享类变量
print(Sensor._count)            # 2

# 陷阱：通过实例赋值
s1.unit = "mV"                  
print(s1.unit, s2.unit)        # mV V —— s2 仍读取类变量
print(Sensor.unit)              # V —— 类变量未变
```

读 `self.attr` 先实例后类；写 `self.attr = val` 总写入实例。

### 3.3 `self` 是约定而非关键字

`self` 只是形参名不是保留字，但 **PEP 8 强制要求使用 `self`**（类方法用 `cls`）。

```python
class Demo:
    def show(this):     # 能用但不要这样写 —— PEP 8 要求 self
        print(f"called on {this}")
    def normal(self):   # 标准写法
        print(f"called on {self}")

d = Demo()
d.show()                # 可用
Demo.normal(d)          # 等价于 d.normal() —— 显式传 self
```

`obj.method(args)` 等价 `ClassName.method(obj, args)`，`self` 即隐式传入的 `obj`。

### 3.4 继承与 `super().__init__()`

```python
class Component:
    def __init__(self, name, sn):
        self.name = name
        self.sn = sn
    def info(self):
        return f"{self.name} [SN:{self.sn}]"

class Component(Component):
    def __init__(self, name, sn, capacity_kwh, soc=100):
        super().__init__(name, sn)          # 必须调用父类 __init__
        self.capacity = capacity_kwh
        self.soc = soc
    def info(self):                         # 重写父类方法
        base = super().info()
        return f"{base} 容量={self.capacity}kWh SOC={self.soc}%"
    def discharge(self, amount):
        self.soc = max(0, self.soc - amount)

b = Component("高压部件", "BAT-001", 70.0)
print(b.info())                        # 高压部件 [SN:BAT-001] 容量=70.0kWh SOC=100%
b.discharge(15)
print(f"SOC: {b.soc}%")               # SOC: 85%
print(isinstance(b, Component))       # True
print(issubclass(Component, Component)) # True
```

**关键**：子类必须在 `__init__` 中调用 `super().__init__()`，否则父类实例变量不初始化。

### 3.5 多态

多态核心是"同一接口，不同实现"——调用方只关心对象有何方法，不关心是哪个类。Python 鸭子类型无需显式继承同一基类。

```python
class TemperatureSensor:
    def read(self): return 25.5
    def unit(self): return "Celsius"

class VoltageSensor:
    def read(self): return 12.8
    def unit(self): return "Volt"

def collect_data(sensors):
    for s in sensors:
        print(f"{type(s).__name__}: {s.read()} {s.unit()}")

collect_data([TemperatureSensor(), VoltageSensor()])
# TemperatureSensor: 25.5 Celsius
# VoltageSensor: 12.8 Volt
```

### 3.6 封装：命名约定与 name mangling

Python 没有 `private` 关键字，靠命名约定控制可见性：

| 命名 | 含义 | 示例 |
|------|------|------|
| `attr` | 公开 | `self.name` |
| `_attr` | 约定内部使用 | `self._cache` |
| `__attr` | name mangling → `_ClassName__attr` | `self.__secret` |
| `__attr__` | 系统魔术方法，勿自定义 | `__init__` |

```python
class Config:
    def __init__(self, api_key):
        self._timeout = 30                  # 约定：内部使用
        self.__api_key = api_key            # name mangling → _Config__api_key
    def _validate(self):                    # 约定：内部方法
        return len(self.__api_key) >= 8
    def connect(self):
        if self._validate(): print("连接成功")

cfg = Config("sk-abc12345")
cfg.connect()                    # 连接成功
print(cfg._timeout)              # 30 —— 能访问但不依赖
print(cfg._Config__api_key)      # sk-abc12345 —— 仍可强制访问
```

`__attr` 的 name mangling 不是安全机制，意在防子类意外覆盖——Python 鼓励"我们都是成年用户"。

### 3.7 `@property`：方法当属性用

`@property` 让方法像属性一样访问，适合需校验/只读/计算的属性。不需要校验直接用实例变量。

```python
class Device:
    def __init__(self, device_id, speed=0):
        self.device_id = device_id
        self._speed = speed

    @property
    def speed(self):
        return self._speed          # getter：像读属性

    @speed.setter
    def speed(self, value):
        if value < 0:
            raise ValueError(f"速度不能为负: {value}")
        if value > 240:
            raise ValueError(f"速度不能超过 240: {value}")
        self._speed = value         # setter：像赋值

v = Device("DEVICE_ID12345")
v.speed = 120          # 调用 setter
print(v.speed)         # 120 —— 调用 getter
try:
    v.speed = -10      # 触发校验
except ValueError as e:
    print(f"校验失败: {e}")
```

### 3.8 `@staticmethod` vs `@classmethod`

| 维度 | 实例方法 | `@staticmethod` | `@classmethod` |
|------|---------|----------------|----------------|
| 第一参数 | `self`（实例） | 无隐式参数 | `cls`（类本身） |
| 访问实例变量 | 是 | 否 | 否 |
| 访问类变量 | 是 | 否（除非通过类名） | 是 |
| 典型用途 | 操作具体对象 | 归类于此的工具函数 | 工厂方法 |

```python
class ComponentPack:
    nominal_voltage = 400.0
    def __init__(self, capacity, module_count):
        self.capacity = capacity; self.module_count = module_count
    def energy(self):                      # 实例方法
        return self.capacity * ComponentPack.nominal_voltage / 1000.0
    @staticmethod
    def kwh_to_ah(kwh, voltage=400.0):     # 工具函数
        return kwh * 1000.0 / voltage
    @classmethod
    def from_energy(cls, kwh, module_count):  # 工厂方法
        return cls(kwh * 1000.0 / cls.nominal_voltage, module_count)

pack = ComponentPack(200.0, 8)
print(f"能量: {pack.energy():.1f}kWh")             # 能量: 80.0kWh
print(f"60kWh={ComponentPack.kwh_to_ah(60):.0f}Ah")  # 60kWh=150Ah
p2 = ComponentPack.from_energy(100.0, 12)
print(f"容量: {p2.capacity:.0f}Ah, 模组: {p2.module_count}")  # 容量: 250Ah, 模组: 12
```

### 3.9 常见魔术方法

魔术方法（dunder methods）让对象融入语言协议——可打印、可比较、可作容器使用。

```python
class Component:
    def __init__(self, name, cap, soc):
        self.name = name; self.cap = cap; self.soc = soc
    def __str__(self):       # print()/str() —— 给用户看
        return f"Component({self.name}, {self.cap}kWh, SOC={self.soc}%)"
    def __repr__(self):      # repr()/调试 —— 给开发者看
        return f"Component({self.name!r}, {self.cap!r}, {self.soc!r})"
    def __eq__(self, other): # == 比较
        if not isinstance(other, Component): return NotImplemented
        return self.name == other.name
    def __hash__(self):      # 放入 set/dict key 的前提
        return hash(self.name)
    def __lt__(self, other): # < 比较，按 SOC 排序
        if not isinstance(other, Component): return NotImplemented
        return self.soc < other.soc

b1 = Component("BT-001", 70.0, 85)
b2 = Component("BT-001", 70.0, 85)
b3 = Component("BT-002", 50.0, 60)
print(b1)                       # Component(BT-001, 70.0kWh, SOC=85%)  —— __str__
print(repr(b1))                 # Component('BT-001', 70.0, 85)       —— __repr__
print(b1 == b2, len({b1, b2, b3}))  # True 2 —— __eq__/__hash__：同名即重复
print(sorted([b1, b3])[0])      # Component(BT-002, ...) —— __lt__ 按 SOC
```

六种最常用魔术方法速查：

| 魔术方法 | 触发 | 对应操作 |
|----------|------|---------|
| `__str__` | `print(obj)`、`str(obj)` | 用户可读表示 |
| `__repr__` | `repr(obj)`、交互环境直接输入 | 开发者精确表示 |
| `__eq__` | `a == b` | `==` 运算符 |
| `__hash__` | `hash(obj)`、放入 set/dict key | `hash()` |
| `__len__` | `len(obj)` | `len()` |
| `__getitem__` | `obj[key]`、`for x in obj` | `[]` 索引/迭代 |

**重要**：定义 `__eq__` 而未定义 `__hash__` 时，Python 将 `__hash__` 设为 `None` 导致对象不可哈希。须同时定义二者并保证 `a == b` 蕴含 `hash(a) == hash(b)`。

## 4. 底层原理

### 4.1 类也是对象

Python 中类本身是 `type` 的实例，`class` 是 `type()` 的语法糖。`obj.attr` 查找链：实例 `__dict__` → 类 `__dict__` → 父类按 **MRO**（C3 线性化）依次。这解释了类变量陷阱：赋值写实例 `__dict__`，读取先实例后类。

```python
Motor = type("Motor", (object,), {"max_rpm": 5000})
m = Motor()
print(type(m), type(Motor))  # <class '__main__.Motor'> <class 'type'>

class A:
    def who(self): return "A"
class B(A):
    def who(self): return "B"
class C(A):
    def who(self): return "C"
class D(B, C):
    pass
print(D.mro())       # [D, B, C, A, object]
print(D().who())     # B —— 按 MRO 顺序第一个找到
```

## 5. 使用场景

| 场景 | 推荐方式 | 原因 |
|------|---------|------|
| 表达稳定的业务实体 | `class` | 数据 + 行为聚合体，语义清晰 |
| 多种相似但有差异的类型 | 继承 + 多态 | 父类定义接口，子类差异化实现 |
| 需要校验的属性 | `@property` + setter | 赋值时强制不变量 |
| 不依赖实例的归类函数 | `@staticmethod` | 明确表示"只归类于此" |
| 工厂方法创建对象 | `@classmethod` | 访问类变量，子类继承自动适配 |
| 对象需可打印/可比较/可哈希 | `__str__`/`__eq__`/`__hash__` | 融入语言协议 |
| 对象行为像容器 | `__len__`/`__getitem__` | 支持 `len()` 和 `[]` 索引 |

**不适合**：无关联函数用模块（ph03）；纯数据载体用 `dict`/`tuple`；超 3 层继承用组合；跨对象可变共享检查类变量陷阱。

## 6. 代码示例

> 本节每个示例的完整可运行文件在 [`examples/`](./examples/) 目录，验证环境 Python 3.13.12，运行命令统一 `python3 <文件名>`（命令见 examples/README.md）。

### 示例 1：类变量共享陷阱

```python
class Counter:
    count = 0
    def __init__(self, name):
        self.name = name; Counter.count += 1  # 正确：通过类名修改
    def bad_inc(self):
        self.count += 1    # 陷阱：创建实例变量遮蔽类变量

c1 = Counter("a"); c2 = Counter("b")
print(f"类:{Counter.count} c1:{c1.count} c2:{c2.count}")  # 类:2 c1:2 c2:2
c1.bad_inc(); c1.bad_inc(); c2.bad_inc()
print(f"类:{Counter.count} c1:{c1.count} c2:{c2.count}")  # 类:2 c1:4 c2:3
```

完整文件：`examples/ex01-class-var.py`

### 示例 2：继承链与多态 —— 电机控制

```python
class Motor:
    def __init__(self, name, max_rpm):
        self.name = name; self.max_rpm = max_rpm
    def control_signal(self, pct):
        raise NotImplementedError("子类必须实现")

class DCMotor(Motor):
    def control_signal(self, pct):
        return f"{self.name} DC {(pct/100)*12:.1f}V, {int(self.max_rpm*pct/100)}rpm"

class StepperMotor(Motor):
    def __init__(self, name, max_rpm, steps=200):
        super().__init__(name, max_rpm); self.steps = steps
    def control_signal(self, pct):
        return f"{self.name} 步进 {pct/100*1000:.0f}Hz {self.steps}步/转"

for m in [DCMotor("驱动电机", 8000), StepperMotor("转向电机", 1000)]:
    print(m.control_signal(50))
print(isinstance(StepperMotor("x", 100), Motor))  # True
```

完整文件：`examples/ex02-inherit-polymorphism.py`

### 示例 3：@property —— 部件 SOC 边界保护

```python
class Component:
    def __init__(self, cap):
        self.cap = cap; self._soc = 100.0
    @property
    def soc(self): return self._soc
    @property
    def available(self): return self.cap * self._soc / 100.0
    def charge(self, a):
        n = self._soc + a
        if n > 100: raise ValueError(f"过充: 当前{self._soc}%")
        self._soc = n
    def discharge(self, a):
        n = self._soc - a
        if n < 0: raise ValueError(f"过放: 当前{self._soc}%")
        self._soc = n

b = Component(70.0)
print(f"SOC={b.soc}% 可用={b.available:.1f}kWh")  # SOC=100.0% 可用=70.0kWh
b.discharge(30); print(f"SOC={b.soc}%")            # SOC=70.0%
b.charge(15);    print(f"SOC={b.soc}%")            # SOC=85.0%
try: b.discharge(200)
except ValueError as e: print(f"失败: {e}")
```

完整文件：`examples/ex03-property-component.py`

### 示例 4：魔术方法 —— 设备容器支持 len/索引/比较

```python
class SensorModule:
    def __init__(self, sn, stype, unit):
        self.sn = sn; self.stype = stype; self.unit = unit
    def __repr__(self): return f"SensorModule({self.sn!r}, {self.stype!r})"

class Device:
    def __init__(self, did, modules=None):
        self.did = did; self._ms = list(modules) if modules else []
    def add(self, m): self._ms.append(m)
    def __len__(self): return len(self._ms)
    def __getitem__(self, i): return self._ms[i]
    def __contains__(self, sn): return any(m.sn == sn for m in self._ms)
    def __eq__(self, o):
        if not isinstance(o, Device): return NotImplemented
        return self.did == o.did
    def __hash__(self): return hash(self.did)
    def __str__(self): return f"Device({self.did}, {len(self)}模块)"

dev = Device("VCU-001")
for sn, st in [("T-01","温度"), ("V-02","电压"), ("C-03","电流")]:
    dev.add(SensorModule(sn, st, "N/A"))
print(dev, f"len={len(dev)} [0]={dev[0]}")  # Device(VCU-001, 3模块) len=3 ...
print("T-01" in dev, dev == Device("VCU-001"))  # True True
```

完整文件：`examples/ex04-magic-methods.py`

### 示例 5：设备管理系统

```python
class Component:
    def __init__(self, pid, name):
        self.pid = pid; self.name = name; self._status = "offline"
    @property
    def status(self): return self._status
    def online(self): self._status = "online"
    def __repr__(self): return f"{type(self).__name__}({self.pid!r}, {self.name!r})"

class Sensor(Component):
    def __init__(self, pid, name, unit, value=0.0):
        super().__init__(pid, name); self.unit = unit; self.value = value
    def read(self): return self.value
    def __str__(self): return f"[{self.status}] {self.name}: {self.value}{self.unit}"

class Actuator(Component):
    def __init__(self, pid, name, max_out):
        super().__init__(pid, name); self.max_out = max_out; self._cur = 0
    def control(self, pct): self._cur = min(pct, 100) * self.max_out / 100.0
    def __str__(self): return f"[{self.status}] {self.name}: {self._cur:.0f}/{self.max_out}"

class DeviceManager:
    def __init__(self, name): self.name = name; self.comps = []
    def add(self, c): self.comps.append(c)
    def online_all(self):
        for c in self.comps: c.online()
    @property
    def online_n(self): return sum(1 for c in self.comps if c.status == "online")
    def report(self):
        print(f"=== {self.name} ===")
        for c in self.comps: print(c)
        print(f"在线: {self.online_n}/{len(self.comps)}")

mgr = DeviceManager("前电机控制器")
mgr.add(Sensor("T-001", "绕组温度", "°C", 32.5))
mgr.add(Sensor("V-001", "母线电压", "V", 400.0))
mgr.add(Actuator("M-001", "驱动电机", 5000))
mgr.online_all(); mgr.comps[2].control(60); mgr.report()
```

完整文件：`examples/ex05-device-manager.py`

## 7. 总结

### 关键要点

1. **`__init__` 是初始化非构造器**：对象由 `__new__` 创建，`__init__` 只设初始属性
2. **类变量 vs 实例变量**：`self.attr = val` 写实例，`ClassName.attr` 改类变量；赋值遮蔽类变量
3. **`self` 是约定**：实例方法第一形参，PEP 8 命名 `self`
4. **继承必调 `super().__init__()`**：否则父类实例变量不初始化
5. **鸭子类型多态**：无需继承同一基类，方法匹配即可互操作
6. **封装靠约定**：`_single` 内部，`__double` name mangling
7. **`@property` 校验融入赋值**：getter 只读/计算，setter 不变量
8. **staticmethod vs classmethod**：不需实例/类用前者，需类数据/工厂用后者
9. **魔术方法融入协议**：`__str__`→print、`__eq__`→==、`__len__`→len()、`__getitem__`→[]
10. **组合优先于深继承**：超 3 层继承树用组合

### 跨语言对比：OOP

| 维度 | Python | Java | C++ |
|------|--------|------|-----|
| 类定义 | `class Name:` | `class Name {}` | `class Name {};` |
| 初始化 | `__init__(self)` | 同名构造器 | 同名构造器 |
| this/self | `self` 显式形参 | `this` 隐式关键字 | `this` 隐式指针 |
| 可见性 | `_`/`__` 命名约定 | private/public/protected | private/public/protected |
| 继承 | `class Child(Parent):` | `class Child extends Parent` | `class Child : public Parent` |
| 多态 | 鸭子类型（动态） | 接口/抽象类（静态） | 虚函数+vtable（静态） |
| 多继承 | 支持（MRO C3） | 不支持 | 支持（虚继承） |
| 运算符重载 | 魔术方法 | 不支持 | operator+ 等 |
| 属性控制 | `@property` | getter/setter | getter/setter |

### 阶段验收清单

- [ ] 能设计职责清晰的类，合理划分实例变量与类变量，说清赋值遮蔽陷阱
- [ ] 能写 `super().__init__()` 继承链，用 `isinstance` / `issubclass` 校验类型关系
- [ ] 能利用多态（含鸭子类型）让同一入口函数处理不同类型的对象
- [ ] 能用 `@property` + setter 校验不变量，区分只读属性与可写属性
- [ ] 能区分 `@staticmethod` / `@classmethod`，说明各自典型用途
- [ ] 能实现 `__str__` / `__repr__` / `__eq__` / `__hash__`，并说清 `__eq__` 与 `__hash__` 必须成对定义

### 动手练习

本阶段练习见 [exercises/](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：学生类、设备类、传感器类、配置管理类共 4 题。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [project/](./project/)：**设备管理系统**（`Component` + `Sensor`/`Actuator` 子类多态 + `Device` 组合 + `DeviceManager` 统一管理，支持 JSON 持久化）。

- [ ] 完成 exercises 全部练习并对照参考实现复盘
- [ ] 独立完成 project 并通过其验收标准

### 下一阶段

[文件操作与异常处理阶段](../ph05-file-exception/05-file-exception.md)—— `open`/`with`、`txt`/`csv`/`json` 读写、`try`/`except`/`finally`、自定义异常。
