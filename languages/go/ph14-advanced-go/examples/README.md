# ph14 高级 Go 示例

> 六个示例覆盖本阶段全部知识点：Generics 类型集（ex01）→ slice 扩容与 map 底层（ex02）→ defer/panic-recover 语义（ex03）→ interface 动态分派（ex04）→ reflect 配置加载器 + unsafe 布局（ex05）→ cgo 调 C 库（ex06）。全部为完整可运行 Go module，零第三方依赖，在 go1.25.6（darwin/arm64，Apple M4 Pro）实测通过（`go vet`、`go test`、`go test -race` 全绿；cgo 需 `CGO_ENABLED=1` + `cc`）。

| 示例 | 一句话说明 | 运行命令（进入各自子目录） |
|------|-----------|--------------------------|
| ex01-generics | 类型集约束（`~int \| ~float64`）、`comparable`、方法集约束、类型推断与显式实例化 | `go test -v ./...`；`go run .` |
| ex02-slice-map-internals | slice 扩容步长实测（<256 翻倍、≥256 ~1.25 + size class 取整）；map 迭代随机；并发写 map 的两种结局 | `go test -v ./...`；`go run .`；`go run . -demo=race`（预期崩溃）；`go run -race . -demo=race`；`go run . -demo=safe` |
| ex03-defer-panic | defer LIFO、参数求值时机、闭包引用、命名返回值被 defer 修改、recover 只在 defer 中生效、嵌套 panic 覆盖、panic(nil) | `go test -v ./...`；`go run .` |
| ex04-interface-dispatch | 动态分派、类型断言/类型 switch、空接口装箱、nil 陷阱三连；分派成本 benchmark | `go test -v ./...`；`go run .`；`go test -run='^$' -bench=. -benchmem -benchtime=5000000x` |
| ex05-reflection-unsafe | reflect 反射配置加载器（JSON/ENV 双来源）；unsafe Sizeof/Alignof/Offsetof 布局；uintptr 陷阱 + checkptr 拦截 | `go test -v ./...`；`go run .`；`go run -tags=checkptrdemo .`；`go run -tags=checkptrdemo -gcflags=all=-d=checkptr=2 .`（预期 fatal） |
| ex06-cgo | 写 C 库 → cc 编译静态库 → cgo 链接 → Go 调用；libm sin | 先 `cc -c -o /tmp/addvec.o c_lib/addvec.c && ar rcs /tmp/libaddvec.a /tmp/addvec.o`，再 `CGO_ENABLED=1 go test -v ./...`、`CGO_ENABLED=1 go run .` |

## 实测记录（go1.25.6 darwin/arm64，Apple M4 Pro，2026-09-01）

数字随机器与 Go 版本波动，以本机重跑为准；本表全部为本环境实测输出。

### ex01：Generics 实测输出

```
Sum([]int): 6
Sum([]float64): 4
Sum([]Celsius): 60        ← 类型集 ~int 覆盖自定义类型 Celsius
Sum[int] 显式实例化: 9
Contains(string): true     ← comparable 约束
Format(Device): device-7   ← 方法集约束
Box[string].Get(): hello
Pair: {key 42}
```

**结论**：三类约束（类型集 / comparable / 方法集）全部生效；泛型在编译期完成类型实例化，运行时零额外分派成本（对比 ex04 的分派基准——泛型不引入 itab 间接跳转）。

### ex02：slice 扩容步长实测（cap 从 1 起反复 append 的成长点）

| 元素类型 | 容量成长序列 |
|---------|-------------|
| `[]int`（8 B） | 1 → 2 → 4 → 8 → 16 → 32 → 64 → 128 → 256 → 512 → **848** → 1280 → 1792 → 2560 |
| `[]byte`（1 B） | 1 → **8** → 16 → 32 → 64 → 128 → 256 → 512 → **896** → 1408 → 2048 |
| `[][32]byte`（32 B） | 1 → 2 → 4 → 8 → 16 → 32 → 64 → 128 → 256 → 512 → **852** → 1280 → 1792 → 2560 |

