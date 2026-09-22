# Go 基础语法阶段

> 面向后端服务、云原生和通用数据平台方向，从 Go 的简洁语法和工程化风格起步。

## 1. 概述

Go 基础语法阶段的目标是：**能写简单 Go 程序，理解 Go 的简洁语法和工程风格**。Go 的设计哲学是"少即多"（Less is more）——刻意排除了很多其他语言有的特性，力求用最少的语法元素解决最多的问题。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 程序结构 | `package main`、`import`、`func main` |
| 数据 | 变量、常量、基本类型、零值（Zero Value） |
| 控制流 | 运算符、`if`、`switch`、`for`（唯一循环语句） |
| 集合 | 数组（Array）、切片（Slice）、映射（Map）、字符串（String） |
| 工具链 | `go run`、`go build`、`gofmt` |

这个阶段涵盖的内容比其他语言的基础语法阶段**更丰富**——Go 在基础阶段就引入了 slice 和 map，因为它们是用 Go 写任何实际程序的必需品。

这个阶段只涉及单文件的命令行程序，**不涉及方法（Method）、接口（Interface）、结构体嵌套和 goroutine 并发** — 那些是 ph04 方法与接口、ph06 并发编程阶段的内容。

## 2. 来源与演变

Go 由 Robert Griesemer、Rob Pike 和 Ken Thompson 于 2007 年在 Google 设计，2009 年开源，2012 年发布 1.0 版本。设计动机是解决 Google 内部大规模软件开发中的痛点：编译慢、依赖管理复杂、并发编程困难。

| 版本 | 年份 | 标志性变化 |
|------|------|-----------|
| Go 1.0 | 2012 | 首个稳定版本，确立向后兼容承诺 |
| Go 1.5 | 2015 | 自举（Go 编译器用 Go 重写），移除 C 依赖 |
| Go 1.11 | 2018 | Go Modules 引入 |
| Go 1.13 | 2019 | Go Modules 默认启用 |
| Go 1.18 | 2022 | 泛型（Generics）引入 |
| Go 1.21 | 2023 | `slices`/`maps` 标准库包 |
| Go 1.22 | 2024 | `for` 循环变量语义修复 |

**Go 的向后兼容承诺**：Go 1.x 的代码可以在后续 Go 1.y（y ≥ x）上编译，这在语言生态中非常罕见。

## 3. 语法与参数

### 3.1 程序结构

```go
package main    // 声明包名，main 包生成可执行文件

import "fmt"    // 导入标准库包

func main() {   // 程序入口
    fmt.Println("Hello, Go")
}
```

- `package main` 定义可执行程序
- `import` 引入其他包，未使用的导入会**编译报错**
- `func main()` 是入口函数，无参数无返回值

### 3.2 变量声明

```go
// 标准声明
var name string = "Go"
var age int = 15

// 类型推导
var score = 95          // 自动推导为 int

// 短变量声明（最常用）
count := 0              // 等价于 var count int = 0
name := "hello"         // 仅限函数内使用

// 批量声明
var (
    host string = "localhost"
    port int    = 8080
)

// 常量
const Pi = 3.14159
const (
    StatusOK    = 200
    StatusError = 500
)
```

| 声明方式 | 范围 | 说明 |
|----------|------|------|
| `var x T = v` | 函数内外 | 标准声明 |
| `var x = v` | 函数内外 | 类型推导 |
| `x := v` | **仅函数内** | 短变量声明 |
| `const X = v` | 函数内外 | 编译期常量 |

**关键概念**：`:=` 是最常用的声明方式，但它只能在函数内使用。包级别的变量必须用 `var`。

### 3.3 基本类型与零值

| 类型 | 零值 | 说明 |
|------|------|------|
| `bool` | `false` | 布尔类型 |
| `string` | `""` | 字符串（不可变字节序列） |
| `int`, `int8` ~ `int64` | `0` | 有符号整数 |
| `uint`, `uint8` ~ `uint64` | `0` | 无符号整数 |
| `float32`, `float64` | `0.0` | 浮点数 |
| `byte` | `0` | `uint8` 的别名 |
| `rune` | `0` | `int32` 的别名，表示 Unicode 码点 |

