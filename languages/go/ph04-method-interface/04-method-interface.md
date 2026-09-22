# Go 方法与接口阶段

> 面向接口编程是 Go 降低耦合、提高可测试性的核心理念，方法则是连接数据与行为的纽带。

## 1. 概述

Go 方法与接口阶段的目标是：**掌握方法定义、接收者抉择、隐式实现与类型断言**。ph03 完成了数据组织（slice/map/struct），本阶段在其 struct 嵌入之上回答行为绑定与抽象解耦——方法是让数据拥有行为，接口是让行为脱离具体类型。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 方法 | 值 vs 指针接收者、方法集规则、嵌入方法提升 |
| Interface | 接口定义、隐式实现、小接口设计、接口组合 |
| 类型断言 | `interface{}`/`any`、ok 模式、type switch |
| 陷阱 | nil 接口 vs 持有 nil 指针的接口、方法集可赋值性 |

Go 的 OOP 靠 **struct + method + interface** 三者组合，不靠类和继承。隐式实现是核心贡献：方法匹配即满足接口，使用方定义接口无需实现方感知——依赖反转自然、mock 零成本。

> 这个阶段只涉及方法、接口与类型断言，**不涉及 goroutine/channel、泛型和 go mod 依赖管理** — 那些是 ph06/ph05 及后续阶段的内容；错误处理已在 ph02 覆盖。

## 2. 来源与演变

Go 从 C、Java、Smalltalk 中提炼出一个更克制的 OOP 模型：

| 设计决策 | 传统方案 | Go 方案 | 设计意图 |
|----------|---------|--------|---------|
| 行为绑定 | 类方法（Java/C++） | 任意类型上定义方法 | 不必先声明类 |
| 接口实现 | `implements`（Java） | 隐式实现（方法匹配） | 解耦定义与实现 |
| 继承/复用 | 类继承（extends） | struct/interface 嵌入 | 组合优先于继承 |
| 顶层抽象 | `Object` / `void*` | `interface{}` / `any` | 最小化顶层类型 |

**方法即为带接收者的函数**：`func (c Counter) Inc()` 本质是把 `Counter` 作为第一个参数的函数。

**隐式实现**：Java 要求声明 `implements`，Go 只需方法匹配。使用方定义接口无需实现方感知——`io.Reader`（1 个方法）能成为全生态通用抽象正因如此。

**小接口传统**：`io.Reader`、`io.Writer`、`fmt.Stringer`、`error` 都只有 1 个方法。

本文示例以 **Go 1.22** 为基线（广泛使用的稳定版本，涵盖 `any` 别名与 `math/rand` 全局函数自动随机化），验证工具链 Go 1.22.2（darwin/arm64）。本阶段的方法、接口、类型断言是 Go 1.0 起就存在的最稳定语法，版本差异影响极小。

## 3. 语法与参数

### 3.1 方法定义与接收者选择

方法是对接收者类型定义的函数：

```go
package main
import "fmt"
type Counter struct {
    Count int
}
// 值接收者：操作副本
func (c Counter) ValueInc() {
    c.Count++
}
// 指针接收者：修改原值
func (c *Counter) PtrInc() {
    c.Count++
}
func main() {
    c := Counter{Count: 0}
    c.ValueInc()
    fmt.Println("ValueInc 后:", c.Count) // 0
    c.PtrInc()
    fmt.Println("PtrInc 后:  ", c.Count) // 1
}
```

值接收者 vs 指针接收者的选择规则：

| 场景 | 推荐 | 原因 |
|------|------|------|
| 需要修改接收者状态 | 指针 `*T` | 值接收者操作副本 |
| 接收者是大 struct | 指针 `*T` | 避免复制开销 |
| 小型不可变类型（如 `time.Time`） | 值 `T` | 安全、无副作用 |
| 包含 `sync.Mutex` | 指针 `*T` | Mutex 复制后状态未定义 |
| map / slice 等引用类型 | 值 `T` 通常可行 | 内部已是指针语义 |

同一类型的方法应使用一致的接收者类型。**方法集**：`T` 仅含值接收者方法；`*T` 含值 + 指针接收者全部方法。以指针接收者定义方法时，只有 `*T` 满足对应接口。

### 3.2 Interface 定义与隐式实现

