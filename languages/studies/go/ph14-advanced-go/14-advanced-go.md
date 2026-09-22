# Go 高级 Go 阶段

> 面向"从'会写 Go'到'懂 Go'"——本阶段把 ph01~ph13 用过的每个语法点拆开看底层：泛型（类型集与编译期实例化）、slice/map/channel/interface 的内部布局、defer 与 panic/recover 的运行时语义、GMP 调度与 GC 触发机制、以及反射 / unsafe / cgo 三件"高级工具"。全部结论都有本环境实测背书（扩容步长、defer 顺序、-race 输出、分派成本、反射结果、cgo 调用）。

## 1. 概述

Go 高级 Go 阶段的目标是（引用 Roadmap）：**理解 Go 底层机制和高级工程能力**。ph03 学会了用 slice/map/struct、ph04 学会了接口、ph06 学会了 goroutine/channel、ph13 学会了"用工具看现象"——本阶段回答这些现象**为什么长这样**：slice 为什么 append 会变慢（扩容的步长与拷贝）、map 并发写为什么会崩（内部并发检测 + 数据竞争）、接口方法为什么"有成本"（itab 间接跳转）、defer 到底什么时候执行（LIFO 栈与返回值交互）、`panic(nil)` 在 Go 1.21 后为什么变了（语义修正）、GMP 决定 goroutine 怎么调度、GC 为什么是"堆增长触发"而不是定时器。同时掌握三件高级工具的正确用法与边界：reflect（反射配置加载器）、unsafe（内存布局与 uintptr 陷阱）、cgo（调 C 库）。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 泛型 | 类型参数、约束（类型集 `~int \| ~float64`、`comparable`、方法集）、类型推断与显式实例化、编译期实例化（无运行时开销） |
| 容器底层 | slice 描述符与扩容算法（<256 翻倍、≥256 约 1.25 倍 + size class 取整，实测）、map 内部结构（经典 bucket 与 Go 1.24+ Swiss map）、并发写 fatal 实测 |
| 接口底层 | iface/eface 双字头、itab 动态分派、去虚拟化、类型断言/类型 switch、nil 陷阱三连、分派成本实测 |
| 运行时语义 | defer 五语义实测（LIFO/参数求值/闭包引用/命名返回值/执行时机）、panic/recover 铁律、GMP 调度模型、GC 触发机制（GOGC 实测）、Go 内存模型（happens-before 与数据竞争） |
| 高级工具 | reflect（Kind/Value/SetXxx，反射配置加载器）、unsafe（Sizeof/Alignof/Offsetof、uintptr 陷阱、checkptr 拦截）、cgo（调 C 库完整闭环） |

这个阶段只涉及"Go 运行时与编译器的底层机制 + 三件高级工具的用法"，**不涉及性能剖析方法论本身（benchmark/pprof/trace/逃逸分析的使用属 ph13 性能优化阶段）、PGO 与生产流量指导优化（属 [ph16 PGO 与高级性能优化阶段](../ph16-pgo-advanced-perf/16-pgo-advanced-perf.md)，roadmap 第 16 节）、语言级并发模型的设计用法（goroutine/channel/context 怎么组织并发属 ph06 并发编程阶段）、Go 版本演进与工具链管理（属 [ph15 Go 版本、工具链阶段](../ph15-version-toolchain/15-version-toolchain.md)，roadmap 第 15 节）和云原生部署（容器/K8s/可观测性属 ph12 云原生与部署阶段）** — 本阶段用标准库 + runtime 公开 API 就能完成全部观测，不拆 runtime 源码改行为，只"看"不改。

## 2. 来源与演变

**Go 底层机制的源头是 2007 年 Google 内部对"C++ 服务太复杂、太慢"的回应**：语言必须简单（可编译期完成的事绝不放运行时）、并发必须便宜（goroutine 的 M:N 调度让十万级并发成为常态）、内存必须自动管理（GC 但要让暂停可接受）。**设计哲学：把复杂度从程序员手里收进编译器与运行时，代价是"机制对用户不可见"——所以本阶段要用实验把它们逼出来**。泛型来得最晚（Go 1.18 才落地，因为设计团队坚持"简单性优先"反复否决提案）；cgo/reflect/unsafe 则从 Go 1.0 就存在——它们是"逃逸口"，永远留给需要的人。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| Go 1.0 发布 | 2012 | reflect / unsafe / cgo 随首发；GOMAXPROCS 默认 = 1（单核，需手动调） |
| Go 1.1 | 2013 | GOMAXPROCS 默认 = NumCPU（多核终于开箱即用） |
| Go 1.5 | 2015 | 并发 GC（三色标记 + 写屏障）替代 stop-the-world 标记；调度器重写（抢占式调度雏形） |
| Go 1.14 | 2020 | defer 改为开放编码（open-coded defer）：多数 defer 零开销，不再每处注册运行时调用 |
| Go 1.18 | 2022 | 泛型落地（类型参数 + 约束），历经近十年提案反复 |
| Go 1.21 | 2023 | `panic(nil)` 语义修正：recover 返回非 nil 的 `*runtime.PanicNilError`（旧行为 recover 得 nil，无法区分"没 panic"） |
| Go 1.24 | 2025 | map 改用 Swiss map 实现（8 槽 group + ctrl 字节 + SIMD 探测，7/8 装载因子），替换经典的 hmap/bmap 桶链 |

本文示例以 **go1.25.6** 为基线（本环境实际跑通——本阶段全部示例、练习、项目与实测数字均为 go1.25.6 / darwin / arm64 / Apple M4 Pro 上零第三方依赖的实测结果，可离线复现；cgo 实验另有本机 cc = Apple clang 21.0.0，CGO_ENABLED=1），验证工具链 go1.25.6（`go vet`、`go test -race`、`-gcflags=all=-d=checkptr=2`、`cc`/`ar` 全部可用）。需要特别说明版本敏感性：**map 内部结构在 Go 1.24 换代（Swiss map），panic(nil) 语义在 Go 1.21 修正，slice 扩容取整数字随架构变化**——本文全部标注了版本依赖点，读者在别的版本/架构上重跑，数字可能不同、规则相同；这正是"机制"与"实现细节"的分界。

**本阶段涉及的版本敏感点速查**（机制稳定、实现细节随版本变——写代码时"按机制设计"，读他人代码时"按版本看实现"）：

