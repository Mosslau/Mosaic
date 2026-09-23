# Go Slice、Map、Struct 阶段

> 面向后端服务、云原生和通用数据平台方向，掌握 Go 最常用的数据组织方式。

## 1. 概述

Go Slice、Map、Struct 阶段的目标是：**掌握 Go 最核心的三种数据组织原语，理解其底层机制与工程陷阱**。这三个类型覆盖了后端开发中绝大多数的数据承载需求——从内存缓冲区到键值索引、从业务实体到配置聚合。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 数组与 Slice | 数组是值类型、Slice 是描述符、len/cap/append、底层数组共享 |
| Map | 创建与初始化、查询与 ok 模式、删除与遍历、nil map 陷阱 |
| Struct | 定义与初始化、组合嵌入（匿名字段）、字段提升、内存对齐 |

这个阶段的核心不是记住 API，而是**理解数据在内存中的布局**：Slice 的 header 和底层数组分离、Map 的哈希桶与无序遍历、Struct 的组合优先思维。

范围边界：本阶段不涉及 interface 与 method（ph04），不涉及 goroutine 与 channel（ph06），不涉及泛型。

## 2. 来源与演变

Go 的设计者在 C 的基础上重新权衡了数据结构的设计取舍：

| 设计决策 | 传统方案（C） | Go 方案 | 设计意图 |
|----------|-------------|--------|---------|
| 动态数组 | `malloc` + 手动管理 | Slice：header + 底层数组 | 安全、自动扩容、零拷贝切片 |
| 键值映射 | 手写哈希 / 第三方库 | 内置 map | 统一语法、编译器优化 |
| 复合数据 | `struct`（无方法绑定） | `struct` + 后续 method | 先组织数据，再追加行为 |

**Slice 取代 Array 成为主力**：Go 中数组 `[3]int` 是值类型——赋值会复制整个数组，类型还包含长度（`[3]int` 和 `[5]int` 是不同的类型），因此极少直接使用。Slice `[]int` 是一个轻量描述符，赋值只复制 24 字节的 header，底层数组共享，这才是 Go 的日常数据结构。

**Map 的哈希实现**：Go map 采用链式哈希桶（每个桶存 8 对 KV），通过 tophash 加速探测，负载因子约 6.5 时触发翻倍扩容，搬迁过程渐进完成。

**Struct 的组合哲学**：Go 没有继承，通过结构体嵌入（匿名字段）实现字段提升和组合复用。这呼应了 Go 设计者 Rob Pike 的名言："Design the data structures, and the algorithms will be obvious."

本文示例以 **Go 1.21+** 为基线（`slices`/`maps` 标准库包可用），本环境验证工具链为 Go 1.22.2。slice、map、struct 的核心语义自 Go 1.0 起稳定。

## 3. 语法与参数

### 3.1 数组与 Slice 对比

数组的类型包含长度，是值类型；Slice 的类型不含长度，是引用底层数组的描述符：

```go
package main

import "fmt"

func main() {
    // 数组：类型包含长度，赋值会复制整个数组
    arr1 := [3]int{1, 2, 3}
    arr2 := arr1
    arr2[0] = 99
    fmt.Println(arr1[0]) // 1 — arr1 不受影响，因为 arr2 是副本

    // Slice：赋值只复制 header，共享底层数组
    s1 := []int{1, 2, 3}
    s2 := s1
    s2[0] = 99
    fmt.Println(s1[0]) // 99 — s1 也被修改
}
```

数组的长度是类型的一部分：`[3]int` 与 `[5]int` 是不同的类型，不能互相赋值。这使数组极少直接使用，只在少数场景（如固定大小的密码学常量、`[32]byte`）中出现。

### 3.2 Slice 操作：len、cap、append、copy