```go
package main
import "fmt"
type Describer interface {
    Describe() string
}
type Vehicle struct {
    VIN   string
    Model string
}
func (v Vehicle) Describe() string {
    return fmt.Sprintf("Vehicle{VIN=%s Model=%s}", v.VIN, v.Model)
}
func printDesc(d Describer) {
    fmt.Println(d.Describe())
}
func main() {
    v := Vehicle{VIN: "LSVAA4184ES000001", Model: "Model S"}
    printDesc(v)
}
```

隐式实现的优势：使用方定义接口解耦依赖、第三方类型可后补满足新接口、只定义需要的方法。编译器在赋值时静态检查方法集——与 Python 运行时 duck typing 本质不同。

**什么时候该引入接口（三个信号）**——接口不是"面向对象"的装饰，是**有成本**的（动态分发、隐藏具体能力），按信号引入而不是按习惯引入：

| 信号 | 例子 | 动作 |
|------|------|------|
| 同一行为将有多个实现 | 数据采集：CAN / UART / MQTT 都要 `Read()` | 定义小接口 + 各自实现 |
| 需要替换或 mock | 存储层要能换内存版 / 文件版 / 测试替身 | 使用方依赖接口 |
| 跨包边界要解耦 | 库代码不该 import 使用方的具体类型 | 接口放使用方一侧 |

**什么时候别引入**：只有一个实现且没有替换/mock 需求（先写具体类型，接口等第二个实现出现再抽）；纯内部小结构体（接口只会增加间接）；高性能零分配路径（`iface` 是两指针 + 动态分发，热循环里能省则省）。

### 3.3 组合与嵌入的方法提升

ph03 的 struct 嵌入带来字段提升；方法同理——嵌入类型的字段和方法都自动提升：

```go
package main
import "fmt"
type Motor struct {
    Speed   int
    Enabled bool
}
func (m Motor) Status() string {
    if m.Enabled && m.Speed > 0 {
        return "运行中"
    }
    return "停止"
}
type Vehicle struct {
    VIN   string
    Motor // 匿名字段：Motor 的字段和方法都提升到 Vehicle
}
func main() {
    v := Vehicle{VIN: "LSV...", Motor: Motor{Speed: 80, Enabled: true}}
    fmt.Println(v.Status()) // 方法提升
    fmt.Println(v.Speed)    // 字段提升
}
```

接口同样支持组合嵌入：`type ReadWriter interface { Reader; Writer }`——任何同时实现 `Read` 和 `Write` 的类型自动满足 `ReadWriter`，比定义一个大接口更灵活。

### 3.4 空接口、类型断言与 type switch

`interface{}`（Go 1.18+ 可用 `any` 别名）是空接口——没有任何方法要求，所有类型都自动满足：

```go
package main
import "fmt"
func main() {
    var x interface{} = 42
    // ok 模式类型断言——安全，失败不 panic
    if s, ok := x.(int); ok {
        fmt.Println("int 断言成功:", s)
    }
    if _, ok := x.(string); !ok {
        fmt.Println("string 断言失败——不 panic")
    }
    describe(42)
    describe("hello")
    describe(3.14)
}
func describe(v interface{}) {
    switch val := v.(type) {
    case int:
        fmt.Printf("整数: %d\n", val)
    case string:
        fmt.Printf("字符串: %s\n", val)
    default:
        fmt.Printf("其他类型: %T\n", val)
    }
}
```

断言分两种：`v := x.(T)` 失败 panic；`v, ok := x.(T)` 失败 ok=false——后者是惯用写法。

## 4. 底层原理

### 4.1 方法的本质

方法编译后转为普通函数（接收者作为第一个参数）：`func (c Counter) Inc()` 编译为 `func Counter_Inc(c Counter)`。编译器在调用侧自动插入 `&` 或 `*`，但仅限可寻址（addressable）的值——字面量、返回值、map 索引值不可寻址，因此 `Counter{}.PtrInc()` 编译错误。

### 4.2 接口的运行时表示与 nil 陷阱

Go 接口在运行时由**两个指针**构成——空接口 `eface { _type; data }`，非空接口 `iface { tab(*itab); data }`，其中 `itab` 组合了接口类型、具体类型和方法函数指针数组。接口比较 `i1 == i2` 比较的是（类型信息 + 数据指针）对——这就是 nil 陷阱的根源：