| 特性 | 稳定机制 | 版本敏感的细节 | 相关章节 |
|------|---------|---------------|---------|
| slice 扩容 | <256 翻倍、≥256 约 1.25 倍 | 取整后的具体容量数字随 size class/架构变 | 4.1 |
| map | 并发写不安全、遍历随机、O(1) 平摊 | 桶链 → Swiss map（Go 1.24）；装载因子 6.5 → 7/8 | 4.2 |
| defer | LIFO、参数即求值、可改命名返回值 | 开放编码（Go 1.14+）让多数 defer 零开销 | 3.2 |
| panic(nil) | recover 可捕获 | Go 1.21 起 recover 返回 `*runtime.PanicNilError`（不再返回 nil） | 3.2 |
| 泛型 | 编译期实例化、类型集约束 | Go 1.18 才引入——老代码里没有 | 3.1 |
| GOMAXPROCS | 默认 = 核数 | Go 1.1 前默认 1（单核） | 4.5 |

## 3. 语法与参数

### 3.1 Generics：类型参数、约束与类型集

**泛型让"一份代码、多种类型"在编译期完成**——函数或类型声明里出现类型参数（`[T ...]`），调用时编译器按实参推断或显式指定类型，然后为每种类型生成一份专用代码（实例化）。与接口多态的"运行时一个实现、动态分派"不同，**泛型是"编译期多个实现、零间接跳转"**：

```go
// 完整可运行版见 examples/ex01-generics/main.go（节选）
// Number 类型集约束：~ 表示底层类型（~int 同时接受 int 与底层为 int 的自定义类型），
// | 是并集；comparable 是内置约束（== 可用）；方法集约束要求"有这个方法"
type Number interface {
	~int | ~int32 | ~int64 | ~float32 | ~float64
}

func Sum[T Number](vs []T) T {
	var s T // T 的零值由类型集保证可构造
	for _, v := range vs {
		s += v // + 可用由类型集保证（这是约束的意义）
	}
	return s
}
```

**三个约束层次**（约束是泛型 API 的一部分，不是装饰）：

| 约束写法 | 含义 | 允许的操作 | 示例 |
|---------|------|-----------|------|
| `any`（= interface{}） | 任何类型 | 只存与传，不能运算 | `Box[T any]` |
| `comparable` | 可比较（== 可用） | 相等比较、map key | `Contains[T comparable]` |
| 类型集 `~int \| ~float64` | 底层类型匹配 | 数值运算（+ - * /） | `Sum[T Number]`、`Reduce[T Number]` |
| 方法集 `interface{ String() string }` | 有该方法 | 调用方法 | `Format[T Stringer]` |

**实测（ex01，go1.25.6）**：`Sum([]Celsius{10, 20, 30})` 返回 `60`——`type Celsius int` 满足 `~int` 约束；`Sum([]int{1,2,3})` 返回 `6`、`Sum([]float64{1.5,2.5})` 返回 `4`。**教学点**：① 类型推断（`Sum([]int{...})` 推出 `T=int`）与显式实例化（`Sum[int](...)`）两种写法等价；② 约束决定"函数体内能对这个类型做什么"——`Reduce` 用类型集约束因为要做加法，`any` 做不到；③ 泛型与接口的分工：泛型是"编译期多态"（性能无损失），接口是"运行时多态"（换取灵活性）——实践中"先接口后泛型"，泛型解决"同一算法要服务多种具体类型"（如 Map/Filter/Reduce），接口解决"行为抽象与依赖反转"（ph04）。

**泛型还是接口（选择三问）**：

| 问题 | 选泛型 | 选接口 |
|------|--------|--------|
| 同一份逻辑要服务几种类型？ | 多种具体类型（`[]int`/`[]float64` 都要） | 一个抽象行为、实现不限（`io.Writer`） |
| 需要在编译期保留类型信息吗？ | 要（类型集约束决定可做运算） | 不需要（运行时才知道具体类型） |
| 性能敏感吗？ | 是（零间接跳转，编译期实例化） | 可接受 itab 动态分派成本 |

**多数库函数的答案是"泛型 + 内部接口"混合**：对外提供泛型 API（编译期多态），内部用接口抽象掉需要替换的部件（运行时多态）——两种多态不是二选一，是各管一段。

> 泛型的完整演进细节（泛型方法、类型参数在方法上受限等）超出本阶段教学目标；**类型集的深入（交集、并集、`~` 与底层类型规则）是 Go 1.18 起最稳定的部分**，本文只覆盖最小充分子集。

### 3.2 defer 与 panic/recover：五语义实测

**defer 是"延迟执行"的注册表**：函数返回前、所有语句执行完后，按**后进先出（LIFO）**逆序执行。它的实现从 Go 1.14 起是"开放编码"（编译器把多数 defer 直接内联到返回路径上，零运行时注册开销），语义不变。五个可实测的语义（全部 go1.25.6 实测，见 ex03）：

| 语义 | 代码模式 | 实测结果 |
|------|---------|---------|
| ① LIFO 逆序 | 一个函数里连写三个 defer | `[body defer3 defer2 defer1]` |
| ② 参数即求值 | `defer f(n)`，随后 `n=100` | defer 捕获的 n=1（语句处已求值） |
| ③ 闭包看最终值 | `defer func(){ use(n) }()`，随后 `n=100` | 闭包捕获 n=100（引用最终值） |
| ④ 可改命名返回值 | `return 5` + defer `x *= 10` | 返回 50（defer 在返回前执行且能改值） |
| ⑤ recover 只在 defer 内有效 | defer 里 `recover()` | 捕获成功；不在 defer 里调用则无效 |

```go
// 完整可运行版见 examples/ex03-defer-panic/main.go（节选）
func namedReturn() (x int) {
	x = 1
	defer func() { x = x * 10 }() // defer 修改命名返回值：return 5 → 50
	return 5
}
```

**panic/recover 的运行时语义**（实测）：**recover 只有在 defer 函数内直接调用才有效**——普通位置调用 `recover()` 返回 nil 且不拦截 panic；**嵌套 panic 时后执行的 defer panic 覆盖先执行的**（recover 拿到内层值）；**Go 1.21+ 的 `panic(nil)` 会让 recover 返回非 nil 的 `*runtime.PanicNilError`**（旧行为返回 nil，无法区分"没 panic"——语义修正，实测 `recover()==nil? false`）；**panic 只终止当前 goroutine**（其他 goroutine 不受影响，未恢复的 panic 才终止进程）。生产模式：**panic 只用于"程序状态不可恢复"**（如初始化失败），业务错误用 error 返回（ph02）；必须跨 panic 边界时用 `defer recover()` 把 panic 转成 error（练习 sol-03 的 `SafeCall`）。