```go
package main

import "fmt"

func main() {
    s := make([]int, 3, 5) // len=3, cap=5
    s[0], s[1], s[2] = 10, 20, 30
    fmt.Println("len:", len(s), "cap:", cap(s), "val:", s)

    // append：超出 cap 时自动扩容，返回新 slice
    s = append(s, 40, 50) // 未超 cap
    fmt.Println("len:", len(s), "cap:", cap(s), "val:", s)
    s = append(s, 60) // 超出 cap，扩容
    fmt.Println("len:", len(s), "cap:", cap(s), "val:", s)

    // copy：按 min(len(dst), len(src)) 复制，不会扩容
    dst := make([]int, 2)
    n := copy(dst, s)
    fmt.Println("copied:", n, "dst:", dst)
}
```

切片表达式 `s[low:high]` 产生一个**共享同一底层数组**的新 Slice header（cap = 原 cap - low）。

### 3.3 Map：创建、查询、删除、遍历

```go
package main

import "fmt"

func main() {
    // 字面量创建
    status := map[string]int{"cpu": 45, "mem": 72}

    // ok 模式：安全判断 key 是否存在
    if v, ok := status["disk"]; ok {
        fmt.Println("disk:", v)
    } else {
        fmt.Println("disk: not found")
    }

    // 零值：不存在的 key 返回 value 类型的零值
    fmt.Println("gpu:", status["gpu"]) // 0，不是 error

    // 删除 key
    delete(status, "mem")

    // 遍历——顺序不固定
    for k, v := range status {
        fmt.Println(k, ":", v)
    }
}
```

nil map 可以读取（返回零值），但写入会 panic（`assignment to entry in nil map`）。map 不是并发安全的——多 goroutine 同时读写需要 `sync.Mutex` 或 `sync.Map`。

### 3.4 Struct：定义、初始化、组合嵌入

```go
package main

import "fmt"

type Motor struct {
    Speed   int
    Enabled bool
}

type Device struct {
    DEVICE_ID   string
    Motor // 匿名字段嵌入，Motor 的字段自动提升到 Device
}

func main() {
    v := Device{
        DEVICE_ID:   "LSVAA4184ES000001",
        Motor: Motor{Speed: 120, Enabled: true},
    }
    // 字段提升：直接访问嵌入类型的字段
    v.Speed = 90
    fmt.Printf("DEVICE_ID=%s Speed=%d Enabled=%v\n", v.DEVICE_ID, v.Speed, v.Enabled)
}
```

嵌套时命名冲突：外层字段优先；同一层级有冲突时编译器报错，访问时需写全路径。

## 4. 底层原理

### 4.1 Slice 运行时结构（SliceHeader）

ph01 4.2 节用代码注释展示过 Slice 的底层结构，这里系统讲透。Slice 在运行时是一个 24 字节的描述符：

```text
type SliceHeader struct {
    Data uintptr // 指向底层数组的指针
    Len  int     // 当前元素个数
    Cap  int     // 容量（从 Data 开始到底层数组末尾的元素数）
}
```

赋值 `s2 := s1` 只复制这 24 字节（一个指针 + 两个 int），不复制底层数组。这就是"子切片修改影响原切片"的根本原因。

**append 扩容规则**（Go 1.18+）：cap < 256 时翻倍；cap >= 256 时增长因子约为 `(cap + 3*256) / 4`，最终趋近 25%。扩容后底层数组是新分配的，旧 Slice 不再受影响——这是解除共享的关键机制。

`copy(dst, src)` 只复制元素值，不复制 header 关联，因此两个 Slice 各自独立。

### 4.2 Map 的哈希桶与扩容

Go map 的底层实现是一张哈希表，核心结构是 `hmap`：

```text
hmap {
    count     int      // 元素个数
    B         uint8    // 桶数量的对数（buckets = 2^B）
    buckets   unsafe.Pointer
    oldbuckets unsafe.Pointer // 渐进搬迁时的旧桶
    ...
}
```

每个桶（`bmap`）存放 8 对 key/value 和一个 tophash 数组。查找时：hash(key) → 低位选桶、高位存入 tophash 用于快速比对。

