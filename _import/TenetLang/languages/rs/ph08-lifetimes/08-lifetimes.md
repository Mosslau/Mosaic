# Rust 生命周期 Lifetime 阶段

> 面向数据基础设施、异步网络服务方向：引用不能"活过"它指向的值——本阶段理解引用有效期，能处理函数、结构体和泛型中的生命周期约束。

## 1. 概述

Rust 生命周期阶段的定位是：**能说明生命周期（lifetime）描述的是"引用与值的有效期关系"而不是引用的属性，掌握生命周期省略规则与显式生命周期参数 `<'a>`，让函数、结构体和泛型正确表达"返回的引用绑定到哪个输入"，并修复 borrowed value does not live long enough（E0597）与 missing lifetime specifier（E0106）等借用检查错误**。本阶段是所有权阶段（ph02）的延续：所有权解决"值归谁管"，生命周期解决"借用能持续多久"。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 生命周期省略规则 | 三条 elision rules：输入引用各自独立、单输入赋所有输出、`&self` 特殊规则 |
| 显式生命周期参数 | `<'a>` 标注、多参数 `<'a, 'b>`、输出生命周期与输入生命周期绑定 |
| 结构体持有引用 | `struct S<'a> { field: &'a T }`、`impl<'a>` 块、生命周期随字段传播 |
| 'static 生命周期 | 字符串字面量 `&'static str`、`T: 'static` 约束、拥有类型天然满足 |
| 生命周期与泛型组合 | `<'a, T>` 同处签名、where 子句中的 `'a: 'b` 约束 |
| 子类型与协变初步 | 长生命周期引用可收缩为短生命周期引用（协变） |
| 常见错误修复 | E0597（borrowed value does not live long enough）、E0106（missing lifetime specifier） |

这个阶段只涉及生命周期标注语法、三条省略规则、结构体生命周期、`'static` 与借用检查的关系，**不涉及集合与迭代器的函数式写法、智能指针与内部可变性（`Rc`/`RefCell` 让共享可变成为可能）和异步生命周期（借用跨 `.await` 的限制）** — 那些是 ph09/ph10/ph12 阶段的内容。承接 ph07 trait 与泛型阶段：本阶段大量示例是"生命周期参数 + 泛型 + trait bound"的混合签名。

## 2. 来源与演变

生命周期标注直接继承**区域推断（region inference）**的思想：在区域（region）内存管理研究中，指针类型携带一个"区域"参数，编译器通过约束求解证明指针不会逃逸出区域。Rust 早期（1.0 之前）的引用类型 `&'a T` 就带着这样的生命周期参数，借用检查器（borrow checker）把整个程序的使用方式转成一组区域约束并求解——**你写的 `<'a>` 本质上是在给约束起名字**。

最早的 Rust 要求几乎所有带引用的函数都显式写生命周期，代码非常啰嗦。2014 年的 RFC 141 引入**生命周期省略规则（lifetime elision）**：常见模式（参数借用、返回借用）免写标注，只有编译器无法推断输出归属时才必须显式写出。2018 年的 Rust 1.31 随 edition 2018 稳定了 **NLL（Non-Lexical Lifetimes，非词法生命周期）**：引用的有效范围从"定义所在词法块的末尾"缩短到"最后一次使用"，大量原本被误报的合法代码通过编译。

`'static` 的语义也从"字符串字面量的类型"扩展为"类型不含非静态引用"的约束（`T: 'static`），成为线程、全局状态、长期缓存场景的常见 bound。

| 时间 | 里程碑 | 影响 |
|------|--------|------|
| 2010 前后 | 借鉴区域推断：引用携带生命周期参数 | `&'a T` 语法与借用检查器的约束求解模型成型 |
| 2014 | RFC 141：生命周期省略规则 | 常见签名免写 `'a`，可读性大幅提升 |
| 2015 | Rust 1.0 稳定 | 生命周期系统随语言定型，`'static` 语义确立 |
| 2018 | Rust 1.31：NLL 稳定 | 引用活到最后一次使用，误报大幅减少 |
| 2018+ | `T: 'static` 约束普及 | 线程、异步任务对 'static 数据的要求成为日常 |

本文示例以 **Rust 1.92 / edition 2021** 为基线（当前 stable 工具链，NLL 与三条省略规则自 1.31 起稳定多年，是选择它的理由），验证工具链 rustc 1.92.0（macOS arm64）。生命周期语法是 Rust 自 1.0 以来最稳定的部分之一，本文示例在可预见的版本内都能原样编译。

## 3. 语法与参数

### 3.1 引用的生命周期与借用检查回顾

ph02 说过"借用不拥有资源"。更精确地说：**每个引用都有一个生命周期（lifetime）——它有效的这段时间**，而借用检查器保证"引用的生命周期不能超过它指向的值的生命周期"。值先死、引用还活着，就是悬垂引用（dangling reference），被编译期禁止：