### 3.3 reflect：运行时类型与值的镜像

**反射（reflect）让程序在运行时检查并操作自己的类型**——`reflect.TypeOf(v)` 拿类型信息，`reflect.ValueOf(v)` 拿值句柄，`Value.SetXxx` 按 Kind 写值。它是"运行时多态的最后一公里"：当类型在编译期未知（配置文件、插件、通用序列化），反射是标准答案：

```go
// 完整可运行版见 examples/ex05-reflection-unsafe/main.go（节选，配置加载器核心）
// fillFromMap：遍历 struct 字段、读 cfg tag、按 Kind 转换、SetXxx 写入
func fillFromMap(rv reflect.Value, raw map[string]any) error {
	for i := 0; i < rv.NumField(); i++ {
		fv := rv.Field(i)
		ft := rv.Type().Field(i)
		key := ft.Tag.Get("cfg")
		if key == "" || key == "-" || !fv.CanSet() {
			continue // CanSet：只对可寻址的导出字段为 true
		}
		if v, ok := raw[key]; ok {
			if err := setByKind(fv, v); err != nil { /* 按 Kind 分派转换 */ }
		}
	}
	return nil
}
```

**反射的三个关键认知**（实测，见 ex05 与练习 sol-04）：① **JSON 数字进 `map[string]any` 一律是 float64**，取整数字段要做类型断言/转换；② **`float64→int64` 的溢出是静默的**——直接 `int64(x)` 在超出范围时结果实现相关，必须转换前查值域（`OverflowInt` 查的是 int64→目标类型，查不到源头，实测 `{"port":99999999999999999999}` 会被正确拦截为"超出 int64 范围"）；③ **反射有真实成本**（类型检查 + 间接写值），热路径上每次调用都是开销——所以"反射加载配置"适合**启动期一次性**使用，不适合每请求路径。配置加载器的完整实现见 ex05（JSON + 环境变量双来源）与练习 sol-04（env 覆盖 json）。

### 3.4 unsafe：绕过类型系统的三件套

**unsafe 包提供三个"尺寸/偏移"函数与一个特殊指针类型**——`unsafe.Sizeof(x)`（类型占用字节数）、`unsafe.Alignof(x)`（对齐要求）、`unsafe.Offsetof(s.f)`（字段偏移），以及 `unsafe.Pointer`（可与任意指针互转、可与 uintptr 互转的"万能指针"）。它的价值不在"危险"，而在**让 Go 程序能表达内存布局**（与 C 交互、序列化、性能优化）：

```go
// 完整可运行版见 examples/ex05-reflection-unsafe/main.go（节选）
// Point{X int32, Y int64, Z int32}：4+8+4=16 字节的数据，实际占 24 字节
fmt.Println(unsafe.Sizeof(Point{}), unsafe.Alignof(Point{}), // 24, 8
	unsafe.Offsetof(Point{}.Y)) // 8（Y 因 8 字节对齐后移，X 后面空 4 字节 padding）
```

**实测（go1.25.6）**：`Point{X:int32,Y:int64,Z:int32}` → Sizeof=24、Alignof=8、偏移 X@0 Y@8 Z@16——padding 让结构体比"数据总和"大 8 字节；`Mixed{A:bool,B:int64,C:float32,D:string}` → Sizeof=40（bool 后空 7 字节）；引用类型描述符大小：string=16（ptr+len）、slice=24（ptr+len+cap）、map/chan/func=8（单指针）。**教学点**：结构体字段重排（把同对齐等级字段放一起）是真实的省内存手段——这正是"unsafe 教你看清布局"的工程价值。

**uintptr 陷阱（实测 + 工具拦截）**：`uintptr` 是普通整数，**GC 不跟踪它**——把 `unsafe.Pointer` 转成 `uintptr` 保存再转回，等于亲手制造悬空指针（对象可能已被回收/移动）。`go run -tags=checkptrdemo -gcflags=all=-d=checkptr=2 .` 实测：`fatal error: checkptr: pointer arithmetic result points to invalid allocation`——checkptr（实验性运行时检测）能当场抓住这种转换；普通构建则"能跑出 42"，错误不暴露。**三条铁律**：① `unsafe.Pointer` 和 `uintptr` 的转换必须"立即使用、不留存"；② 需要保存地址用 `unsafe.Pointer`（参与 GC 跟踪），不要用 `uintptr`；③ 业务代码优先用 `encoding/binary`、`unsafe.Slice` 等安全封装，unsafe 只在性能关键路径与 FFI 里出现（roadmap 必会概念：reflect、unsafe、cgo 是高级工具，业务代码慎用）。

### 3.5 cgo：调用 C 代码的桥

**cgo 让 Go 程序直接调用 C 函数**——在 `import "C"` 前的注释块（preamble）里写 C 代码与链接指令，Go 侧用 `C.函数名` 调用、`C.int`/`C.size_t` 等映射类型传参：

```go
// 完整可运行版见 examples/ex06-cgo/main.go（节选）
/*
#cgo CFLAGS: -I./c_lib
#cgo LDFLAGS: /tmp/libaddvec.a -lm
#include <addvec.h>
extern double sin(double);
*/
import "C"

func addVec(a, b []int32) []int32 {
	out := make([]int32, len(a))
	C.addvec((*C.int)(unsafe.Pointer(&a[0])), (*C.int)(unsafe.Pointer(&b[0])),
		(*C.int)(unsafe.Pointer(&out[0])), C.size_t(len(a)))
	return out
}
```

**实测（本机 cc = clang 21.0.0，CGO_ENABLED=1，完整闭环跑通）**：写 `c_lib/addvec.c`（向量加法）→ `cc -c` 编成 `.o` → `ar rcs` 打包静态库 `/tmp/libaddvec.a` → cgo 链接 → Go 调用，输出 `addvec: [11 22 33 44]`；调 libm 的 `sin(pi/2)` 输出 `1.0`（与 `math.Sin` 一致）。**四个必须知道的点**：① **preamble 是 C 的天下**——`#cgo CFLAGS/LDFLAGS` 指定头文件路径与链接库；② **类型映射**：`C.int`（32 位）≠ Go 的 `int`（64 位），`C.size_t` 对应 `uintptr`；③ **切片 → C 指针要 `unsafe.Pointer(&s[0])` 桥接，C 侧不做边界检查**——越界是 C 的世界，这也是 cgo 让 Go 失去内存安全的入口之一（unsafe 是另一个）；④ **成本**：cgo 调用要跨越 Go/C 边界（栈切换、goroutine 绑定），比纯 Go 调用慢一个数量级——高频热路径避免 cgo。**cgo 的替代**：Go 生态内优先用 `syscall`/`golang.org/x/sys`（纯 Go 系统调用）；真需要 C 库时，用 cgo 封装成薄层、暴露 Go 风格 API（"cgo 只进不出"）。

