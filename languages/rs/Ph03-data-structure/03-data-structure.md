# Rust 基础数据结构阶段

> 从所有权规则到在所有权约束下使用集合的实战第一关：struct/enum/Vec/HashMap 本身不难，难的是在所有权约束下正确使用它们。

## 1. 概述

Rust 基础数据结构阶段的定位是：**能用结构体和枚举表达业务实体、用 Vec/HashMap 组织集合数据、用 impl 封装行为，并在所有权约束下正确传递和遍历数据**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 三种结构体 | named field struct、tuple struct、unit struct |
| 枚举 | 带数据的变体、代数数据类型（ADT）基础 |
| impl 方法 | `self`、`&self`、`&mut self` 三种接收者 |
| Vec | 动态数组的创建、扩容、三种 for 遍历所有权语义 |
| HashMap / HashSet | entry API、分组统计、集合去重 |
| derive 宏 | Debug、Clone、PartialEq 一行省去 boilerplate |

**本阶段边界**：不展开 trait/泛型（Ph07）、生命周期标注（Ph08）和智能指针（Ph10）。枚举只讲基础定义，深度模式匹配在 **Ph05 模式匹配与枚举阶段**。

## 2. 来源与演变

Rust 数据结构融合两种传统：`struct` 来自 C/C++ 但加入所有权语义——字段的拥有者是结构体本身；`enum` 来自 ML/Haskell 的代数数据类型（ADT），每个变体可携带不同类型的数据。`Vec`/`HashMap` 对标其他语言的标准容器，但元素移入集合后所有权归集合。

| 概念 | C | C++ | Java | Go | Rust |
|------|---|-----|------|----|------|
| 复合数据 | `struct` | `struct`/`class` | `class` | `struct` | `struct`（所有权） |
| 标签联合 | `union`（不安全） | `std::variant` | `sealed class` | 接口+断言 | `enum`（ADT+穷尽） |
| 动态数组 | 手动管理 | `std::vector` | `ArrayList` | slice | `Vec`（owning） |
| 哈希表 | 无标准库 | `unordered_map` | `HashMap` | `map` | `HashMap`（SipHash） |

## 3. 语法与参数

### 3.1 三种结构体

Rust 有三种结构体形式，最常用的是**带名字段的 struct**：

```rust
#[derive(Debug, Clone)]
#[allow(dead_code)]
struct User {
    name: String,       // 持有 String（owned），无生命周期问题
    email: String,
    age: u8,
}

fn main() {
    let u1 = User {
        name: String::from("alice"),
        email: String::from("alice@example.com"),
        age: 30,
    };
    let u2 = User { name: String::from("bob"), ..u1.clone() };
    println!("{:?}", u2);
}
```

**tuple struct**：字段无名、按位置访问，适合包装语义清晰的简单类型（坐标、距离、温度）：

```rust
#[derive(Debug, PartialEq)]
struct Point(i32, i32);

#[derive(Debug)]
#[allow(dead_code)]
struct Millimeters(u64);

fn main() {
    let p = Point(3, 5);
    println!("x={} y={}", p.0, p.1);
    assert_eq!(p, Point(3, 5));

    let dist = Millimeters(1500);
    println!("distance: {:?}", dist);
}
```

**unit struct**：无字段，用作标记类型或 trait 实现的载体：

```rust
#[derive(Debug)]
struct Initialized;
#[allow(dead_code)]
struct Uninitialized;

fn main() {
    let state = Initialized;
    println!("state: {:?}", state);
}
```

### 3.2 struct 字段所有权

结构体字段持有 `String` 还是 `&str` 的根本区别：持有 `String`（owned）结构体拥有数据，没有生命周期问题；持有 `&str` 需要生命周期标注（Ph08）。

```rust
#[derive(Debug)]
#[allow(dead_code)]
struct OwnedUser {
    name: String,   // 推荐：owned 类型，无生命周期标注
}

fn main() {
    let name = String::from("alice");
    let user = OwnedUser { name }; // name 的 ownership 移入 user
    println!("{:?}", user);
}
```

基础阶段推荐持有 owned 类型（`String`、`Vec<T>`），掌握生命周期后再引入引用字段。

### 3.3 枚举基础

Rust 的枚举每个变体可以携带不同类型和数量的数据，这是 ADT 的核心表达能力。`Option<T>`/`Result<T, E>` 本质就是标准库用枚举定义的泛型类型。深度模式匹配见 Ph05。

```rust
#[derive(Debug)]
#[allow(dead_code)]
enum DeviceState {
    Online,
    Offline,
    Error { code: u32, msg: String },
}

fn main() {
    let s1 = DeviceState::Online;
    let s2 = DeviceState::Error { code: 404, msg: String::from("not found") };
    println!("{:?} {:?}", s1, s2);
}
```