```rust
fn main() {
    let text = String::from("hello");
    {
        let view: &str = &text;   // view 的生命周期 ⊆ text 的生命周期
        println!("{}", view);
    }                             // view 在这里结束，text 依然存活
    println!("{}", text);
}
```

要点与坑：
- **生命周期描述的是引用关系，不是引用的属性**：同一个 `&text` 可以拥有不同的生命周期，取决于它被使用到什么时候。
- **标注不会延长引用的寿命**：`<'a>` 只声明约束，编译器不会为了让代码通过而让值多活一会儿——值在作用域结束时照样 drop。
- 大多数时候你不需要写生命周期：编译器能推断（省略规则见 3.2），只有推断不出时才需要显式标注。

### 3.2 生命周期省略规则（三条 elision rules）

**省略规则（lifetime elision）**：编译器在没有显式标注时自动补齐生命周期参数的规则，共三条：

1. 每个输入引用参数（包括 `&self`）**各自获得一个独立**的生命周期参数；
2. 如果**只有一个输入生命周期**，它会被赋给**所有输出**生命周期；
3. 如果有**多个输入生命周期**，但其中一个是 `&self` 或 `&mut self`，则 `self` 的生命周期赋给所有输出生命周期。

```rust
// 省略写法（第 2 条规则）：
fn first_word(s: &str) -> &str {
    s.split_whitespace().next().unwrap_or("")
}
// 编译器自动展开为：
// fn first_word<'a>(s: &'a str) -> &'a str { ... }

fn main() {
    let text = String::from("rust lifetimes are explicit");
    println!("{}", first_word(&text)); // rust
}
```

要点与坑：
- **坑：两个输入 + 一个输出**——第 2 条规则失效（有两个输入生命周期，不知道该把哪个给输出），编译器报 E0106，必须手动标注（见 3.8）。
- 第 3 条规则让方法签名几乎不用写生命周期：`fn get(&self) -> &str` 的返回引用自动绑定 `self`。
- 省略规则只是"省字"，语义与显式标注完全一致；省略规则的展开细节见 4.2。

### 3.3 显式生命周期参数（<'a> 与多参数）

当省略规则失效，或需要表达"返回引用绑定到哪个输入"时，用**显式生命周期参数**：

```rust
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() >= y.len() { x } else { y }
}

// 多参数：输出绑定到 'a（msg），'b 只用于打印标签
fn announce<'a, 'b>(msg: &'a str, tag: &'b str) -> &'a str {
    println!("[{}]", tag);
    msg
}

fn main() {
    let s1 = String::from("rust");
    let s2 = String::from("go");
    println!("{}", longest(&s1, &s2));       // rust
    let note = String::from("note");
    println!("{}", announce(&s1, &note));    // rust
}
```

要点与坑：
- `longest<'a>` 读作："存在一个生命周期 `'a`，`x`、`y` 的引用和返回值都活不过它"——返回值与两个输入**共享同一个** `'a`，编译器取三者中最短的那个。
- **坑：过度标注**——不需要的地方写 `<'a>` 不会报错，但会让签名难读；规则是"省略规则够用就别写"，写出来的每个 `'a` 都应该有约束作用。
- 生命周期参数与泛型参数语法上并列：`<'a, T>`，`'a` 习惯写在前面。
- 返回引用永远不能来自函数内部新建的局部值（无输入生命周期时原样报 E0106，补上 `<'a>` 后报 E0515；借用逃出作用域才报 E0597），只能来自输入或 `'static` 数据——这是"**输入引用与输出引用的约束**"的本质。

### 3.4 结构体持有引用（&'a str 字段）

结构体字段存引用时，生命周期参数必须**显式声明**（省略规则不适用于结构体定义）：

```rust
struct Highlight<'a> {
    text: &'a str,
    start: usize,
    end: usize,
}

impl<'a> Highlight<'a> {
    fn new(text: &'a str, start: usize, end: usize) -> Self {
        Highlight { text, start, end }
    }
    fn as_str(&self) -> &str {
        &self.text[self.start..self.end]
    }
}

fn main() {
    let line = String::from("the quick brown fox");
    let hl = Highlight::new(&line, 4, 9);
    println!("{}", hl.as_str()); // quick
}
```

要点与坑：
- `struct Highlight<'a>` 表示"这个类型的实例引用了某个外部数据，其引用不能超过 `'a`"；**结构体定义引用字段而不写 `<'a>` 直接报 E0106**。
- **坑：生命周期传播**——`Highlight<'a>` 出现在哪里，`<'a>` 就要跟到哪里：impl 块写 `impl<'a> Highlight<'a>`，作为字段/参数时写 `Highlight<'a>`。改起来比拥有字段麻烦，这是"拥有数据可简化生命周期"的现实理由（见 6.4）。
- 方法的省略规则在此依然生效：`fn as_str(&self) -> &str` 自动绑定 `self` 的生命周期，不需要写 `<'a>`。