**扩容触发条件**：溢出桶过多或负载因子（count / 2^B）超过 6.5。扩容时桶数量翻倍，旧桶中的数据**渐进式搬迁**到新桶（每次读写操作搬迁 1-2 个旧桶），避免一次性的延迟抖动。

**遍历顺序不稳定的原因**：Go 故意在遍历起始位置注入随机偏移（`mapiterinit` 中调用 `fastrand`），让依赖顺序的代码在开发阶段就暴露问题。

### 4.3 Struct 内存对齐

Go 遵循平台对齐规则：每个字段的起始地址必须是其类型大小的整数倍，结构体整体大小必须是最大字段对齐值的整数倍：

```go
package main

import (
    "fmt"
    "unsafe"
)

type BadLayout struct {
    A byte  // 1B + 7B padding
    B int64 // 8B
    C byte  // 1B + 7B padding
} // 总 24B

type GoodLayout struct {
    B int64 // 8B
    A byte  // 1B
    C byte  // 1B + 6B padding
} // 总 16B

func main() {
    fmt.Println("Bad:", unsafe.Sizeof(BadLayout{}))  // 24
    fmt.Println("Good:", unsafe.Sizeof(GoodLayout{})) // 16
}
```

将大字段放在前面能减少 padding。在日常开发中不需要刻意优化，但了解这个机制有助于理解编译器行为。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 数据缓冲区与动态集合 | Slice len/cap/append、扩容控制 |
| 字符串处理与子串操作 | 切片表达式、底层数组共享 |
| ID 快速索引与缓存 | Map 创建、ok 模式查询、delete |
| 业务实体建模 | Struct 定义、字段组合 |
| 设备/设备状态表 | Map + Struct 组合、遍历、更新 |
| 多维度数据聚合 | Slice of Struct、排序与过滤 |

**不适合 / 注意事项**：

- nil map 不可写入——声明后必须 `make` 或字面量初始化
- 多个 goroutine 并发读写 map 会触发 fatal error，必须加锁或使用 `sync.Map`
- 子 Slice 修改影响原 Slice——需要独立副本时使用 `copy`
- append 后原 Slice 变量若不重新赋值，底层扩容产生的修改对旧变量不可见
- 依赖 map 遍历顺序不可靠——需要有序遍历时先收集 key 再排序

## 6. 代码示例

> 完整可运行文件见 [`examples/`](./examples/)，每个示例对应一个 `ex0*-*.go`，已在本环境用 Go 1.22.2 验证（gofmt 无差异、go vet 通过、go run 输出符合预期）。逐文件 `go run` 运行，详见 examples/README.md。

### 示例 1：Slice 扩容实验

完整文件：`examples/ex01-slice-grow.go`

```go
package main

import "fmt"

func main() {
    var s []int
    for i := 0; i < 12; i++ {
        s = append(s, i)
        fmt.Printf("append %2d: len=%2d cap=%2d val=%v\n", i, len(s), cap(s), s)
    }
}
```

### 示例 2：子切片共享底层数组

完整文件：`examples/ex02-subslices-share.go`

```go
package main

import "fmt"

func main() {
    // 创建底层数组容量较大的 slice
    original := make([]int, 0, 10)
    original = append(original, 1, 2, 3, 4, 5)

    // 子切片共享底层数组（cap 从 low 位置算起）
    sub := original[1:3] // len=2 cap=9
    fmt.Println("--- 修改子切片 ---")
    sub[0] = 99
    fmt.Println("original:", original) // [1 99 3 4 5] — 被影响
    fmt.Println("sub:     ", sub)      // [99 3]

    // append 在 cap 范围内仍然共享
    sub = append(sub, 100)
    fmt.Println("\n--- 子切片 append（未超 cap）---")
    fmt.Println("original:", original) // [1 99 3 100 5] — 仍被影响
    fmt.Println("sub:     ", sub)      // [99 3 100]

    // append 超出 cap 触发扩容，分配新底层数组
    sub = append(sub, 200, 300, 400, 500, 600, 700, 800)
    sub[0] = 0 // 修改新的底层数组
    fmt.Println("\n--- 扩容后修改 ---")
    fmt.Println("original:", original) // [1 99 3 100 5] — 不受影响
    fmt.Println("sub:     ", sub)      // [0 3 100 200 300 400 500 600 700 800]
}
```