## 4. 底层原理

### 4.1 slice：描述符 + 扩容算法

```text
slice 变量（24 字节描述符）       底层数组（堆或栈上的连续内存）
┌──────────┬──────────┬────────┐   ┌───┬───┬───┬───┬───┬───┐
│ data ptr │  len     │  cap   │──▶│ 0 │ 1 │ 2 │ 3 │ 4 │ · │
└──────────┴──────────┴────────┘   └───┴───┴───┴───┴───┴───┘
   指向数组首元素    已用长度    可容纳长度（cap ≥ len）
```

**slice 不是数组，是"指向数组的描述符"**（ph03 的"slice 是描述符"在这里落到结构上）。`append` 在 `len < cap` 时直接写数组（零拷贝）；`len == cap` 时触发 **growslice**：分配新数组 → 拷贝旧元素 → 返回新描述符。扩容算法（go1.25.6 runtime/slice.go）：**cap < 256 时翻倍；cap ≥ 256 时 `newcap += (newcap + 3*256)/4`（约 1.25 倍）；再按分配器 size class 向上取整**。实测成长点序列（ex02 / 练习 sol-02 / 项目 slicegrow）：

| 元素类型 | 容量成长序列（cap 从 1 起） |
|---------|---------------------------|
| `[]int`（8 B） | 1 → 2 → 4 → 8 → 16 → 32 → 64 → 128 → 256 → 512 → **848** → 1280 → 1792 → 2560 |
| `[]byte`（1 B） | 1 → **8** → 16 → 32 → 64 → 128 → 256 → 512 → **896** → 1408 → 2048 |
| `[][32]byte`（32 B） | 1 → 2 → 4 → 8 → 16 → 32 → 64 → 128 → 256 → 512 → **852** → 1280 → 1792 → 2560 |

**读法**：512→848 是"512 + (512+768)/4 = 832，832×8=6656 字节 → size class 取整 6784 字节 → 848 个 int"；`[]byte` 首轮 1→8 是分配器最小块（8 B）直接抬升；同一规则、不同元素大小，取整结果不同。**工程含义**：频繁 append 大量元素的场景，`make([]T, 0, n)` 预分配（ph13 实测 allocs 12→1、快 3.2 倍）就是在"提前付一次扩容费"。**共享底层数组的别名陷阱**（ph03 内容，这里补机制）：两个 slice 指向同一数组时，一个 append 可能覆盖另一个的数据——因为描述符各自维护 len/cap。

### 4.2 map：从经典桶链到 Swiss map

**map 的两种内部实现**（版本敏感点）：Go 1.24 前是**经典桶链**（hmap 头 + bucket 数组，每个 bmap 装 8 个 key/value + overflow 指针，装载因子 6.5 触发扩容）；Go 1.24 起换成 **Swiss map**（`internal/runtime/maps`，8 槽 group + ctrl 字节，7/8 装载因子，SIMD 探测）。两者共享的**设计结论**（跨版本稳定）：

```text
经典桶链（Go < 1.24）              Swiss map（Go ≥ 1.24）
hmap ──▶ bucket[]                  map ──▶ group[]
        每个 bmap：8 键值 + 溢出指针         每个 group：8 槽 + ctrl 字节
        装载因子 6.5 触发扩容                装载因子 7/8 触发扩容
        hash 低 8 位选桶、高 8 位加速比对     SIMD 一次比 8 个 ctrl 字节
```

**并发写 map 的两种结局（实测，ex02）**：① 普通运行 `go run . -demo=race`：`fatal error: concurrent map writes` 直接崩溃进程——**map 内部在写入路径上自带并发写检测**（不是 -race 才报）；② 加 `-race` 运行：先报 `WARNING: DATA RACE`（读写栈都聚在 `main.go:99` 的 `m[k]=v`），随后同样 fatal。**教学点**：map 并发写是"双重保险"——race detector 报数据竞争（ph06/08 的工具），map 自己也会 fatal（运行时保护）；正确写法是 `sync.Mutex`（ex02 `-demo=safe` 实测 4 goroutine×1000 写正常）或 `sync.Map`。**遍历顺序随机**是设计决定（实测两次遍历输出不同）——禁止依赖顺序；`len`/`delete` 都是 O(1) 平摊；map 是引用类型（8 字节描述符，`unsafe.Sizeof(map[int]int{})=8`）。

### 4.3 interface：双字头与动态分派

```text
非空接口 iface（16 字节）         空接口 eface（16 字节）
┌─────────────┬─────────────┐   ┌─────────────┬─────────────┐
│   itab 指针  │   data 指针  │   │   type 指针  │   data 指针  │
└─────────────┴─────────────┘   └─────────────┴─────────────┘
  itab = 接口类型 + 具体类型           仅存具体类型
       + 函数指针表（方法跳转表）       （无方法可查）
```

**接口变量是"类型 + 值"的双字头**：调用接口方法 = 从 itab 的函数指针表里取目标函数 → 间接跳转（**动态分派**）；直接调用 = 编译期定址 → 直接跳转。**实测成本（ex04，-benchtime=5000000x，go1.25.6）**：直接调用 0.71 ns/op vs 接口分派 1.01 ns/op（约 1.4 倍）——这就是 roadmap 必会概念"interface 动态分发有成本"的数字；装箱（int → any）约 5.6 ns/op、7~8 B/op、**0 allocs/op**——64 位 int（8 B）恰等于指针宽，装箱时值直接内联进 eface 数据字、零堆分配（0 allocs 印证；这正是"小值装箱便宜"的机制）。**但注意去虚拟化（devirtualization）**：编译器在能证明具体类型时（单实现、内联后类型已知）会把接口调用变成直接调用——实测 `Shape` 变量只装 `Circle` 时，编译器输出 `devirtualizing s.Area to Circle`（`-gcflags=-m` 可见），接口调用被去虚拟化成直接调用（基准 `BenchmarkDevirtualized`：0.70 ns/op ≈ 直接调用 0.71，itab 间接跳转被消除）——"接口有成本"只在**类型运行时不确定**时成立（分派基准用 `shapes[i&1]` 交替类型来保证这一点）。