**结论**：① cap < 256 时翻倍（1→2→4…→256）；② cap ≥ 256 时按 `newcap += (newcap+3*256)/4`（约 1.25 倍）增长：512 → 832，再按分配器 size class 向上取整 → int 得 848（832×8=6656 B → 6784 B 块）、byte 得 896、[32]byte 得 852；③ 小元素首次扩容会被 size class 直接抬升（`[]byte` 1→8，分配器最小块 8 B）；④ 精确数字依赖架构与 size class，规则（翻倍 → 1.25 倍 + 取整）跨机器稳定——测试只断言规则不断言具体数。

**map 并发写实测（`go run . -demo=race`，无 -race）**：

```
fatal error: concurrent map writes
main.raceWrite(...)
	.../ex02-slice-map-internals/main.go:99
```

**`go run -race . -demo=race`（加 -race）**：先输出 `WARNING: DATA RACE`（Write at … by goroutine 8 / Previous write … by goroutine 7，栈都在 `main.go:99` 的 `m[g*1000+i] = i`），随后同样 `fatal error: concurrent map writes`。

**结论**：map 并发写是「双重保险」——race detector 报数据竞争，map 内部自己也检测并发写并直接 fatal 崩溃进程（`fatal error: concurrent map writes`，不靠 -race 也能触发）。go1.24+ 的 map 是 Swiss map 实现（`internal/runtime/maps`，8 槽 group + ctrl 字节、7/8 装载因子），fatal 检测在 `map.go` 的写入路径上。对照 `go run . -demo=safe`：sync.Mutex 保护后 4 goroutine × 1000 写正常完成（map size 4000）。

**map 遍历顺序实测**：同一 map 两次遍历输出不同（`[a b c d e]` vs `[d e a b c]`）——Go 刻意随机化遍历起点，禁止依赖遍历顺序。

### ex03：defer / panic-recover 语义实测（go run . 输出节选）

```
== 1. defer LIFO ==
  执行顺序: [body defer3 defer2 defer1]      ← 逆序执行
== 2. defer 参数求值时机 ==
  body 中 n=100，defer 捕获的 n=1             ← 参数在 defer 语句处求值
== 3. defer 闭包引用变量 ==
  闭包捕获的 n: 100                           ← 闭包引用看最终值（与②相反）
== 4. defer 修改命名返回值 ==
  namedReturn: 50                             ← return 5 后 defer 乘 10
== 6. recover 不在 defer 中 = 无效 ==
  调用方 defer 捕获到: boom2                   ← panic 冒泡给调用方
== 7. 嵌套 panic ==
  nestedPanic 捕获: inner                      ← 内层 panic 覆盖外层
== 8. panic(nil) ==
  recover()==nil? false, 值: &runtime.PanicNilError{...}   ← Go 1.21+ 起非 nil
```

**结论**：defer 的三大时机语义（LIFO、参数即求值、命名返回值可改）+ recover 的两条铁律（只在 defer 中有效、panic(nil) 在 Go 1.21+ 返回非 nil 的 `*runtime.PanicNilError`）+ 嵌套 panic 覆盖规则，全部实测确认。另注意「defer 里 append 的坑」：defer 修改返回值必须用命名返回值，否则返回的 slice 头在 defer 执行前就拷贝走了。

### ex04：interface 动态分派与成本实测（-benchtime=5000000x，go1.25.6，3 轮稳定值）

| 基准 | ns/op | B/op | allocs/op |
|------|-------|------|-----------|
| BenchmarkDirectValue（直接调用，noinline） | 0.71 | 0 | 0 |
| BenchmarkIfaceDispatch（接口分派，类型运行时交替） | 1.01 | 0 | 0 |
| BenchmarkDevirtualized（单实现接口调用，去虚拟化） | 0.70 | 0 | 0 |
| BenchmarkBoxing（int 装箱进 any） | 5.6 | 7~8 | 0 |

**结论**：接口分派约 1.4 倍于直接调用（1.01 vs 0.71 ns，itab 间接跳转 vs 编译期定址）。**去虚拟化（devirtualization）实测**：接口变量只装 `Circle` 一种类型时，编译器把接口调用改写为直接调用（`-gcflags=-m` 输出 `devirtualizing s.Area to Circle`），基准 `BenchmarkDevirtualized` 0.70 ns/op ≈ 直接调用 0.71——itab 间接跳转被消除，"接口有成本"只在类型运行时不确定时成立（分派基准刻意用 `shapes[i&1]` 让类型交替）。**装箱实测**：约 5.6 ns/op、7~8 B/op、**0 allocs/op**——64 位 int（8 B）恰等于指针宽，装箱时值直接内联进 eface 数据字、零堆分配（0 allocs/op 印证：若每迭代都堆分配，allocs/op 必为 1）——"小值装箱便宜"。**nil 陷阱三连实测**：零值接口 `== nil` 为 true；装着 nil 指针的接口 `== nil` 为 false；对后者做类型断言 ok=true 但值是 nil 指针——判空必须 `if x == nil` 与「接口本身 nil」分开判断。