### 3.5 'static 生命周期（字符串字面量与 'static 约束）

`'static` 是最长的生命周期："**活到程序结束**"。它出现在两个位置，语义不同：

```rust
fn main() {
    // 1) 引用类型：&'static str —— 数据存于二进制只读段，永不释放
    let name: &'static str = "kv-store";
    println!("{}", name);

    // 2) 约束：T: 'static —— T 中不能含"非静态"引用；拥有类型天然满足
    let owned: String = String::from("data");
    println!("{}", owned);
}
```

```rust
// 'static 约束的写法：只有"不借用非静态数据"的类型才能通过
fn assert_static<T: 'static>(value: T) -> T { value }

fn main() {
    let owned: String = assert_static(String::from("data")); // 拥有类型 ✓
    println!("{}", owned);
    let lit: &'static str = assert_static("literal");        // 'static 引用 ✓
    println!("{}", lit);
    // let s = String::from("tmp");
    // let r = assert_static(&s);  // E0597：argument requires that s is borrowed for 'static，被拒绝
}
```

要点与坑：
- 字符串字面量的类型就是 `&'static str`：它们编译进可执行文件的数据段，进程存活期间一直有效。
- **坑：'static 滥用**——`let s: &'static str = &local_string;` 无法编译，因为 local_string 会先被 drop；不要为了"省事"把局部数据泄漏成 'static（见 4.4）。
- 区分两种写法：`&'static str`（一个引用类型）与 `T: 'static`（一个对类型的约束）。拥有类型（`String`、`Vec<T>`、`i32`）都满足 `T: 'static`，因为它们不借用任何数据。

### 3.6 生命周期与泛型组合（<'a, T> 与 where 子句）

生命周期参数和泛型参数可以（也经常）同时出现。组合时用 **where 子句**整理：trait bound 与生命周期约束都放进去，签名保持可读：

```rust
use std::fmt::Display;

// <'a, T>：生命周期参数 + 泛型参数；T: Display 与 'a 同时约束
fn longest_with_tag<'a, T>(x: &'a str, y: &'a str, tag: T) -> &'a str
where
    T: Display,
{
    println!("tag: {tag}");
    if x.len() >= y.len() { x } else { y }
}

// 生命周期约束也可以进 where：'a: 'b 表示 "'a 不短于 'b"
fn keep_first<'a, 'b>(x: &'a str, _y: &'b str) -> &'a str
where
    'a: 'b,
{
    x
}

fn main() {
    let a = String::from("rust");
    let b = String::from("go");
    println!("{}", longest_with_tag(&a, &b, "compare"));
    println!("{}", keep_first(&a, &b));
}
```

要点与坑：
- **`'a: 'b` 读作 "'a outlives 'b"**：`'a` 至少和 `'b` 一样长。含义与 `T: Display` 类似——前者约束两个生命周期的大小关系，后者约束类型的 trait 能力，二者可以写在同一个 where 块里。
- **坑：'a: 'b 写反**——想让 `'a` 收缩成 `'b` 返回，必须 `'a: 'b`；写成 `'b: 'a` 语义相反，编译器会要求证明一个不成立的关系而报错。
- 结构体同样支持 `struct S<'a, T> where T: Display { ... }`，impl 块写 `impl<'a, T> S<'a, T> where T: Display { ... }`。

### 3.7 子类型与协变初步

生命周期之间有一个隐藏的**子类型关系（subtyping）**：**更长的生命周期是更短生命周期的子类型**——`&'long T` 可以在任何需要 `&'short T` 的地方使用（编译器自动收缩，称为**协变 covariance**）。这正是大量"长生命周期引用传给短生命周期参数"的代码能通过编译的原因：

```rust
fn takes_short(s: &str) -> usize { s.len() }

fn main() {
    let long_lived = String::from("hello");
    {
        // 长生命周期引用自动收缩为短生命周期引用（协变）
        let short: &str = &long_lived;
        println!("{}", takes_short(short));
    }
    // 'static 是最长的生命周期，所以 &'static str 可以传给任何 &str 参数
    let lit: &'static str = "world";
    println!("{}", takes_short(lit));
    println!("{}", long_lived);
}
```

要点与坑：
- 收缩方向是"长 → 短"：`&'static str` 能当 `&'a str` 用；反过来不行。
- **坑：可变引用对 T 是不变的（invariant）**——`&'a mut T` 在 T 上不允许收缩/放宽，这是 `RefCell`（ph10）存在的原因之一；本阶段只需记住"生命周期上的协变方向"。
- 子类型关系是隐式的：你几乎不会写转换，编译器自动处理；理解它有助于读懂"为什么这个调用能过、那个不能过"。