```go
var i int        // i = 0（零值）
var s string     // s = ""（零值，不是 nil）
var b bool       // b = false
var p *int       // p = nil（指针零值是 nil）
```

**零值（Zero Value）设计哲学**：Go 的每个类型都有定义好的零值，变量声明后保证有值而不是随机内存。这消除了未初始化变量的不确定性。

### 3.4 运算符

| 类别 | 运算符 | 示例 |
|------|--------|------|
| 算术 | `+ - * / %` | `a + b`, `x % 2` |
| 关系 | `== != < > <= >=` | `a == b` |
| 逻辑 | `&& \|\| !` | `a > 0 && b > 0`（短路求值） |
| 位运算 | `& \| ^ &^ << >>` | `n &^ 1`（位清除，Go 特有） |
| 赋值 | `= += -= *= /=` | `x += 1` |
| 自增自减 | `++ --` | `i++`（仅后置，且是语句不是表达式） |

**注意**：
- Go **没有三元运算符**——用 `if`/`else` 替代
- `i++` 是**语句**而非表达式，`a := i++` 无法通过编译；也没有前置 `++i`

### 3.5 控制流

**if**：条件表达式不需要括号，但花括号必须有：

```go
if score >= 90 {
    fmt.Println("A")
} else if score >= 60 {
    fmt.Println("Pass")
} else {
    fmt.Println("Fail")
}

// if 支持初始化语句
if err := doSomething(); err != nil {
    fmt.Println("error:", err)
}
// err 的作用域仅限于 if/else 块
```

**for — Go 唯一的循环语句**：

```go
// 经典 for 循环（替代 C 的 for）
for i := 0; i < 10; i++ {
    fmt.Println(i)
}

// while 风格（替代 C 的 while）
n := 10
for n > 0 {
    fmt.Println(n)
    n--
}

// 无限循环（替代 C 的 while(1) / for(;;)）
for {
    fmt.Println("loop")
    break
}

// range 遍历（最常用）
nums := []int{1, 2, 3}
for i, v := range nums {
    fmt.Printf("nums[%d] = %d\n", i, v)
}
```

Go **没有 `while` 关键字**——`for` 是唯一的循环语句，三种形式覆盖所有循环场景。

**switch**：Go 的 switch 不需要 `break`，每个 case 默认不会贯穿（Fallthrough）：

```go
switch day {
case 1:
    fmt.Println("Monday")
case 2:
    fmt.Println("Tuesday")
default:
    fmt.Println("Other")
}

// switch 也可以没有表达式（替代 if-else 链）
score := 85
switch {
case score >= 90:
    fmt.Println("A")
case score >= 60:
    fmt.Println("Pass")
default:
    fmt.Println("Fail")
}
```

### 3.6 数组、切片、映射

```go
// 数组（Array）：固定长度，值类型
var arr [5]int = [5]int{1, 2, 3, 4, 5}
fmt.Println(arr[0], len(arr))

// 切片（Slice）：动态长度，引用底层数组
// 切片是 Go 中使用最频繁的数据结构
slice := []int{1, 2, 3}
slice = append(slice, 4)   // 追加元素
sub := slice[1:3]           // 切片操作 [low:high]
fmt.Println(len(slice), cap(slice))

// 映射（Map）：键值对
scores := map[string]int{
    "alice": 90,
    "bob":   85,
}
scores["carol"] = 92                // 添加
fmt.Println(scores["alice"])
if v, ok := scores["unknown"]; ok { // 安全查询
    fmt.Println(v)
} else {
    fmt.Println("not found")
}
```

| 类型 | 长度 | 值/引用 | 说明 |
|------|------|--------|------|
| 数组 `[N]T` | 固定 | 值类型 | 长度是类型的一部分 |
| 切片 `[]T` | 动态 | 引用语义 | 最常用的集合类型，建立在数组之上 |
| 映射 `map[K]V` | 动态 | 引用语义 | 哈希表，支持安全查询 |