```text
var s Sensor = nil
// _type=nil, data=nil → s==nil → true → 调用方法 panic

var t *TempSensor = nil; s = t
// tab._type 非 nil, data=nil → s==nil → false!
// 方法可调用，但 t 为 nil → 方法内访问 t 的字段 panic
```

**工程教训**：返回接口类型时永远 `return nil`，不要 `return (*ConcreteType)(nil)`——后者是持有 nil 指针的非 nil 接口，会让调用方的 nil 检查失效。

### 4.3 方法集的三个可赋值性推论

3.1 说"`*T` 方法集 ⊃ `T` 方法集"，落到"能不能赋给接口"上有三个推论——这是编译错误最常见的来源：

| 场景 | 代码 | 结果 |
|------|------|------|
| 值类型赋给只需要值方法的接口 | `var d Describer = Vehicle{}` | ✅ |
| 值类型赋给**需要指针方法**的接口 | `var w Writer = buf`（`buf` 是 `bytes.Buffer` 值） | ❌ 编译错误：`*Buffer` 才有 `Write` |
| 可寻址值自动取址 | `var w io.Writer = &buf` 或 `w = buf`（若 `buf` 是变量） | ✅ 编译器自动 `&buf` |
| 指针类型赋给接口 | `var w io.Writer = &buf` | ✅ 值方法 + 指针方法都在方法集内 |

```go
// 典型编译错误：bytes.Buffer 的 Write 是值接收者，但实现 io.Writer 的意图要用指针
// 错误: var w io.Writer = bytes.Buffer{}   // *Buffer 才有 Write（Buffer 的方法集不含指针方法）
var w io.Writer = &bytes.Buffer{}            // 正确:指针在 *T 的方法集里
```

一句话记忆：**接口需要的方法如果声明在指针接收者上，就必须传指针（或可寻址的变量）**；反过来值接收者的方法，值和指针都能满足。这条规则解释了为什么文件/缓冲这类"要改状态"的类型几乎都以 `*T` 满足接口。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 设备数据采集抽象层 | 接口定义、多实现（CAN / UART / MQTT） |
| 可替换存储后端 | 接口解耦、依赖注入、mock 测试 |
| 单元测试 mock | 接口隔离外部依赖、替换真实实现 |
| 日志/指标标准化 | 小接口（Logger / Metrics）、接口组合 |
| 中间件/插件系统 | 接口约定、类型断言、动态注册 |
| 协议适配器 | type switch、不同协议的接口统一 |

注意事项：不要为每个 struct 配 interface（只在需要解耦时引入）；接口由使用方定义；含 `sync.Mutex` 的类型必须用指针接收者；返回接口类型时避免返回持有 nil 指针的"非 nil 接口"。

**一条 Go 社区惯例值得提前建立**：**"accept interfaces, return structs"（接收接口、返回结构体）**——函数参数用最小的接口（只声明你需要的方法），返回值返回具体类型（调用方拿到具体类型才能继续链式使用、零断言负担）。它是 3.1 小接口哲学在函数签名上的落地：`func Save(w io.Writer, data []byte) error` 比 `func Save(f *os.File, data []byte) error` 可测试性强得多（能传入 `bytes.Buffer` 做测试），而 `func New() *TodoService` 比 `func New() Service` 更好用（需要 mock 时再抽接口也不迟）。

## 6. 代码示例

> 本节每个示例的完整可运行文件在 [`examples/`](./examples/) 目录，验证环境 Go 1.22.2（darwin/arm64），运行命令统一 `go run examples/ex0X-*.go`（单文件模式，命令见 examples/README.md）。

### 示例 1：值接收者与指针接收者对比

```go
package main
import "fmt"
type Counter struct {
    Count int
}
func (c Counter) ValueInc() {
    c.Count++ // 修改副本，不影响原值
}
func (c *Counter) PtrInc() {
    c.Count++ // 修改原值
}
func main() {
    c := Counter{Count: 0}
    c.ValueInc()
    fmt.Println("ValueInc 后:", c.Count) // 0
    c.PtrInc()
    fmt.Println("PtrInc 后:  ", c.Count) // 1
    Counter{Count: 10}.ValueInc() // 字面量可调用值接收者
    // Counter{Count: 10}.PtrInc() // 编译错误：字面量不可寻址
}
```

完整文件：`examples/ex01-receiver.go`

### 示例 2：Sensor 接口——CAN / UART 数据采集