### 3.8 常见生命周期错误修复（E0597 / E0106）

**E0106：missing lifetime specifier**。两种高频触发：结构体引用字段没写 `<'a>`；多个输入引用 + 输出引用，省略规则无法决定输出归属：

```rust
// 错误 1：结构体引用字段 —— 必须显式声明 'a
// struct Wrapper { inner: &str }  // error[E0106]: missing lifetime specifier
struct Wrapper<'a> {
    inner: &'a str,
}
impl<'a> Wrapper<'a> {
    fn inner(&self) -> &str { self.inner }
}

// 错误 2：两个输入 + 一个输出，省略规则失效
// fn pick(x: &str, y: &str) -> &str { ... }  // error[E0106]
fn pick<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}

fn main() {
    let a = String::from("longer");
    let b = String::from("s");
    let w = Wrapper { inner: &a };
    println!("{} / {}", w.inner(), pick(&a, &b)); // longer / longer
}
```

**E0597：borrowed value does not live long enough** 对应"借用逃出作用域"场景（值先 drop、引用还在用，见示例 5 的真实报错）。返回局部值的引用是另一种情况：无输入生命周期时原样报 **E0106**，补上 `<'a>` 后报 **E0515**（cannot return reference to local variable）：

```rust
// 错误 3：返回局部值的引用 —— 原样报 error[E0106]（missing lifetime specifier，
//         无输入生命周期可绑定输出）；补上 <'a> 后报 error[E0515]（cannot return
//         reference to local variable）。借用逃出作用域才报 E0597，见示例 5
// fn bad_label() -> &str {
//     let label = String::from("cache-hot");
//     &label   // label 在函数返回时被 drop，引用悬空
// }
// 修复：返回拥有值 String
fn good_label() -> String {
    String::from("cache-hot")
}

fn main() {
    println!("{}", good_label());
}
```

要点与坑：
- **E0106 是"写少了"**：补上 `<'a>`，把引用字段/返回引用与生命周期参数关联起来即可。
- **E0515 / E0597 是"设计错了"**：返回引用只能来自输入参数或 `'static` 数据；数据是函数内部新建的，就返回拥有值（E0515）。借用逃出作用域（E0597）则调整作用域或返回拥有值。定位与修复套路见示例 5。
- 这几类错误（E0106 / E0515 / E0597）是生命周期阶段最常见的编译错误，务必练到"看到报错能说出修复方向"。

## 4. 底层原理

### 4.1 生命周期只是编译期概念（零运行时开销）

生命周期标注**在编译后不存在于机器码中**：借用检查通过后，编译器直接擦除所有生命周期信息。没有引用计数、没有运行时检查、没有额外的字段——这是"**零成本抽象**"的又一次体现。对比 GC（运行时跟踪对象存活）与 `Rc`（运行时增减计数），生命周期是纯静态证明：

```rust
// 编译产物里根本没有 'a 的存在：下面两个函数生成的机器码完全相同
fn f<'a>(s: &'a str) -> usize { s.len() }
fn g(s: &str) -> usize { s.len() }

fn main() {
    println!("{} {}", f("a"), g("b"));
}
```

（`'static` 字符串字面量确实占用二进制数据段并存活整个进程，但那是数据布局，不是检查开销。）

### 4.2 省略规则的展开（输入/输出生命周期）

省略规则实际上是把签名"翻译"成显式版本，翻译按 3.2 的三条规则顺序执行：

| 省略写法 | 展开后 |
|---------|--------|
| `fn f(s: &str) -> &str` | `fn f<'a>(s: &'a str) -> &'a str` |
| `fn f(s: &str, t: &str)` | `fn f<'a, 'b>(s: &'a str, t: &'b str)` |
| `fn f(&self) -> &str` | `fn f<'a>(&'a self) -> &'a str` |
| `fn f(s: &str, t: &str) -> &str` | 无法展开（E0106，需手动指定） |

规则要点：**输入生命周期**（参数里出现的 `'a`）由调用点决定；**输出生命周期**（返回类型里的 `'a`）要么由规则 2/3 从输入推导，要么手动标注。省略规则只影响"要不要写"，不影响语义。这也是"输入引用与输出引用的约束"的含义：**返回值能活多久，由它绑定的输入决定**。

### 4.3 借用检查器如何推断（NLL 与活跃借用分析）

借用检查器（borrow checker）把程序转成**生命周期约束（region constraints）**，然后做**区域推断（region inference）**求解：例如 `let r = &s;` 产生约束"s 的寿命 ≥ r 的寿命"，`println!("{}", r)` 则要求"r 活到这一行"。