**注意**：Go 的数组是**值类型**——赋值和传参会复制整个数组。实际工作中绝大多数场景用切片而不是数组。

### 3.7 字符串与指针

```go
s := "hello, 世界"         // 字符串是不可变的字节序列
fmt.Println(len(s))       // 字节长度（不是字符数）
fmt.Println(utf8.RuneCountInString(s))  // 字符数（需 import "unicode/utf8"）

// 遍历字符串：
for i, r := range s {     // range 按 rune 遍历
    fmt.Printf("%d: %c\n", i, r)
}

// 指针：Go 有指针但没有指针运算
x := 42
p := &x                   // p 是指向 x 的指针
fmt.Println(*p)           // 解引用
*p = 100                  // 通过指针修改值
```

Go 的指针比 C 的指针**受限**：
- 没有指针运算（不能 `p++`）
- 不能对指针做类型转换
- 但保留值传递语义——可以通过指针修改外部变量

## 4. 底层原理

### 4.1 Go 的编译模型

```text
go mod init example   # 初始化模块（Go 1.16+ 必须）
go run main.go        → 编译 + 运行（开发用）
go build              → 编译为单一可执行文件
go build -o app       → 指定输出文件名
```

> **重要**：Go 1.16 起模块模式（Module Mode）是默认行为。创建新项目时先用 `go mod init <模块名>` 初始化，否则 `go run` 可能报错 `no required module`。

Go 编译为**静态链接**的本地二进制文件——不需要任何运行时依赖（不需要 JVM、不需要解释器、不需要动态库）。编译速度极快（大型项目通常几秒以内），这是 Go 设计的核心成就之一。

### 4.2 切片的底层结构

```go
// 切片在运行时的内部表示（概念上）：
type slice struct {
    ptr *T   // 指向底层数组的指针
    len int  // 当前长度
    cap int  // 容量
}
```

理解这个结构能帮助你避免很多切片相关的坑：
- 切片赋值只复制 header（ptr/len/cap），不复制底层数据
- `append` 可能触发扩容，分配新的底层数组
- 子切片共享底层数组，修改可能互相影响

### 4.3 零值设计的工程意义

```go
var m map[string]int
// m["key"] = 1  // panic! nil map 不能直接写

var s []int
s = append(s, 1)  // nil slice 可以 append，这很合理

var mu sync.Mutex
mu.Lock()         // 零值 mutex 可以直接使用，无需初始化
```

Go 的零值设计意味着很多类型不需要显式的构造函数——零值本身就是可用的"空"状态。

### 4.4 gofmt 与代码风格

```go
// 你写什么不重要，gofmt 说了算：
// gofmt 自动统一格式：缩进、空格、换行
// gofmt -w main.go  // 直接写入文件
// gofmt -d main.go  // 显示差异
```

Go 社区不会争论代码格式——`gofmt` 是**强制标准**。所有标准 Go 代码都用 tab 缩进、左花括号不换行。这在语言生态中是独一无二的。

## 5. 使用场景

基础语法阶段适合解决的问题：

| 场景 | 涉及知识点 |
|------|-----------|
| 计算器 | 变量、算术运算、输入输出 |
| 素数判断 | 循环、条件分支 |
| 词频统计 | map、range、字符串处理 |
| 字符串工具 | 字符串操作、rune 遍历 |
| 命令行工具 | flag 解析、fmt 输出 |

## 6. 代码示例

> **说明**：示例 3 起会用到自定义函数——函数与错误处理是下一阶段（ph02）的主题，此处模仿写法即可。
> 完整可运行文件见 [`examples/`](./examples/)，每个示例对应一个 `ex0*-*.go`，用 `go run ex0X-*.go` 即可运行，已在本环境（Go 1.22.2）验证。

### 示例 1：命令行计算器

完整文件：`examples/ex01-calculator.go`