```go
package main
import (
    "fmt"
    "math/rand"
)
type Sensor interface {
    Read() float64
    Name() string
}
// CAN 总线传感器——值接收者
type CANSensor struct {
    Channel string
}
func (c CANSensor) Read() float64 {
    return 25.0 + rand.Float64()*10.0
}
func (c CANSensor) Name() string {
    return "CAN-" + c.Channel
}
// UART 传感器——指针接收者（需修改校准偏移）
type UARTSensor struct {
    Port   string
    offset float64
}
func (u *UARTSensor) Read() float64 {
    return 3.3 + rand.Float64()*1.7 + u.offset
}
func (u *UARTSensor) Name() string {
    return "UART-" + u.Port
}
func (u *UARTSensor) Calibrate(offset float64) {
    u.offset = offset
}
func collect(sensors []Sensor) {
    for _, s := range sensors {
        fmt.Printf("[%s] 读数: %.2f\n", s.Name(), s.Read())
    }
}
func main() {
    can := CANSensor{Channel: "CAN0"}
    uart := &UARTSensor{Port: "/dev/ttyUSB0", offset: 0.5}
    fmt.Println("=== 第 1 轮采集 ===")
    collect([]Sensor{can, uart}) // can 值类型、uart 指针，都满足 Sensor
    uart.Calibrate(1.0)
    fmt.Println("\n=== 校准后采集 ===")
    collect([]Sensor{can, uart})
}
```

完整文件：`examples/ex02-sensor.go`

### 示例 3：Storage 接口——可替换存储层的 Todo 服务

```go
package main
import "fmt"
// Storage 由使用方定义
type Storage interface {
    Save(key, value string)
    Load(key string) (string, bool)
    Delete(key string)
}
type MemStorage struct {
    data map[string]string
}
func (m *MemStorage) Save(key, value string) {
    if m.data == nil {
        m.data = make(map[string]string)
    }
    m.data[key] = value
}
func (m *MemStorage) Load(key string) (string, bool) {
    v, ok := m.data[key]
    return v, ok
}
func (m *MemStorage) Delete(key string) {
    delete(m.data, key)
}
// TodoService 依赖接口而非具体实现
type TodoService struct {
    store Storage
}
func (t *TodoService) Add(id, task string) {
    t.store.Save(id, task)
    fmt.Printf("[添加] %s → %s\n", id, task)
}
func (t *TodoService) Done(id string) {
    t.store.Delete(id)
    fmt.Printf("[完成] %s 已删除\n", id)
}
func (t *TodoService) List(ids []string) {
    fmt.Println("\n=== Todo 列表 ===")
    for _, id := range ids {
        if v, ok := t.store.Load(id); ok {
            fmt.Printf("  [ ] %s: %s\n", id, v)
        }
    }
}
func main() {
    svc := &TodoService{store: &MemStorage{}}
    svc.Add("1", "学习 Go 接口的隐式实现")
    svc.Add("2", "实现可替换存储层的 Todo 服务")
    svc.Add("3", "理解 nil 接口与 nil 指针的区别")
    svc.Done("2")
    svc.List([]string{"1", "2", "3"})
}
```

完整文件：`examples/ex03-storage-todo.go`

### 示例 4：nil 接口陷阱

```go
package main
import "fmt"
type Speaker interface {
    Speak() string
}
type Dog struct {
    Name string
}
// 方法内检查 nil 接收者——防御性编程
func (d *Dog) Speak() string {
    if d == nil {
        return "<nil dog 无法叫>"
    }
    return "汪汪，我是" + d.Name
}
func main() {
    // 情况 1：接口本身为 nil
    var s Speaker = nil
    fmt.Printf("nil 接口: s == nil → %v\n", s == nil) // true
    // s.Speak() // panic
    // 情况 2：接口持有 nil 指针——接口非 nil！
    var d *Dog = nil
    s = d
    fmt.Printf("持有 nil 指针: s == nil → %v\n", s == nil) // false!
    fmt.Println(s.Speak()) // 方法可调用（Speak 内检查了 nil）
    // 情况 3：正常使用
    s = &Dog{Name: "大黄"}
    fmt.Println(s.Speak())
}
```

完整文件：`examples/ex04-nil-interface.go`

核心教训：接口值 =（类型, 数据指针），类型非 nil 时接口就不为 nil。返回接口时永远 `return nil`，不写 `return (*Dog)(nil)`。