NLL（Non-Lexical Lifetimes）让推断是**数据流敏感**的：编译器像活跃变量分析（liveness analysis）一样，计算每个借用"从创建到最后一次使用"的活跃区间（live range），只有活跃区间内出现冲突访问（比如可变借用或所有权移动）才报错。因此：

```rust
fn main() {
    let mut v = vec![1, 2, 3];
    let first = &v[0];
    println!("{}", first); // first 的最后一次使用
    v.push(4);             // first 已不活跃，允许可变借用
    println!("{:?}", v);
}
```

要点与坑：
- 大多数情况下你**不需要**写生命周期，因为推断自动完成；显式标注只在"推断不出输出归属"（E0106）或"结构体字段需要声明"时出现。
- **坑：NLL 不是万能的**——借用跨函数边界时（返回值、结构体字段），编译器无法在函数内部推断，必须依赖签名里的标注；这正是本阶段要掌握显式标注的原因。
- 借用检查是**全程序性**的：一个借用错误可能由很远处的调用点引起，报错信息通常会给出借用创建点、使用点、冲突点三个位置。

### 4.4 'static 与内存中的静态数据/泄漏

`'static` 引用指向**静态数据**：字符串字面量被编译进可执行文件的只读数据段（rodata），进程启动时加载、进程结束时才消失，地址在程序运行期间一直有效——所以 `&'static str` 可以安全地活到程序结束。这些数据**永远不会被释放**，但这种"故意泄漏"是安全的：只读、无所有权、无析构需求。

`T: 'static` 约束的语义不同：它要求**类型 T 不包含任何"非静态"的引用**。拥有类型（`String`、`Vec<T>`、`i32`、全拥有字段的结构体）天然满足；`&'a str`（`'a` 非 static）不满足。因此它常出现在"数据要跨越线程/异步任务边界"的场景（ph12）。

| 概念 | 含义 | 典型例子 |
|------|------|---------|
| `&'static str` | 一个活到程序结束的字符串引用 | 字符串字面量 |
| `T: 'static` | T 不借用非静态数据（对类型的约束） | 拥有类型 String、Vec<i32> |
| `Box::leak` | 故意让堆数据活到程序结束，返回 `&'static mut` | 需要程序级生命周期的极端手段 |

要点与坑：
- **坑：'static 滥用 = 内存泄漏**——`Box::leak`、`mem::forget` 都合法，但会让内存永不释放；除非真的需要"程序级生命周期"（如静态配置、全局注册表），否则优先拥有值或普通借用。
- Rust 允许泄漏（泄漏不是 unsafe），但泄漏会使资源（文件句柄、连接）无法回收，服务器场景要格外小心。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 函数返回输入字符串的子串（first_word、最长单词） | 省略规则 + 显式 `<'a>` |
| 结构体保存对输入数据的只读视图（配置视图、解析结果） | 结构体生命周期参数 `<'a>` |
| 多个输入引用、返回其中一个的引用 | 多生命周期参数、输出绑定 |
| 生命周期与泛型、trait bound 同时出现 | `<'a, T>` + where 子句 |
| 判断数据能否放入线程/异步任务/全局缓存 | `T: 'static` 约束 |
| 修复 borrowed value does not live long enough | E0597 定位 + 返回拥有值 |
| 长生命周期数据传给短生命周期参数的函数 | 协变（子类型）自动收缩 |
| 需要长期保存的引用数据（不想承担生命周期传播） | 拥有字段 String 替代 &'a str |

**不适合**此阶段的事项：
- 复杂自引用结构（结构体字段引用自身内部的数据，需要 `Pin` 等高级机制，后续阶段）。
- 异步作用域跨 `await` 的引用（借用跨越 `.await` 点会被拒绝，ph12 异步阶段）。
- `Rc`/`RefCell` 内部可变性（共享可变状态属于 ph10 智能指针）。
- 集合与迭代器的函数式写法（map/filter/fold 链式组合，ph09）。

## 6. 代码示例

本节展示完整可运行示例的关键片段，完整文件在 [`examples/`](./examples/) 目录，全部为零第三方依赖的单文件，可用 `rustc --edition 2021` 直接编译运行（已验证：rustc 1.92.0）。

### 示例 1：返回引用的函数加生命周期（longest）

roadmap 练习"为返回引用的函数添加生命周期"的标准题：两个输入引用、返回较长者的引用。省略规则无法处理"两个输入 + 一个输出"，必须显式标注：