**类型断言与类型 switch**（运行时类型检查，实测）：comma-ok 断言失败给零值不 panic；单返回值断言失败直接 panic；类型 switch 按具体类型分派。**nil 陷阱三连（实测）**：① 零值接口 `== nil` 为 true（itab 与 data 都零）；② 装着 nil 指针的接口 `== nil` 为 false（itab 有类型）；③ 对②做断言 `ok=true` 但值是 nil 指针——判空必须同时看"接口本身"与"接口里的指针"两个层面。

### 4.4 channel：带锁的消息队列

**channel 的内部是一个 `hchan` 结构**（环状缓冲 + 发送/接收等待队列 + 互斥锁）：

```text
hchan
┌─────────┬─────────┬──────────┬──────────────┬──────────────┬──────┐
│  buf 指针│  qcount │  dataqsiz│    sendx     │    recvx     │ lock │
└─────────┴─────────┴──────────┴──────────────┴──────────────┴──────┘
   环状缓冲    当前元素     缓冲容量     下一个发送位     下一个接收位    互斥锁
   （无缓冲时 buf=nil，sendx/recvx 退化为"直接配对"）
```

**行为由缓冲决定**（实测，项目 chanx）：无缓冲 channel 是**同步点**——发送必须等到接收方就绪（实测：接收方先就绪时发送 292ns 立即完成）；缓冲 channel 是**解耦**——容量 3 吸收 3 次发送不阻塞；**关闭是广播**——关闭后 range 自动结束、再读得零值 + ok=false；**select 在就绪分支间随机**（实测 100 次选择 a=60/b=40，两边都被选中）；**channel 内部自带同步**（互斥锁保护缓冲）——1000 goroutine 并发发送计数精确、-race 零报告，与 map 并发写 fatal 形成对照。**工程含义**：channel 是"带同步语义的消息队列"（ph06 用法 + 本阶段机制）；关闭由发送方负责（ph06 必会概念）；只发不收或只收不发会阻塞（ph06 的泄漏场景在机制上是"发送队列挂起"）。

**channel 还是 Mutex（机制层面的分工）**：两者的底层都有锁（channel 的 hchan 自带 lock，Mutex 就是锁本身），差别在**语义载体**：

| 场景 | 用 channel | 用 Mutex |
|------|-----------|---------|
| 传递数据 / 任务 | ✅ 数据在"发送→接收"中易主 | 别扭（要自己搬数据 + 加锁） |
| 信号与协作（通知、汇合、关闭广播） | ✅ 语义天然 | 勉强 |
| 保护共享状态（计数器、配置、缓存） | 别扭（把状态当消息传来传去） | ✅ 直接加锁访问 |

判断口诀：**要"把东西送过去"用 channel，要"一起用同一个东西"用 Mutex**（配合 4.7 的 happens-before 表理解：channel 收发与锁的临界区都是同步点，只是承载的语义不同）。

### 4.5 GMP：goroutine 的 M:N 调度

```text
G（goroutine）    M（OS 线程）       P（processor，逻辑处理器）
栈 + 执行状态      真正跑代码的线程    本地 runq + 可运行的 G 池
百万级，便宜       数十个，昂贵        GOMAXPROCS 个，绑定 M
                 ┌─── runq ───┐
G1 ──▶ 入队 ──▶  │ G5 G6 G7   │ ◀── P ──▶ M ──▶ 执行 G1
                 └────────────┘
调度循环：M 绑 P → 从 P 的 runq 取 G → 执行 → G 阻塞/让出/结束 → 取下一个
G 阻塞（channel/锁/IO）时 M 不阻塞：P 换绑其他 M，阻塞的 G 醒来后重新入队
```

**GMP 是"用户态线程（G）在 OS 线程（M）上复用"的 M:N 调度器**——G 由 Go 运行时调度（协作式 + 抢占式混合），M 由操作系统调度。关键数字（实测，项目 gmp）：本机 `GOMAXPROCS=14 = NumCPU=14`（P 数默认等于核数）；**P 是"谁能跑 Go 代码"的许可**（G 必须绑定 P 才能执行）；**M 数运行时内部管理、外部不可见**（阻塞的系统调用会让运行时补新 M）。**调度点**：goroutine 在 channel 收发、锁等待、`runtime.Gosched()`、系统调用、GC 等位置让出 P（协作）；Go 1.14+ 还支持基于信号的抢占（长 CPU 任务也会被强拆）。**实测**：8 个 goroutine 各自 `Gosched()` 让出后汇合，`runtime.NumGoroutine()` 回到初始值（无泄漏）。**工程含义**：`GOMAXPROCS` 决定并行度（ph06 的 worker pool 用 `runtime.NumCPU()` 开 worker 数的依据）；goroutine 便宜但**不是免费的**（ph13 的泄漏场景=G 挂在 channel 队列上）。

### 4.6 GC：堆增长触发，不是定时器

```text
程序分配堆对象 ──▶ 堆大小增长 ──▶ 达到触发阈值（GOGC=100：堆翻倍）──▶ 触发 GC
──▶ 三色标记（并发，白色→灰色→黑色）──▶ 清扫（并发）──▶ 堆回落，等下次增长
写屏障：标记期间新写入的指针也标黑，保证"并发下不漏对象"
```

**GC 是"堆增长到阈值就触发"**（ph13 的因果链在这里补上机制）：三色标记 + 混合写屏障让标记阶段与程序并发执行（Go 1.5 起），暂停只发生在"写屏障切换"的瞬间（微秒级）。**实测（项目 gcstats）**：同一份 200 MiB 分配压力下，`GOGC=100`（默认）触发 6 次 GC、累计暂停 57µs；`GOGC=-1`（关闭自动 GC）触发 0 次——GC 次数完全由 GOGC 与分配量决定。**工程含义**：调大 GOGC 减少 GC 频率但抬高堆峰值（内存换 CPU）；调小降低内存占用但增加 GC 开销；ph13 的"减少分配"（allocs/op 下降）在这里的机制意义是**降低堆增长速度 → 拉长两次 GC 的间隔**。

### 4.7 Go 内存模型：happens-before 与数据竞争

**Go 内存模型回答"一个 goroutine 对变量的写，什么时候对另一个 goroutine 的读可见"**——不是"内存屏障在哪"，而是"哪些同步操作建立了顺序关系"（happens-before 偏序）。本阶段不必背全部规则，掌握**四条同步操作的 happens-before 关系**就够覆盖 99% 的并发正确性判断：