### 3.4 impl 方法与三种 self

`impl` 块为结构体或枚举定义方法。接收者 `self` 的形式决定了所有权的转移方式：

```rust
#[derive(Debug)]
struct Counter {
    count: u32,
}

impl Counter {
    fn new() -> Self {
        Counter { count: 0 }
    }

    fn value(&self) -> u32 {     // &self：只读借用，最常见
        self.count
    }

    fn incr(&mut self) {         // &mut self：可变借用，修改内部状态
        self.count += 1;
    }

    fn into_inner(self) -> u32 { // self：拿走所有权，Counter 被消耗
        self.count
    }
}

fn main() {
    let mut c = Counter::new();
    c.incr();
    c.incr();
    println!("value={}", c.value()); // 2
    println!("final={}", c.into_inner()); // into_inner 消耗 c
}
```

`&self`（只读）最常见；`&mut self`（可变借用）用于修改内部状态；`self`（消耗）用于构建器收尾。

### 3.5 Vec 的创建、扩容与三种遍历

`Vec<T>` 是堆分配的动态数组，内部结构与 `String` 同源（ptr/len/cap 三元组，呼应 Ph02 4.1），`len == cap` 时扩容翻倍。遍历时三选一：

```rust
fn main() {
    let v = vec![10, 20, 30];

    for x in v {
        println!("owned: {}", x);
    }
}
```

```rust
fn main() {
    let v = vec![10, 20, 30];

    for x in &v {
        println!("borrowed: {}", x);
    }
    println!("still alive: {:?}", v); // v 仍可用
}
```

```rust
fn main() {
    let mut v = vec![10, 20, 30];

    for x in &mut v {
        *x += 1; // 解引用修改元素
    }
    println!("modified: {:?}", v); // [11, 21, 31]
}
```

| 写法 | 遍历后 v | x 类型 | 能修改元素 | 适合场景 |
|------|---------|--------|-----------|---------|
| `for x in v` | 消耗，不可用 | `T` | 否（拥有但只是读取） | 最后使用，交出所有权 |
| `for x in &v` | 仍可用 | `&T` | 否 | 只读统计、查找 |
| `for x in &mut v` | 仍可用 | `&mut T` | 是 | 原地修改、批量更新 |

### 3.6 HashMap 与 entry API

`HashMap<K, V>` 用于键值对存储，默认哈希函数 SipHash-1-3（防 HashDoS）。`HashSet<T>` 本质是 `HashMap<T, ()>`——只关心键不关心值。

**entry API** 是 Rust 哈希表最具特色的操作：一次哈希查找完成"存在则返回、不存在则插入"：

```rust
use std::collections::HashMap;

fn main() {
    let mut scores = HashMap::new();
    scores.insert(String::from("alice"), 90);

    // entry API：查一次哈希表完成判断+插入
    scores.entry(String::from("alice")).or_insert(100); // 已存在，不改
    scores.entry(String::from("bob")).or_insert(80);    // 不存在，插入 80

    // 更新已有值
    scores.entry(String::from("alice")).and_modify(|v| *v += 5);

    println!("{:?}", scores); // {"alice": 95, "bob": 80}
}
```

对比分两步写的版本——`contains_key` + `get`/`insert` 需要两次哈希查找且涉及所有权问题；entry API 一步完成，是最 Rustacean 的写法。

`HashSet` 用于去重：

```rust
use std::collections::HashSet;

fn main() {
    let mut seen = HashSet::new();
    seen.insert("apple");
    seen.insert("banana");
    seen.insert("apple"); // 重复插入无效果
    println!("unique: {:?}", seen); // {"apple", "banana"}
    println!("contains apple: {}", seen.contains("apple"));
}
```

### 3.7 derive 宏

`#[derive(...)]` 让编译器自动为类型生成 trait 实现，省去大量手工 boilerplate：

```rust
#[derive(Debug, Clone, PartialEq)]
struct Device {
    id: u32,
    name: String,
}

fn main() {
    let a = Device { id: 1, name: String::from("sensor") };
    let b = a.clone();                       // Clone：生成副本，a 仍可用
    println!("{:?} == {:?} -> {}", a, b, a == b); // Debug + PartialEq
}
```

| derive trait | 作用 |
|-------------|------|
| `Debug` | `{:?}` 格式化输出（几乎必须） |
| `Clone` | `.clone()` 深拷贝 |
| `PartialEq` | `==` 和 `!=` 比较 |
| `Eq` / `Hash` | HashMap key 必备 |

## 4. 底层原理

### 4.1 Vec 与 String：同源的 ptr/len/cap 三元组

