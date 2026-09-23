# 03 · 单继承与接口：Java 的多态答案

> demo: `java demos/03_inheritance_interface.java`

## 1. 设计动机

C++ 的多继承威力大、陷阱深（菱形继承、二义性）；Java 的命题：**类是"一个父亲"，
接口可以有"多个干爹"**——用**单继承**保住"is-a"的简单，用**接口**拿回多态的自由。
这是对 C++ 多继承的一次著名"减法"：继承表达"是什么"（一棵树），接口表达"能做什么"
（任意多个契约），两者分家。JDK 8 又给接口加了 default 方法，让"接口演进"不再破坏
所有实现者——但也模糊了抽象类与接口的边界。

## 2. 机制拆解

```java
class Device {                      // 单根继承：Object ← Device ← Car
    void start() { /* ... */ }
}

interface Electric {                 // 契约一：能补能
    void charge();
}

interface Navigable {                // 契约二：能导航
    void navigate();
}

class Car extends Device implements Electric, Navigable {
    public void charge()   { /* 实现 Electric */ }
    public void navigate() { /* 实现 Navigable */ }
    // start() 从 Device 继承，不用重写
}
```

三个关键机制：

- **虚方法表（vtable）动态分派**：`Device v = new Car(); v.start()` 运行期查
  Car 的 vtable 找到实际实现——多态的成本是一次间接跳转；
- **接口默认方法（JDK 8）**：给接口加方法不再破坏实现者，但同名 default 冲突
  必须显式解决（`X.super.m()` 语法），复杂度随之而来；
- **继承是白盒、接口是黑盒**：子类能覆写/窥探父类实现（脆基类问题），
  接口只暴露契约——这是"组合优于继承"运动的理论根源。

## 3. 代码验证（demos/03_inheritance_interface.java）

demo 演示：① `ArrayList` 同时是 `List`/`RandomAccess`/`Cloneable`——同一对象多种身份，
传给只认接口的函数；② 动态分派——父类引用调子类覆写方法；③ default 方法演进——
往接口加方法老实现不用改；④ 展示脆基类的雏形（子类依赖父类实现细节）。

```bash
java demos/03_inheritance_interface.java
```

## 4. 代价与取舍

| 代价 | 说明 |
|------|------|
| 脆弱基类（fragile base class） | 改父类实现可能悄悄破坏子类；继承是运行时最强耦合 |
| 深继承树难维护 | 企业里 5 层以上的继承是坏味道，"组合优于继承"成铁律 |
| 接口膨胀 | 一个接口几十个方法的反模式；default 方法部分缓解但引入冲突规则 |
| 名词暴力（God Object） | "所有东西都 extends 一个基类"的设计惯性 |

**换来的**：单继承让"is-a"关系永远是一棵树——没有菱形继承、没有二义性，
OOP 建模简单清晰；接口让框架可以面向契约编程（`List` 接口换实现零改动），
这是 Spring 等框架生态的基石。Java 的成熟实践最终收敛到：**继承少用、接口多用、
组合默认**。

## 5. 对 Tenet 的启示

- ❌ **拒绝继承/类层次**（架构文档拒绝清单已记，来源含 Java）：Java 自身 20 年
  实践给出证据——脆基类、深继承是坏味道，框架层早已"接口 + 组合"化。
  Tenet 选 `struct` 组合（无继承），从语法上杜绝这一类问题
- ✅ **吸收"面向契约编程"的精神但换载体**：Java 接口的价值（依赖抽象不依赖实现）
  在 Tenet 里由**函数签名**承担——`print` 接受任意值、函数只关心参数形态，
  是"契约"的最小形式（呼应 Python 分析中"鸭子类型的最小形式"）
- 💡 Java 的教训是：**当语言缺接口，人们会发明自己的接口**（struct + 函数指针 /
  trait），说明"行为抽象"是刚需——Tenet 演进加 trait 时应学 Rust 的
  "数据 + 行为分离"，而非 Java 的"继承树"
- 💡 default 方法证明"给已发布契约加方法"是高频痛点——Tenet 若做库生态，
  版本兼容要提前设计（见 Rust 分析中 trait 演进的一致性规则）

**一句话**：Java 用「单继承 + 多接口」把多态切成 is-a 与 can-do 两半，
安全了但样板化了；Tenet 拒绝类层次，用「struct 组合 + 未来 trait」走 Rust 路线。