| 同步操作 | happens-before 关系 | 工程含义 |
|---------|--------------------|---------|
| `go f()` 启动 goroutine | go 语句 happens-before f 内所有操作 | 启动前的写入，f 一定能看到 |
| channel 发送/接收 | 发送 happens-before 对应接收 | "通过 channel 传数据"是同步，不只是传值 |
| `Mutex.Unlock` / `Lock` | Unlock happens-before 下一次 Lock | 临界区内的写入，后续拿锁者一定看到 |
| `WaitGroup.Done` / `Wait` | Done happens-before Wait 返回 | 汇合即同步点（项目 gmp 实验的计数回落依赖它） |

**数据竞争的定义**：两个 goroutine 并发访问同一变量、至少一个是写、且两者之间**没有** happens-before 关系——这就是 `-race` 检测的东西（ph06/08 的工具、本阶段 ex02 的 map 并发写实测正是数据竞争 + 运行时 fatal 双保险）。**注意**：内存模型是"正确性契约"，GMP（4.5）是"调度机制"，GC（4.6）是"内存回收"——三者独立：happens-before 关系不依赖调度器实现，所以"内存模型保证"跨 Go 版本稳定，而"调度行为"（谁先跑）从不被保证。这也解释了为什么**禁止依赖 goroutine 执行顺序**（ph06 必会概念）：顺序不是调度器承诺的一部分。

## 5. 使用场景

| 场景 | 用什么 | 对应知识点 |
|------|--------|-----------|
| 同一算法服务多种具体类型（工具函数、集合操作） | 泛型（编译期实例化） | 3.1 |
| 类型在编译期未知（配置文件、通用序列化、插件） | reflect（启动期一次性使用） | 3.3 |
| 结构体内存布局优化 / 与 C 共享内存 / 高性能序列化 | unsafe（先看 Sizeof/Offsetof 再动手） | 3.4 |
| 复用现成 C 库（加密、图像、系统库） | cgo（薄封装，只进不出） | 3.5 |
| 并发容器 / 协程间协作 | channel（同步语义自带）、sync.Mutex（保护共享状态） | 4.4 / 4.2 |
| 理解"为什么慢"的机制层 | GMP（调度）、GC（分配触发） | 4.5 / 4.6 |

**不适合**此阶段的事项：

- **性能剖析方法本身**（benchmark/pprof/trace/逃逸分析怎么用）：属 ph13——本阶段讲机制，ph13 讲工具
- **PGO（用生产 profile 指导编译）**：属 ph16——本阶段的 GMP/GC 认知是它的背景，但流程属 ph16
- **并发模型设计**（worker pool、fan-in/out、context 取消怎么组织）：属 ph06——本阶段只讲机制，设计用法在 ph06
- **Go 版本演进与工具链**（go env/install/work/toolchain）：属 ph15——本阶段的"版本敏感点"正是 ph15 的主题入口

**「现象 → 机制」对照图（学完自检用）**——把此前各阶段遇到的"现象"在本阶段找到"机制"：

| 你之前见到的现象 | 本阶段的机制解释 | 章节 |
|-----------------|----------------|------|
| append 之后 slice 可能变慢/换底层 | growslice：<256 翻倍、≥256 约 1.25 倍 + size class 取整（实测 512→848） | 4.1 |
| 两个 slice 互相覆盖数据 | 描述符各自维护 len/cap，共享同一底层数组 | 4.1 |
| map 并发写直接崩进程 | map 内部写入路径自带并发写检测 → fatal | 4.2 |
| map 遍历顺序每次不同 | 设计决定（随机起点），禁止依赖顺序 | 4.2 |
| defer 的执行顺序"反直觉" | LIFO 栈 + 开放编码（Go 1.14+） | 3.2 |
| 接口调用比直接调用慢一点 | itab 间接跳转（实测约 1.4 倍）；去虚拟化可消除 | 4.3 |
| goroutine 泄漏后数量只增不减 | G 挂在 channel 的收发队列上（关闭=广播可唤醒） | 4.4 |
| `-race` 能抓到并发 bug | 数据竞争 = 无 happens-before 的并发读写（4.7 四张同步表） | 4.7 |
| 高分配程序 GC 频繁 | GC 是堆增长触发（GOGC），不是定时器 | 4.6 |

对照这张表过一遍：**每条都能"由现象说出机制"，本阶段才算吸收**——这正是"从'会写 Go'到'懂 Go'"的验收标准。

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：Go 的泛型 = 编译期实例化（类似 C++ 模板的"每种类型一份代码"、Rust 泛型的单态化），但约束系统比 C++ 概念简洁、比 Rust trait 弱（没有关联类型/泛型方法）；Go 的接口 = 运行时多态（类似 Java 接口，但**结构性实现**而非声明式 implements），itab 对应 Java 的 vtable；Go 的 unsafe 类似 C 的指针自由（但要自己守规矩，checkptr 是"安全带"）；cgo 对应 C 语言生态里的 FFI（Python ctypes、Java JNI、Rust extern "C"），Go 的差异化是 cgo 与工具链集成（交叉编译、-race 覆盖 C 侧内存）。**Tenet 语言启示**：泛型做编译期多态、接口做运行时多态，两种多态的分工与成本透明，是 Go 留给后发语言的明确设计样本。

## 6. 代码示例

> 以下示例均为完整可运行 Go module，位于 [`examples/`](./examples/) 目录（每个示例一个子目录，先进入对应目录再运行）。验证环境：go1.25.6（darwin/arm64，Apple M4 Pro），零第三方依赖；cgo 示例另需本机 `cc`（clang 21.0.0）与 `CGO_ENABLED=1`。六个示例均通过 `go vet ./...`、`go test ./...`、`go test -race ./...`；实测数字见 examples/README.md（下表"实测"列为本环境输出节选）。

| 示例 | 一句话说明 | 实测（节选） |
|------|-----------|-------------|
| ex01-generics | 类型集约束、comparable、方法集约束、类型推断与实例化 | `Sum([]Celsius{10,20,30})=60`（~int 覆盖自定义类型） |
| ex02-slice-map-internals | slice 扩容步长实测 + map 迭代随机 + 并发写两种结局 | int 扩容 512→848；`-demo=race` → `fatal error: concurrent map writes` |
| ex03-defer-panic | defer 五语义 + panic/recover 铁律 + panic(nil) | 顺序 `[body defer3 defer2 defer1]`；named-return 50；panic(nil) recover 非 nil |
| ex04-interface-dispatch | 动态分派、断言/switch、nil 陷阱 + 分派成本基准（含去虚拟化对照） | 直接 0.71 ns vs 接口 1.01 ns（约 1.4 倍）；去虚拟化 0.70 ns ≈ 直接调用；装箱 ~5.6 ns + 7~8 B、0 allocs |
| ex05-reflection-unsafe | 反射配置加载器（JSON/ENV）+ unsafe 布局 + uintptr 陷阱 | `Point` Sizeof=24（padding）；checkptr 拦截 `fatal error` |
| ex06-cgo | 写 C 库 → cc 编静态库 → cgo 链接 → Go 调用 | `addvec: [11 22 33 44]`；`sin(pi/2)=1.0` |