`Vec<T>` 和 `String` 内存表示完全一致：栈上 `{ptr, len, capacity}` 三元组，堆上存数据。`len == cap` 时扩容为新容量的 2 倍，move 只复制栈上 24 字节（64 位）。这与 Ph02 4.1 呼应：`String` 本质是 `Vec<u8>` + UTF-8 保证。

### 4.2 HashMap 内部：SipHash + SwissTable

默认 **SipHash-1-3** 防 HashDoS；自 1.36 起采用 **SwissTable**，SIMD 探测一次检查 16 槽位。`HashSet<T>` 本质是 `HashMap<T, ()>`。

## 5. 使用场景

| 场景 | 推荐方式 | 原因 |
|------|---------|------|
| 表达有名字段的实体 | named field struct | 字段命名清晰 |
| 包装单值（坐标、距离） | tuple struct | 比裸类型安全 |
| 表达互斥状态 | enum | 穷尽检查 |
| 动态数量的同类记录 | `Vec<T>` | push/排序/过滤 |
| 按键查找、分组统计 | `HashMap<K, V>` | entry API 高效 |
| 去重 | `HashSet<T>` | HashMap 的键侧封装 |
| 查询/读属性 | `&self` | 最常见，不消耗结构体 |
| 修改内部状态 | `&mut self` | 调用后结构体仍可用 |

**不适合**此阶段：trait/泛型（Ph07）、生命周期标注（Ph08）、`Box/Rc/Arc/RefCell`（Ph10）、迭代器链式调用（Ph09）。

## 6. 代码示例

### 示例 1：三种结构体 + derive

```rust
#[derive(Debug, Clone, PartialEq)]
struct Order {
    id: u32,
    product: String,
    quantity: u32,
}

#[derive(Debug)]
struct Celsius(f64);

fn main() {
    let o1 = Order { id: 1, product: String::from("widget"), quantity: 5 };
    let o2 = o1.clone();
    assert_eq!(o1, o2);

    let temp = Celsius(36.8);
    println!("{:?} -> {:.1}C", temp, temp.0);
}
```

### 示例 2：impl 方法 + 构建器模式

```rust
#[derive(Debug)]
struct Config {
    host: String,
    port: u16,
    timeout_secs: u32,
}

impl Config {
    fn new() -> Self {
        Config {
            host: String::from("localhost"),
            port: 8080,
            timeout_secs: 30,
        }
    }

    fn host(mut self, host: impl Into<String>) -> Self {
        self.host = host.into();
        self
    }

    fn port(mut self, port: u16) -> Self {
        self.port = port;
        self
    }

    fn timeout(mut self, secs: u32) -> Self {
        self.timeout_secs = secs;
        self
    }
}

fn main() {
    let cfg = Config::new()
        .host("api.example.com")
        .port(443)
        .timeout(10);
    println!("{:?}", cfg);
}
```

### 示例 3：Vec 操作与排序过滤

```rust
#[derive(Debug)]
#[allow(dead_code)]
struct Record {
    name: String,
    score: u32,
}

fn main() {
    let mut records = vec![
        Record { name: String::from("alice"), score: 85 },
        Record { name: String::from("bob"), score: 92 },
        Record { name: String::from("carol"), score: 78 },
    ];

    // 可变借用遍历：所有记录 +10 分
    for r in &mut records {
        r.score += 10;
    }

    let pass: Vec<&Record> = records.iter().filter(|r| r.score >= 90).collect();
    println!("pass: {:?}", pass);

    records.sort_by(|a, b| b.score.cmp(&a.score));
    println!("sorted: {:?}", records);
}
```

### 示例 4：HashMap 分组统计

```rust
use std::collections::HashMap;

fn main() {
    let orders = vec![
        ("alice", 100),
        ("bob", 200),
        ("alice", 150),
        ("carol", 300),
        ("bob", 50),
    ];

    let mut total: HashMap<&str, u32> = HashMap::new();
    for (name, amount) in &orders {
        total.entry(name).and_modify(|v| *v += amount).or_insert(*amount);
    }
    println!("totals: {:?}", total);

    let mut count: HashMap<&str, u32> = HashMap::new();
    for (name, _) in &orders {
        *count.entry(name).or_insert(0) += 1;
    }
    println!("counts: {:?}", count);
}
```

### 示例 5：索引注册表（struct + Vec + HashMap 综合）