```go
package main

import "fmt"

func main() {
    var a, b float64
    var op string

    fmt.Print("输入算式 (如 3 + 4): ")
    fmt.Scanf("%f %s %f", &a, &op, &b)

    switch op {
    case "+":
        fmt.Printf("%.2f\n", a+b)
    case "-":
        fmt.Printf("%.2f\n", a-b)
    case "*":
        fmt.Printf("%.2f\n", a*b)
    case "/":
        if b != 0 {
            fmt.Printf("%.2f\n", a/b)
        } else {
            fmt.Println("错误: 除数为零")
        }
    default:
        fmt.Println("不支持的操作符")
    }
}
```

### 示例 2：词频统计

完整文件：`examples/ex02-word-frequency.go`

```go
package main

import (
    "fmt"
    "strings"
)

func main() {
    text := "apple banana apple orange banana apple"
    words := strings.Fields(text)

    freq := make(map[string]int)
    for _, w := range words {
        freq[w]++
    }

    for word, count := range freq {
        fmt.Printf("%s: %d\n", word, count)
    }
}
```

### 示例 3：判断素数

完整文件：`examples/ex03-is-prime.go`

```go
package main

import "fmt"

func isPrime(n int) bool {
    if n < 2 {
        return false
    }
    for i := 2; i*i <= n; i++ {
        if n%i == 0 {
            return false
        }
    }
    return true
}

func main() {
    fmt.Print("1-100 的素数: ")
    for i := 1; i <= 100; i++ {
        if isPrime(i) {
            fmt.Printf("%d ", i)
        }
    }
    fmt.Println()
}
```

### 示例 4：Todo CLI（用 slice 和 map）

完整文件：`examples/ex04-todo-cli.go`

```go
package main

import "fmt"

func main() {
    todos := []string{}   // 空切片

    // 添加
    todos = append(todos, "学习 Go 基础语法")
    todos = append(todos, "写一个命令行工具")
    todos = append(todos, "学习 Go 并发")

    // 列出
    fmt.Println("Todo 列表：")
    for i, todo := range todos {
        fmt.Printf("  %d. %s\n", i+1, todo)
    }

    // 删除第一个
    if len(todos) > 0 {
        todos = todos[1:]
    }

    fmt.Println("\n完成一项后：")
    for i, todo := range todos {
        fmt.Printf("  %d. %s\n", i+1, todo)
    }
}
```

## 7. 总结

### 关键要点

1. **Go 没有 while**：`for` 是唯一的循环关键字，三种形态覆盖所有循环场景
2. **短变量声明 `:=`**：最常用的声明方式，仅限函数内使用
3. **零值保证**：所有类型都有定义好的零值，未初始化的变量也有确定的值
4. **代码格式由 gofmt 统一**：格式不是个人偏好问题，是工具自动处理的问题
5. **切片（Slice）是主力**：数组使用场景很少，切片才是日常数据结构
6. **Go 编译极快**：生成静态链接的单一可执行文件

### 跨语言对比：基础语法（与 C）

| 方向 | C | Go |
|------|---|----|
| 循环 | `for`/`while`/`do-while` | 只有 `for` |
| 变量声明 | `int x = 5;` | `x := 5` 或 `var x int = 5` |
| 字符串 | `char[]` / `char*` | `string`（不可变） |
| 动态数组 | `malloc`/`free` | `[]T` 切片 |
| 代码格式 | 手动 | `gofmt` 自动 |
| 未初始化变量 | 不确定 | 零值保证 |
| 指针运算 | 支持 | 不支持 |

### 阶段验收清单

- [ ] 能独立运行 `go run` 和 `go build`
- [ ] 能写出基础控制流（`if`、`for`、`switch`）和函数
- [ ] 能使用 slice 和 map 处理数据
- [ ] 能使用 `gofmt` 格式化代码

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：Todo CLI——增删查改待办事项，用 slice 存储、命令行交互。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[函数与错误处理阶段](../ph02-func-error/02-func-error.md) — 掌握多返回值、`defer`、`panic`/`recover` 和显式错误处理。