### 示例 1：泛型（ex01-generics）

```go
// examples/ex01-generics/main.go —— 类型集约束（节选）
// Number 类型集：~ 表示底层类型（覆盖自定义类型），| 是并集
type Number interface {
	~int | ~int32 | ~int64 | ~float32 | ~float64
}

func Sum[T Number](vs []T) T {
	var s T
	for _, v := range vs {
		s += v
	}
	return s
}
```

运行：`cd examples/ex01-generics && go test -v ./... && go run .`。**教学点**：约束决定函数体内可用的操作；`~int` 让 `type Celsius int` 也能求和——类型集是"按底层类型匹配"而非"按具名类型匹配"。

### 示例 2：slice 扩容与 map 底层（ex02-slice-map-internals）

```go
// examples/ex02-slice-map-internals/main.go —— 扩容序列观察器（节选）
// IntGrowth 记录 []int 从 cap=1 起反复 append 的容量成长点
func IntGrowth(n int) []int {
	s := make([]int, 0, 1)
	seq := []int{cap(s)}
	for i := 0; i < n; i++ {
		s = append(s, i)
		if c := cap(s); c != seq[len(seq)-1] {
			seq = append(seq, c)
		}
	}
	return seq
}
```

运行：`go run .` 打印三元素扩容序列；**`go run . -demo=race` 故意出错**（map 并发写 → fatal，需单独运行）；`go run -race . -demo=race` 看 DATA RACE + fatal；`go run . -demo=safe` 看加锁对照。**教学点**：扩容规则（<256 翻倍、≥256 约 1.25 倍 + size class 取整）与 map 并发写的双重保险（race detector + 内部 fatal）。

### 示例 3：defer / panic-recover（ex03-defer-panic）

```go
// examples/ex03-defer-panic/main.go —— 命名返回值被 defer 修改（节选）
func namedReturn() (x int) {
	x = 1
	defer func() { x = x * 10 }() // return 5 后、返回前执行：5 → 50
	return 5
}
```

运行：`go test -v ./...`（九条断言覆盖全部语义）；`go run .` 打印实验报告。**教学点**：defer 的执行顺序与"返回值先算好、defer 还能改"的交互；recover 只在 defer 内有效；panic(nil) 在 Go 1.21+ 的语义修正。

### 示例 4：interface 动态分派（ex04-interface-dispatch）

```go
// examples/ex04-interface-dispatch/bench_test.go —— 分派成本基准（节选）
// shapes[i&1] 让具体类型在 circle/rect 间交替：编译器无法去虚拟化，测的是真实分派
func BenchmarkIfaceDispatch(b *testing.B) {
	shapes := []Shape{Circle{R: 2}, Rect{W: 2, H: 3}}
	for i := 0; i < b.N; i++ {
		sink = shapes[i&1].Area()
	}
}
```

运行：`go test -run='^$' -bench=. -benchmem -benchtime=5000000x`。**教学点**：接口分派 ≈ 直接调用 1.4 倍（itab 间接跳转，实测 1.01 vs 0.71 ns）；去虚拟化让"单实现接口"≈直接调用（实测 0.70 ns，基准 `BenchmarkDevirtualized`，`-gcflags=-m` 可见 `devirtualizing s.Area to Circle`）——"接口有成本"只在类型运行时不确定时成立。

### 示例 5：reflect 配置加载器 + unsafe（ex05-reflection-unsafe）

```go
// examples/ex05-reflection-unsafe/main.go —— 按 Kind 转换（节选）
case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
	var n int64
	switch x := v.(type) {
	case float64:
		// JSON 数字是 float64：先查值域再转换（直接 int64(x) 溢出是静默的）
		if x > float64(math.MaxInt64) || x < float64(math.MinInt64) {
			return fmt.Errorf("%v 超出 int64 范围", x)
		}
		n = int64(x)
	...
```

运行：`go test -v ./...`；`go run .`；uintptr 陷阱演示用 `go run -tags=checkptrdemo .`（普通构建，能跑出 42）与 `go run -tags=checkptrdemo -gcflags=all=-d=checkptr=2 .`（checkptr 拦截，预期 fatal）。**教学点**：反射的 CanSet/Kind/SetXxx 三件套、float64→int64 静默溢出、uintptr 不参与 GC 跟踪、checkptr 是运行时安全带。

### 示例 6：cgo（ex06-cgo）

```go
// examples/ex06-cgo/main.go —— cgo preamble 与调用（节选）
/*
#cgo CFLAGS: -I./c_lib               // 头文件目录：c_lib/addvec.h（相对包目录，可移植）
#cgo LDFLAGS: /tmp/libaddvec.a -lm   // 链接编译好的静态库 + libm
#include <addvec.h>
extern double sin(double);
*/
import "C"

func addVec(a, b []int32) []int32 {
	out := make([]int32, len(a))
	C.addvec((*C.int)(unsafe.Pointer(&a[0])), (*C.int)(unsafe.Pointer(&b[0])),
		(*C.int)(unsafe.Pointer(&out[0])), C.size_t(len(a)))
	return out
}
```

运行（先编译 C 库，产物在 /tmp）：`cc -c -o /tmp/addvec.o c_lib/addvec.c && ar rcs /tmp/libaddvec.a /tmp/addvec.o`，再 `CGO_ENABLED=1 go test -v ./...`、`CGO_ENABLED=1 go run .`。**教学点**：写 C 库 → cc 编静态库 → cgo 链接 → Go 调用的完整闭环；preamble/类型映射/unsafe.Pointer 桥接三要点。

## 7. 总结

### 关键要点