```rust
use std::collections::HashMap;

#[derive(Debug, Clone)]
#[allow(dead_code)]
struct Index {
    name: String,
    index_type: String, // "btree" | "hash" | "inverted"
    column_count: u32,
}

struct IndexRegistry {
    indexes: Vec<Index>,
    by_name: HashMap<String, usize>, // name -> Vec 索引
}

impl IndexRegistry {
    fn new() -> Self {
        IndexRegistry {
            indexes: Vec::new(),
            by_name: HashMap::new(),
        }
    }

    fn register(&mut self, index: Index) {
        let pos = self.indexes.len();
        self.by_name.insert(index.name.clone(), pos);
        self.indexes.push(index);
    }

    fn get_by_name(&self, name: &str) -> Option<&Index> {
        self.by_name.get(name).map(|&pos| &self.indexes[pos])
    }

    fn count_by_type(&self) -> HashMap<&str, u32> {
        let mut result = HashMap::new();
        for idx in &self.indexes {
            *result.entry(idx.index_type.as_str()).or_insert(0) += 1;
        }
        result
    }
}

fn main() {
    let mut reg = IndexRegistry::new();
    reg.register(Index { name: String::from("pk_users"), index_type: String::from("btree"), column_count: 1 });
    reg.register(Index { name: String::from("idx_email"), index_type: String::from("hash"), column_count: 1 });
    reg.register(Index { name: String::from("idx_name_age"), index_type: String::from("btree"), column_count: 2 });

    match reg.get_by_name("idx_email") {
        Some(idx) => println!("found: {:?}", idx),
        None => println!("not found"),
    }
    println!("by type: {:?}", reg.count_by_type());
}
```

## 7. 总结

### 关键要点

1. **三种结构体各有用处**：named field 表达实体，tuple struct 包装单值，unit struct 作编译期标记。
2. **字段优先持有 owned 类型**：`String` 而非 `&str`，避免生命周期标注。
3. **三种 self 对应三种所有权**：`&self`（最常见）、`&mut self`（修改）、`self`（消耗）。
4. **Vec 遍历三选一**：`for x in v`（消耗）、`for x in &v`（只读借用）、`for x in &mut v`（可变借用）。
5. **entry API 是最 Rustacean 的写法**：一次哈希查找代替 contains_key + insert 两步走。
6. **derive 宏省 boilerplate**：`#[derive(Debug, Clone, PartialEq)]` 一行获得打印、拷贝、比较能力。
7. **HashSet 就是 `HashMap<T, ()>`**：理解这一点就理解了 HashSet 的所有行为。

### Rust 结构体/枚举/集合与其他语言对照

| 概念 | Rust | C | C++ | Go | Java |
|------|------|---|-----|----|------|
| 复合数据 | `struct`（所有权） | `struct`（纯数据） | `struct`/`class` | `struct`（值） | `class`（引用） |
| 标签联合 | `enum`（ADT+穷尽） | `union`（不安全） | `std::variant` | 接口+类型断言 | `sealed class` |
| 动态数组 | `Vec<T>` | 手动管理 | `std::vector` | slice（非 owning） | `ArrayList` |
| 哈希表 | `HashMap`（SipHash） | 无标准 | `unordered_map` | `map`（内置） | `HashMap` |
| 方法 | `impl` + `&self` | 函数指针 | 成员函数 | receiver 函数 | 实例方法 |

### 阶段验收标准

- 能定义 struct（named field、tuple、unit）并用 `impl` 封装方法。
- 能解释 `&self`、`&mut self`、`self` 的所有权区别。
- 能根据场景选择 `for x in v`、`for x in &v` 或 `for x in &mut v`。
- 能用 `HashMap` entry API 做分组统计，而不是 contains_key + insert 两步走。
- 能看到 `#[derive(Debug, Clone, PartialEq)]` 并理解每项的作用。
- 能区分 struct 字段应持有 `String` 还是 `&str`。

### 进入下一阶段前

完成以下练习：
- 定义 `User`、`Device`、`Order` 三个结构体并添加 derive 宏。
- 用 `Vec` 保存 `Order` 记录，实现按金额排序和按状态过滤。
- 用 `HashMap` + entry API 对 `Order` 记录按产品名称分组统计总金额。
- 故意写出会触发 E0382（move 后使用）的 Vec 遍历代码，然后修复。
- 把示例 5 的 `IndexRegistry` 扩展为支持按类型列出所有索引名称。

### 推荐项目

- **索引注册表**：支持新增索引（名称、类型、列数），按名称查询，按类型统计数量。示例 5 已给出核心实现，可扩展删除和排序。
- **数据源注册表**：支持注册数据源（名称、类型如 MySQL/Kafka/Redis、连接地址），按名称查询，按类型分组列出数据源名称。

### 下一阶段

[Option 和 Result 阶段](../Ph04-option-result/04-option-result.md)—— 用枚举表达"可能有值/可能错误"的类型安全替代方案，掌握 `unwrap`/`?`/`map`/`and_then` 的适用边界。