```rust
// examples/ex01-longest.rs —— 返回引用的函数加生命周期（已验证：rustc 1.92.0，rustc --edition 2021 单文件编译）
// 返回较长字符串的引用：输出绑定到输入 'a
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() >= y.len() { x } else { y }
}

fn main() {
    let s1 = String::from("rust");
    let s2 = String::from("go");
    let result = longest(&s1, &s2);
    println!("longer: {}", result); // longer: rust

    // 返回值绑定两个输入中较短的生命周期：tmp 先被 drop 就不能再用 result
    let r;
    {
        let tmp = String::from("temporary");
        r = longest(&s1, &tmp);
        println!("inside: {}", r); // 仍在 tmp 存活期内，合法
    }
    // println!("{}", r); // 若取消注释：E0597，r 借用了 tmp，而 tmp 已 drop
}
```

要点与坑：
- 去掉 `<'a>` 直接写 `fn longest(x: &str, y: &str) -> &str` 会报 E0106——省略规则只能处理"一个输入"的情况。
- `'a` 取两个输入生命周期中**较短**的那个：这是最保守的选择，保证返回值无论如何都安全。
- 返回引用只能来自输入：函数内新建的 `String` 不能作为返回引用（见示例 5）。

### 示例 2：结构体持有引用（只读配置视图 ConfigView<'a>）

roadmap 推荐项目"**只读配置视图**"的核心：解析配置文本，但**不复制内容**，只保存指向原文的切片（借用字段），并提供查询接口：

```rust
// examples/ex02-config-view.rs —— 结构体持有引用：只读配置视图（已验证：rustc 1.92.0）
// 从配置文本中借用字段的只读视图：零拷贝，生命周期绑定原文
struct ConfigView<'a> {
    host: &'a str,
    port: &'a str,
    retries: &'a str,
}

impl<'a> ConfigView<'a> {
    fn from_text(text: &'a str) -> ConfigView<'a> {
        let mut host: &'a str = "localhost";
        let mut port: &'a str = "8080";
        let mut retries: &'a str = "3";
        for line in text.lines() {
            if let Some((key, value)) = line.split_once('=') {
                match key.trim() {
                    "host" => host = value.trim(),
                    "port" => port = value.trim(),
                    "retries" => retries = value.trim(),
                    _ => {}
                }
            }
        }
        ConfigView { host, port, retries }
    }

    fn host(&self) -> &str { self.host }
    fn port(&self) -> &str { self.port }
    fn retries(&self) -> usize { self.retries.parse().unwrap_or(3) }
}

fn main() {
    let config_text = String::from("host=db-01.internal\nport=5432\nretries=5\n");
    let view = ConfigView::from_text(&config_text); // 借用 config_text，未复制任何字段
    println!("host={} port={}", view.host(), view.port());
    println!("retries as number: {}", view.retries());
    // view 的生命周期与 config_text 绑定：config_text 存活期间 view 才有效
}
```

要点与坑：
- `from_text(text: &'a str) -> ConfigView<'a>`：输入借用与结构体绑定同一个 `'a`，返回的视图与原文同生共死。
- **坑：生命周期传播**——`ConfigView<'a>` 一旦作为字段或参数，`<'a>` 会出现在所有使用处；如果只想长期持有，考虑拥有字段版本（示例 4）权衡。
- 零拷贝是这类"视图"的价值：配置文本只读一次，查询接口零成本返回切片。

### 示例 3：生命周期 + 泛型组合（where 'a: 'b 约束）

roadmap 练习"整理含泛型和生命周期的 where 子句"：把 `'a: 'b` 生命周期约束与 `T: Display` trait bound 写进同一个 where 块：

```rust
// examples/ex03-where-lifetime.rs —— 生命周期 + 泛型的 where 子句（已验证：rustc 1.92.0）
use std::fmt::Display;

// 'a: 'b（'a 不短于 'b）+ T: Display：两类约束同处 where
fn choose_longer<'a, 'b, T>(x: &'a str, y: &'b str, tag: T) -> &'b str
where
    'a: 'b,
    T: Display,
{
    println!("tag: {tag}");
    if x.len() >= y.len() { x } else { y }
}

fn main() {
    let x = String::from("rust");   // 外层作用域：x 活得更久
    let result;
    {
        let y = String::from("go"); // 内层作用域：y 活得更短（'b）
        result = choose_longer(&x, &y, "compare");
        println!("inside: {}", result); // 此时 y 还活着，可以用
    }
    // println!("outside: {}", result); // 若取消注释：E0597
    // result 绑定的是较短的 'b（y 的生命周期），y 被 drop 后不可再使用
    println!("done");
}
```

要点与坑：
- 为什么需要 `'a: 'b`：`x` 是 `&'a str`，但返回值类型是 `&'b str`（更短）；只有证明 `'a` 不短于 `'b`，编译器才允许把 `x` 的引用收缩成 `&'b str` 返回。
- 结果的生命周期由**较短的输入**（`'b`，即 `y`）决定——返回引用"不能比它绑定的数据活得更久"。
- where 里生命周期约束与 trait bound 写法一致，只是约束对象从"类型"变成"生命周期"。