### 示例 3：Map 安全操作与遍历

完整文件：`examples/ex03-map-ops.go`

```go
package main

import "fmt"

func main() {
    // make 初始化（字面量 nil 不可写）
    cache := make(map[string]int)
    cache["cpu"] = 45
    cache["mem"] = 72

    // 安全查询：ok 模式判断 key 是否存在
    keys := []string{"cpu", "disk", "mem"}
    for _, k := range keys {
        if v, ok := cache[k]; ok {
            fmt.Printf("%s=%d\n", k, v)
        } else {
            fmt.Printf("%s: not found\n", k)
        }
    }

    // 删除后查询
    delete(cache, "mem")
    if _, ok := cache["mem"]; !ok {
        fmt.Println("mem 已删除")
    }

    // 遍历——多次运行输出顺序可能不同
    cache["gpu"] = 20
    cache["net"] = 10
    fmt.Println("\n所有条目:")
    for k, v := range cache {
        fmt.Printf("  %s: %d\n", k, v)
    }
}
```

### 示例 4：Struct 嵌入——设备实体

完整文件：`examples/ex04-struct-embed.go`

```go
package main

import "fmt"

type Motor struct {
    Speed   int
    Enabled bool
}

type Component struct {
    Level int // 百分比 0-100
    Temp  float64
}

type Device struct {
    DEVICE_ID     string
    Model   string
    Motor          // 匿名字段嵌入
    Component        // 匿名字段嵌入
}

func main() {
    v := Device{
        DEVICE_ID:   "LSVAA4184ES000001",
        Model: "Model S",
        Motor: Motor{Speed: 80, Enabled: true},
        Component: Component{Level: 72, Temp: 35.2},
    }

    // 字段提升：直接访问嵌入类型的字段
    fmt.Printf("DEVICE_ID=%s Model=%s\n", v.DEVICE_ID, v.Model)
    fmt.Printf("Speed=%d Enabled=%v\n", v.Speed, v.Enabled)
    fmt.Printf("Component=%d%% Temp=%.1fC\n", v.Level, v.Temp)

    // 也可以通过嵌入类型名访问
    v.Motor.Speed = 100
    v.Component.Level = 85
    fmt.Printf("更新后: Speed=%d Component=%d%%\n", v.Speed, v.Level)
}
```

### 示例 5：设备状态管理（Map + Struct）

完整文件：`examples/ex05-device-status.go`

```go
package main

import (
    "fmt"
    "sort"
)

type Device struct {
    ID     string
    Type   string
    Status string
    CPU    float64
    Mem    float64
}

func main() {
    devices := make(map[string]Device)

    // 添加设备
    devices["gw-001"] = Device{ID: "gw-001", Type: "gateway", Status: "online", CPU: 45.2, Mem: 72.1}
    devices["cam-002"] = Device{ID: "cam-002", Type: "camera", Status: "offline", CPU: 0, Mem: 0}
    devices["db-003"] = Device{ID: "db-003", Type: "database", Status: "online", CPU: 68.5, Mem: 85.3}

    // 查询单个设备
    if d, ok := devices["gw-001"]; ok {
        fmt.Printf("查询 gw-001: Status=%s CPU=%.1f%% Mem=%.1f%%\n", d.Status, d.CPU, d.Mem)
    }

    // 更新设备状态（struct 是值类型，需回写）
    if d, ok := devices["cam-002"]; ok {
        d.Status = "online"
        d.CPU = 23.7
        d.Mem = 45.0
        devices["cam-002"] = d
    }

    // 下线设备
    if d, ok := devices["db-003"]; ok {
        d.Status = "offline"
        devices["db-003"] = d
    }

    // 遍历设备（按 ID 排序输出以保持稳定）
    ids := make([]string, 0, len(devices))
    for id := range devices {
        ids = append(ids, id)
    }
    sort.Strings(ids)

    fmt.Println("\n=== 设备状态表 ===")
    for _, id := range ids {
        d := devices[id]
        fmt.Printf("%s | %-8s | %-7s | CPU:%5.1f%% | Mem:%5.1f%%\n",
            d.ID, d.Type, d.Status, d.CPU, d.Mem)
    }

    // 统计在线设备数
    online := 0
    for _, d := range devices {
        if d.Status == "online" {
            online++
        }
    }
    fmt.Printf("\n在线设备: %d/%d\n", online, len(devices))
}
```