1. **泛型是编译期多态**（必会概念）：类型集约束（`~`/`|`/`comparable`/方法集）决定函数体内可用的操作；实例化在编译期完成、运行时零间接跳转——与接口的"运行时多态"分工明确
2. **slice 扩容有明确步长**：<256 翻倍、≥256 约 1.25 倍 + size class 取整（实测 int：512→848）；预分配（`make cap`）就是提前付一次扩容费
3. **map 并发写会 fatal**（必会概念）：map 内部自带并发写检测（`fatal error: concurrent map writes`）+ race detector 双重保险；Go 1.24+ 换 Swiss map 实现，但"并发不安全、遍历随机"的结论跨版本不变
4. **interface 动态分派有成本**（必会概念）：itab 间接跳转 ≈ 直接调用 1.4 倍（实测 1.01 vs 0.71 ns）；去虚拟化让单实现接口 ≈ 直接调用（实测 0.70 ns）；nil 接口 ≠ 装着 nil 指针的接口
5. **defer 五语义 + panic/recover 铁律**：LIFO、参数即求值、闭包看最终值、defer 可改命名返回值；recover 只在 defer 内有效；Go 1.21+ panic(nil) recover 非 nil；panic 只终止当前 goroutine
6. **channel 是带锁的消息队列**：无缓冲=同步点、缓冲=解耦、关闭=广播、select 随机、内部自带同步（与 map 并发写 fatal 对照）
7. **GMP 决定调度行为**（必会概念）：P 数=GOMAXPROCS=核数（实测 14），G 在 channel/锁/Gosched/系统调用处让出 P；M 外部不可见
8. **GC 是堆增长触发**：GOGC 决定阈值（实测 GOGC=100 压力下 6 次 GC、-1 时 0 次）；减少分配的直接收益是拉长 GC 间隔
9. **内存模型是并发正确性契约**：四条同步操作（go 启动 / channel 收发 / mutex 解锁加锁 / WaitGroup 汇合）建立 happens-before；数据竞争 = 无 happens-before 的并发读写——所以禁止依赖 goroutine 执行顺序
10. **reflect/unsafe/cgo 是高级工具、业务代码慎用**（必会概念）：反射适合启动期一次性；unsafe 的 uintptr 陷阱要 checkptr 拦截；cgo 跨边界有真实成本、C 侧无边界检查

### 阶段验收清单

- [ ] 能解释 GMP/GC 大致机制：说清 G/M/P 的关系与调度点、GC 的触发条件与 GOGC 的作用（项目 gmp/gc 实验复现）
- [ ] 能谨慎使用泛型和反射：说清类型集约束与"约束决定操作"、反射的 CanSet/Kind/SetXxx 与适用边界（练习 1/4）
- [ ] 能说出 slice 扩容步长与 map 并发写结局：实测序列（<256 翻倍、≥256 约 1.25 倍）与 `-demo=race` 的 fatal 输出（示例 2）
- [ ] 能解释 interface 分派成本与 nil 陷阱：itab 间接跳转、去虚拟化、nil 接口 vs nil 指针（示例 4）
- [ ] 能实测 defer/panic 语义：LIFO、参数求值、recover 范围、panic(nil)（示例 3 / 练习 3）
- [ ] 能独立完成 cgo 闭环：写 C 库 → cc 编静态库 → cgo 调用并跑通测试（示例 6）
- [ ] 能完成项目验收标准：rtlab 五个实验全部可复现输出、`go test -race ./...` 通过

### 跨语言对比

- Go 泛型（编译期实例化、约束=类型集）vs C++ 模板（编译期实例化、约束=概念）vs Rust 泛型（单态化、约束=trait）——Go 的约束系统最简，代价是表达能力（无关联类型/泛型方法）
- Go 接口（结构性实现、itab 运行时分派）vs Java 接口（声明式实现、vtable 分派）——"鸭子类型"让 Go 接口天然轻量，代价是编译期接口匹配检查更弱
- Go unsafe vs C 指针——Go 的 unsafe 是"带安全带的 C"（checkptr/GC 规则），C 是"裸的自由"
- Go cgo vs Java JNI / Python ctypes / Rust FFI——Go 的差异化是 cgo 与工具链集成（-race 覆盖、交叉编译）
- （为 analysis/ 与 Tenet 合成积累素材）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 4 题后继续。四题与 roadmap §14 对齐（roadmap 练习列表已按本目录同步）：练习 1 ↔ 推荐项目「泛型工具库」、练习 2 ↔「观察 slice 扩容」、练习 3 ↔ 学习内容「defer、panic/recover 原理」、练习 4 ↔「写反射版配置加载器」；roadmap 练习「用 cgo 调 C 库」由示例 6 覆盖，「用 pprof 分析高 CPU」属 ph13。

1. **泛型工具库**（★★）：Map/Filter/Reduce + 类型集约束（参考实现实测：Celsius 等自定义类型直接可用）
2. **观察 slice 扩容**（★★）：扩容序列观察器 + 结构性规则测试（参考实现实测：int 512→848、byte 512→896）
3. **defer / panic-recover 语义实验**（★★）：六语义断言 + SafeCall 模式（参考实现实测：九条断言全绿）
4. **反射版配置加载器**（★★★）：JSON 默认值 + env 覆盖 + 类型转换与错误路径（参考实现实测：九条测试覆盖）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**Go runtime 机制实验台（rtlab）**（roadmap 推荐项目「Go runtime 机制实验笔记」）——五个实验包把 slice 扩容、defer/panic 语义、GMP 调度、GC 触发、channel 语义做成可复现报告，`go run ./cmd/rtlab -exp all` 一键跑完。**实测**：扩容序列三元素对比、defer 七语义、GOMAXPROCS=14、GOGC=100 下 6 次 GC vs -1 下 0 次、select 随机 60/40。roadmap 另一个推荐项目「泛型工具库」已由练习 1 覆盖。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部 4 题并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（五实验可复现输出、`go test -race ./...` 通过）

### 下一阶段

[Go 版本与工具链阶段](../ph15-version-toolchain/15-version-toolchain.md)（ph15，roadmap 第 15 节）— 本阶段反复强调的"版本敏感点"（Go 1.24 的 Swiss map、Go 1.21 的 panic(nil)、扩容取整随架构变化）正是 ph15"工具链版本统一与依赖升级"的动机来源；届时本阶段的机制认知会落到"如何在不同 Go 版本间稳定复现构建与行为"——go env / go install / go work 多模块 workspace、toolchain 指令、模块版本与语义化版本策略。当前已建目录至 ph21（Go 路线末阶段，已收官），roadmap 见 [`languages/go/go.md`](../go.md)。

---

*本文全部"已验证"声明（go1.25.6 实测：示例 1~6、练习 1~4、项目五个实验的全部命令与数字）均属实；cgo 示例实测环境含本机 cc（Apple clang 21.0.0）、CGO_ENABLED=1；`go tool trace` 浏览器 UI 等图形查看器未在本阶段涉及；不虚构验证。*