### ex05：reflect 加载器 + unsafe 布局实测

```
== 1. JSON 来源 ==
  err=<nil> cfg={Port:8080 Host:0.0.0.0 Debug:true TimeoutMS:1.5 Tags:[]}
== 2. 环境变量来源 ==
  err=<nil> cfg={Port:9090 Host:127.0.0.1 Debug:false TimeoutMS:0 Tags:[]}
== 3. 类型不匹配 ==
  err=字段 Port (cfg:"port"): strconv.ParseInt: parsing "not-a-number": invalid syntax
== 4. unsafe 内存布局 ==
  Point: Sizeof=24 Alignof=8 | X@0 Y@8 Z@16    ← 4+8+4=16 的数据因对齐变 24（padding）
  Mixed: Sizeof=40 Alignof=8 | A@0 B@8 C@16 D@24
  引用类型描述符: string=16 slice=24 map=8 chan=8 func=8
```

**结论**：反射加载器把 JSON 数字（float64）与 ENV 字符串（string）统一按目标字段 Kind 转换——int 的 float64 来源必须先查值域再转（直接 `int64(x)` 在溢出时是静默错误，OverflowInt 事后查不出来）。unsafe 布局：Point 的 padding 让 Sizeof=24（数据 16 + 空 8）；string/slice 是 16/24 字节的描述符头，map/chan/func 是 8 字节单指针。

**uintptr 陷阱实测**（`-tags=checkptrdemo`）：

```
# 普通构建：两个路径都打印 42（错误没暴露）
go run -tags=checkptrdemo .
  via unsafe.Pointer: 42
  via uintptr: 42
# 加 checkptr 检测：readViaUintptr 当场 fatal
go run -tags=checkptrdemo -gcflags=all=-d=checkptr=2 .
fatal error: checkptr: pointer arithmetic result points to invalid allocation
```

**结论**：`uintptr` 是整数，GC 不跟踪——把 `unsafe.Pointer` 转成 `uintptr` 保存再转回，等于亲手制造悬空指针；`-gcflags=all=-d=checkptr=2`（实验性检测）能当场抓住这种转换。该演示代码本身是 go vet `unsafeptr` 检查禁止的写法，属教学性故意违规，用 build tag 隔离保证默认 vet 全绿。

### ex06：cgo 实测

```
addvec: [11 22 33 44]          ← 自定义 C 库：向量加法
add(7, 8): 15                  ← C 标量函数
sin(pi/2) via libm: 1.0（对照 Go math.Sin: 1.0）   ← libm 数学库
```

**结论**：完整闭环（写 C 库 → `cc` 编静态库 → cgo 链接 → Go 调用）在本机（clang 21.0.0，CGO_ENABLED=1）跑通；`go test -race` 全绿。cgo 三要点：preamble 里 `#cgo CFLAGS/LDFLAGS` 指定头文件与链接库；`C.int`/`C.size_t` 类型映射；切片 → C 指针用 `unsafe.Pointer(&s[0])` 桥接——C 侧不做边界检查，越界风险自负（这就是 cgo 让 Go 失去内存安全的入口）。

## 验证说明

- 全部示例 `go vet ./...`、`go test ./...`、`go test -race ./...` 通过（ex02/ex04/ex06 含并发/基准测试，-race 零数据竞争）；ex06 需先编译 C 库（命令见上表），ex05 的 checkptr demo 是预期崩溃的故意出错示例，不在默认测试路径里
- 本表实测环境：go1.25.6 darwin/arm64，Apple M4 Pro，cc = Apple clang 21.0.0；机器/版本差异会导致精确数字波动（尤其 ex02 扩容取整与 ex04 基准），趋势稳定
- ex02 的 `-demo=race` 与 ex05 的 checkptr demo 是"故意出错"演示（L1 教学性覆盖），运行前请读对应文件头注释