### 示例 4：把不必要的引用字段改成拥有字段（String 替代 &'a str 的取舍）

roadmap 练习"把不必要的引用字段改成拥有字段"：当数据会被长期持有、来源多变（来自构造、计算、外部输入）时，引用字段带来的生命周期传播是纯粹的负担——改用 `String` 拥有字段，结构体立即"自洽"：

```rust
// examples/ex04-owned-fields.rs —— 把不必要的引用字段改成拥有字段（已验证：rustc 1.92.0）
// 改造前：引用字段，生命周期传播到所有使用方
// struct Config<'a> { name: &'a str, version: &'a str }
// impl<'a> Config<'a> {
//     fn name(&self) -> &str { self.name }
// }

// 改造后：拥有字段，生命周期参数整体消失
#[derive(Debug)]
struct Config {
    name: String,
    version: String,
}

impl Config {
    fn new(name: &str, version: &str) -> Self {
        Config {
            name: name.to_string(),     // 拷贝一份，从此自给自足
            version: version.to_string(),
        }
    }
    fn name(&self) -> &str { &self.name }
    fn version(&self) -> &str { &self.version }
}

fn main() {
    let cfg = Config::new("cache", "3.2.1");
    println!("{:?}", cfg);                       // Debug
    println!("{} v{}", cfg.name(), cfg.version());
    // 拥有字段的结构体可以自由移动、进集合、跨线程，不再受借用约束
    let cfgs = vec![cfg];
    println!("count: {}", cfgs.len());
}
```

要点与坑：
- **取舍**：拥有字段（`String`）的代价是每次构造多一次堆分配与拷贝；换来的是结构体**不依赖外部数据的存活**，可以自由 move、存进 `Vec`、放进其他结构体。
- 判断标准：数据是"输入的只读视图"（用 `&'a str`，零拷贝）还是"需要长期/独立持有"（用 `String`）——roadmap 必会概念"**拥有数据可简化生命周期**"说的就是这个。
- 方法 `fn name(&self) -> &str` 依然可以返回 `&str`：方法内借用 `self`，不涉及结构体的生命周期参数。

### 示例 5：修复 borrowed value does not live long enough（E0597）

roadmap 阶段验收的核心技能。先复现：借用逃出了它所属的作用域。真实编译器输出（rustc 1.92，--edition 2021）：

```text
error[E0597]: `s` does not live long enough
 --> e0597.rs:5:13
  |
4 |         let s = String::from("hello");
  |             - binding `s` declared here
5 |         r = &s;
  |             ^^ borrowed value does not live long enough
6 |     }
  |     - `s` dropped here while still borrowed
7 |     println!("{}", r);
  |                    - borrow later used here
```

修复原则：**数据从哪来，决定返回什么**——

```rust
// examples/ex05-fix-e0597.rs —— 修复 E0597 的三种方向（已验证：rustc 1.92.0；错误版本已注释，仅作对照）
// 错误版本（无法编译）：借用逃出作用域 / 返回对局部值的引用
// fn main() {
//     let r;
//     {
//         let s = String::from("hello");
//         r = &s;                 // error[E0597]：s 被 drop 时 r 还在用
//     }
//     println!("{}", r);
// }
// fn render_label(id: u64) -> &str {
//     let label = format!("record-{id}");  // label 是函数内部的拥有值
//     &label                               // error[E0597]
// }

// 修复 1：数据是新建的 → 返回拥有值 String，所有权移出函数
fn render_label(id: u64) -> String {
    format!("record-{id}")
}

// 修复 2：内容恒定 → 返回 &'static str（编译进二进制，永不释放）
fn health_status() -> &'static str {
    "healthy"
}

// 修复 3：数据是传入的 → 返回输入切片（用省略规则即可）
fn trimmed(s: &str) -> &str {
    s.trim()
}

fn main() {
    println!("{}", render_label(42));  // record-42
    println!("{}", health_status());   // healthy
    println!("{}", trimmed("  ok  ")); // ok
}
```

要点与坑：
- 排查套路：报错指向的函数/作用域里，找到"引用指向的值"，问一句"这个值属于谁？"——属于函数内部（新建/局部）就返回拥有值；属于输入就返回输入切片；属于程序级数据就返回 `'static`。
- **坑：用 `.to_string()`/`clone()` 强行续命**——如果调用方本来就要长期持有，返回拥有值是正解；但不要用 `Box::leak` 之类的把局部值"钉死"成静态（见 4.4）。

## 7. 总结

### 关键要点