## 7. 总结

### 关键要点

1. **数组是值类型，Slice 是描述符**：`[3]int` 赋值复制整个数组（含长度），`[]int` 赋值只复制 24 字节 header，共享底层数组
2. **append 扩容有阈值**：cap < 256 加倍，>= 256 斜率下降趋近 25%；扩容分配新数组，旧 Slice 和通过它获得的子切片不再受新 append 影响
3. **子切片共享底层数组是双刃剑**：零拷贝子切片高效，但不小心会互相影响；需要独立副本时用 `copy`
4. **map 查询用 ok 模式**：`v, ok := m[key]` 区分"不存在"与"零值"；nil map 可读不可写
5. **map 遍历顺序不稳定**：Go 故意注入随机偏移，依赖顺序的代码会在不同运行中暴露问题
6. **map 不是并发安全的**：多 goroutine 同时读写会报 fatal error，需要 `sync.Mutex` 保护
7. **struct 组合优先于继承式思维**：Go 通过嵌入（匿名字段）实现字段提升，没有类继承体系

### 跨语言对比：数据结构

| 概念 | Go | Python | Java | Rust |
|------|-----|--------|------|------|
| 动态数组 | `[]int`（Slice） | `list` | `ArrayList<T>` | `Vec<T>` |
| 哈希表 | `map[K]V` | `dict` | `HashMap<K,V>` | `HashMap<K,V>` |
| 复合类型 | `struct`（组合嵌入） | `class`（继承） | `class`（继承） | `struct`（无继承） |
| 值/引用语义 | Array 值类型、Slice 引用语义 | 全部引用语义 | 基本类型值、对象引用 | 默认值类型、`&` 引用 |
| 零值机制 | 有（int=0, string=""） | 无（NameError） | 有（null） | 无（必须初始化） |
| 扩容控制 | 自动、不可配置 | 自动 | 可指定 initialCapacity | `Vec::with_capacity` |
| 遍历确定性 | Map 不确定 | dict 3.7+ 插入序 | LinkedHashMap 保持序 | HashMap 不确定 |

### 阶段验收清单

- [ ] 能解释 Slice 的 len 与 cap 区别，描述 append 扩容时底层数组的变化
- [ ] 能正确使用 `v, ok := m[key]` 判断 map key 是否存在，区分"零值"与"缺失"
- [ ] 能用 struct 组合表达业务实体（如设备 DEVICE_ID + Motor + Component）
- [ ] 能写出 Map + Struct 组合的管理程序（设备状态表、设备缓存等）
- [ ] 能说明子切片共享底层数组的场景与陷阱，知道何时需要 copy

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：设备状态管理 CLI——用 map + struct 管理设备列表、查询单设备状态、更新资源指标、按状态筛选。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[方法与接口阶段](../ph04-method-interface/04-method-interface.md)—— 方法定义、值/指针接收者抉择、interface 与多态、隐式实现与依赖反转。