### 示例 5：类型断言与 type switch——多源数据分发

```go
package main
import "fmt"
type CANFrame struct {
    ID   uint32
    Data [8]byte
}
func (c CANFrame) String() string {
    return fmt.Sprintf("CANFrame{ID=0x%X}", c.ID)
}
func processData(data interface{}) {
    switch v := data.(type) {
    case CANFrame:
        fmt.Printf("CAN 帧  : ID=0x%X Data=%v\n", v.ID, v.Data[:4])
    case float64:
        fmt.Printf("传感器值: %.2f\n", v)
    case string:
        fmt.Printf("日志消息: %s\n", v)
    case []string:
        fmt.Printf("信号列表: %v\n", v)
    default:
        fmt.Printf("未知类型: %T = %v\n", v, v)
    }
}
func main() {
    var val interface{} = CANFrame{ID: 0x7E8, Data: [8]byte{0x41, 0x0D, 0x00, 0x00}}
    if frame, ok := val.(CANFrame); ok {
        fmt.Println("断言成功:", frame.String())
    }
    if _, ok := val.(int); !ok {
        fmt.Println("val 不是 int 类型——断言失败不 panic")
    }
    fmt.Println("\n=== type switch 分发 ===")
    processData(CANFrame{ID: 0x18F, Data: [8]byte{0x00, 0xFA, 0x20}})
    processData(36.5)
    processData("车速传感器离线")
    processData([]string{"turn_left", "brake"})
}
```

完整文件：`examples/ex05-type-switch.go`

## 7. 总结

### 关键要点

1. **方法就是带接收者的函数**：Go 没有类——struct 组织数据，method 附加行为
2. **指针接收者才能修改状态**：值接收者操作副本，指针接收者操作原值
3. **隐式实现**：无需 `implements`，方法匹配即满足接口——依赖反转是自然行为
4. **小接口比大接口好**：`io.Reader`（1 个方法）是典范——实现负担小、组合灵活
5. **nil 接口** `!=` **持有 nil 指针的接口**：接口值 =（类型, 数据指针）对，类型非 nil 时接口就不为 nil
6. **`*T` 方法集** `>` **`T` 方法集**：指针接收者方法只属于 `*T`；值接收者同时属于 `T` 和 `*T`
7. **组合嵌入**：嵌入类型的字段和方法都提升到外层——无需继承即可复用

### 跨语言对比：方法/接口

| 概念 | Go | Java | C++ | Rust | Python |
|------|-----|------|-----|------|--------|
| 行为绑定 | 方法（接收者函数） | 类方法 | 成员函数/虚函数 | `impl` 块方法 | 类方法 |
| 接口/契约 | `interface`（隐式） | `interface`/`abstract` | 纯虚类/concept | `trait` | Protocol/ABC |
| 实现声明 | 无（方法匹配） | `implements` | `: public` 继承 | `impl Trait for Type` | 继承 ABC |
| 多态机制 | iface 动态分发 | vtable | vtable | trait object/单态化 | duck typing |
| 类型检查 | 类型断言/type switch | `instanceof` | `dynamic_cast` | `downcast_ref` | `isinstance()` |
| 继承 | 无（组合嵌入） | 单继承+多接口 | 多继承 | 无（trait组合） | 多继承 |
| 运行时开销 | 2 指针(16B) | vtable | vtable | trait object 2指针 | 无静态检查 |

### 阶段验收清单

- [ ] 能区分值/指针接收者的适用场景，定义小而清晰的接口并写出多个实现
- [ ] 能解释隐式实现的工程优势，通过接口 mock 依赖
- [ ] 能正确使用 ok 模式断言和 type switch，识别 nil 接口陷阱

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：Sensor 接口、Storage 接口、Logger 接口、用接口模拟 CAN/UART 数据读取共 4 题。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**可替换存储层的 Todo 服务**（Storage 接口 + MemStorage + FileStorage，一条命令切换存储后端）。

- [ ] 完成 exercises 全部练习并对照参考实现复盘
- [ ] 独立完成 project 并通过其 README 验收标准

### 下一阶段

[包管理与工程结构阶段](../ph05-pkg-structure/05-pkg-structure.md)—— go mod 依赖管理、package 可见性、`cmd/internal/pkg` 目录规范、多包项目工程化组织。