1. **生命周期描述引用关系，不延长引用本身**：标注只声明"引用能活多久"，编译器不会因此让值多活一秒。
2. **三条省略规则**：每个输入引用独立；单输入赋所有输出；`&self` 规则。无法省略时（多输入 + 输出引用）必须显式标注。
3. **显式 `<'a>` 表达"输出绑定到哪个输入"**：`longest<'a>(x: &'a str, y: &'a str) -> &'a str` 中 `'a` 取输入中较短的寿命。
4. **结构体持有引用必须声明生命周期**：`struct S<'a>`；`<'a>` 会传播到 impl 块、字段和所有使用处。
5. **'static 有两个含义**：`&'static str` 是"活到程序结束的引用"（字符串字面量），`T: 'static` 是"类型不借用非静态数据"的约束（拥有类型天然满足）。
6. **拥有数据可简化生命周期**：`String` 替代 `&'a str` 字段后生命周期参数整体消失，代价是堆分配与拷贝。
7. **生命周期是编译期概念**：检查通过后被擦除，零运行时开销。
8. **NLL**：引用活跃到**最后一次使用**，不是词法块末尾，让自然写法更容易通过编译。
9. **协变：长可收缩为短**：`&'static str` 可传给任意 `&str` 参数；方向不可逆。
10. **错误即诊断信号**：E0106 是"写少了"（补 `<'a>`），E0597 是"设计错了"（返回拥有值）。

### 跨语言对比：引用安全与所有权

| 维度 | Rust | C++ | Java | Go | C |
|------|------|-----|------|----|---|
| 引用有效期表达 | 生命周期参数 `'a`（编译期） | 无（靠作用域约定） | 无 | 无 | 无 |
| 悬垂引用防护 | 编译期拒绝（E0597） | 无（dangling 是常见 bug） | GC 保证 | GC 保证 | 无 |
| 修改与共享冲突 | xor 规则编译期检查 | 无 | 无（引用可共享） | 无（多数共享） | 无 |
| 借用检查运行时开销 | 零（编译后擦除） | 零 | GC 暂停 | GC 暂停 | 零 |
| 悬垂后行为 | 无法编译 | 未定义行为（UB） | 不可能 | 不可能 | 未定义行为 |
| 手动释放需求 | 无（Drop 自动） | 有（或 RAII） | 无（GC） | 无（GC） | 有（free） |

### 阶段验收清单

- [ ] 能说明生命周期参数表达的约束：`<'a>` 声明引用有效期，并把输出引用与某个输入引用绑定
- [ ] 能判断何时应返回拥有值：返回引用只允许来自输入或 `'static` 数据；数据是新建/局部的就返回拥有值
- [ ] 能修复 borrowed value does not live long enough（E0597），并说出三种修复方向（拥有值 / `'static` / 输入切片）
- [ ] 能补上省略规则无法处理的签名：两个输入 + 一个输出时显式标注 `<'a>`
- [ ] 能区分 `&'static str` 与 `T: 'static` 两种语义，并说明结构体引用字段带来的生命周期传播

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看），共 5 题，与本章示例 1~5 一一对应：

- 为返回引用的函数添加生命周期（提示：`fn longest(x: &str, y: &str) -> &str` 报 E0106，手动补 `<'a>`；对照示例 1）
- 写一个持有引用的结构体并实现方法（提示：`impl<'a> S<'a>`，方法参数与返回自动省略；对照示例 2）
- 整理含泛型和生命周期的 where 子句（提示：`<'a, T>` 顺序、`'a: 'b` 与 `T: Display` 同处 where；对照示例 3）
- 把不必要的引用字段改成拥有字段（提示：字段类型 `&'a str` → `String`，观察 `<'a>` 从结构体、impl 块、所有使用处消失；对照示例 4）
- 尝试制造并修复一个借用检查错误（提示：让借用逃出作用域报 E0597，或返回 `format!` 结果的引用——原样报 E0106、补 `<'a>` 后报 E0515——然后改为返回拥有值；对照示例 5）

完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**只读配置视图**——从配置文本中借用字段并提供查询接口（roadmap 推荐项目；示例 2 给出核心，project/ 扩展为支持 section 分组、通用 `get(key)`、行号定位的完整版本，含单元测试）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

扩展方向（可选）：**文本索引视图**——对日志文本建立"行号 → 行内容"的借用视图，提供 `line(n) -> Option<&str>` 查询接口，同样是"借用不复制"的套路。

### 下一阶段

[集合、迭代器与函数式写法阶段](../ph09-collections-iterators/09-collections-iterators.md) —— Vec/HashMap/BTreeMap 深入、迭代器链、collect/闭包组合、函数式风格。生命周期解决了"引用能活多久"，迭代器阶段则大量出现"返回引用 + 迭代器 + 闭包"的组合：`iter()` 的生命周期、`collect` 的拥有/借用选择、闭包捕获与 `move`，都需要本阶段的约束功底。
