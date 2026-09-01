# ph14 高级 Go 练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★）。四题与 roadmap ph14 对齐：练习 2 ↔ 「观察 slice 扩容」、练习 4 ↔ 「写反射版配置加载器」、练习 1 ↔ roadmap 推荐项目「泛型工具库」、练习 3 ↔ 学习内容「defer、panic/recover 原理」；roadmap 练习里的「用 pprof 分析高 CPU」已由 ph13 性能优化阶段覆盖，此处不重复。
> 全部参考实现已在 go1.25.6（darwin/arm64）验证（`go test`、`go vet`、`go test -race` 全绿），零第三方依赖，进入各自子目录运行。

## 练习 1：泛型工具库（★★）

**目标**：用 Go 泛型实现 `Map` / `Filter` / `Reduce` 三个高阶函数，让同一份代码同时服务 `int`、`float64` 与自定义数值类型，体会「类型集约束」与「编译期实例化」。

**要求**：
- `Map[T, U any](vs []T, f func(T) U) []U`：逐元素变换
- `Filter[T any](vs []T, f func(T) bool) []T`：按谓词保留
- `Reduce[T Number](vs []T, acc T, f func(T, T) T) T`：折叠——约束用类型集 `~int | ~int32 | ~int64 | ~float32 | ~float64`（不能是 `any`：`any` 没法做加法）
- 额外实现 `Contains[T comparable]`（`==` 需要 comparable）
- 自定义类型（如 `type Celsius int`）必须能直接传给 `Map`/`Reduce`（`~int` 的作用）

**验收**：`go test -v ./...` 通过；`go run .` 演示 int/float64/Celsius 三种类型共用同一套函数（参考实现实测输出见 sol-01 文件头验证块）

**提示**：sol-01 目录；先想清楚 `Reduce` 的约束为什么必须比 `Map` 严格——这是「约束是泛型函数 API 的一部分」的核心教学点

## 练习 2：观察 slice 扩容（★★）

**目标**：写一个观察器，从 `cap=1` 起反复 `append`，打印容量每次变化的成长点序列；再用三种元素大小（1 B / 8 B / 32 B）对比同一规则的不同结果，亲手得出「<256 翻倍、≥256 约 1.25 倍 + size class 取整」的结论。

**要求**：
- `GrowSequence[T any](n int) []int`：记录 cap 成长点序列（元素类型作类型参数——一个实现测三种元素）
- 输出并对比 `[]int`、`[]byte`、`[][32]byte` 三个序列
- 测试断言**结构性规则**而非精确数字（精确数字依赖架构与 size class，跨机器会变）：① 容量严格增长；② prev<256 时 `cur ≥ 2×prev`（翻倍，size class 只会上取整）；③ prev≥256 时比率落在 [1.25, 2) 内

**验收**：`go test -v ./...` 通过；`go run .` 打印三个序列；能解释为什么 `[]byte` 首次扩容是 1→8（分配器最小块 8 B）而不是 1→2（参考实现实测：int 512→848、byte 512→896、[32]byte 512→852）

**提示**：sol-02 目录；先跑起来看序列，再想「规则」与「具体数字」哪个该写进测试——这正是 ph08 测试阶段「断言意图而非实现」思想的延伸

## 练习 3：defer / panic-recover 语义实验（★★）

**目标**：把「defer、panic/recover 原理」的六个语义做成可断言的实验函数，逐条验证：LIFO、参数求值时机、闭包引用、命名返回值、recover 只在 defer 中生效、嵌套 panic 覆盖。

**要求**：
- `Order()`：返回 defer 实际执行顺序（注意：defer 里 append 返回值必须用**命名返回值**，普通 return 拿不到——这是隐藏教学点）
- `ArgEval()`：返回「body 中的 n」与「defer 捕获的 n」，验证参数在 defer 语句处求值
- `NamedReturn()`：defer 修改命名返回值（return 5 后 defer ×10 → 50）
- `PanicNil()`：验证 Go 1.21+ 的 `panic(nil)` recover 返回非 nil 的 `*runtime.PanicNilError`
- `SafeCall(f func()) error`：用 recover 把 panic 转成 error（生产代码「panic 转 error」的标准模式）

**验收**：`go test -v ./...` 通过（九条断言全部覆盖上述语义）；`go run .` 打印实验报告（参考实现实测输出见 sol-03 文件头验证块）

**提示**：sol-03 目录；`panic(nil)` 在 Go 1.21 前 recover 返回 nil（「recover 返回 nil = 没 panic」的旧经验），1.21+ 行为变了——这正是「语义随版本演进」的活例子

## 练习 4：反射版配置加载器（★★★）

**目标**：不用 viper 等第三方库，用 reflect 实现配置加载：JSON 字符串给默认值、环境变量做覆盖（env 优先），按 `cfg` tag 匹配 key、按字段 Kind 自动转换类型。

**要求**：
- `LoadJSON(cfg, data)`：从 JSON 填充（数字进 map 是 float64，要按目标字段 Kind 转 int/bool/float64）
- `LoadEnv(cfg, prefix)`：从环境变量填充（key = prefix + tag 大写，转小写对齐 tag）
- `Load(cfg, jsonData, prefix)`：组合——env 覆盖 json（文件给默认值、环境变量做覆盖是生产常见语义）
- 错误处理：类型不匹配、非法 JSON、int 溢出都要报错且带字段名
- 关键坑：`float64→int64` 溢出是**静默**的（直接 `int64(x)` 转换在溢出时结果实现相关），必须转换前查值域，不能依赖 `reflect.OverflowInt`（它查的是 int64→目标类型，查不到源头）

**验收**：`go test -v ./...` 通过（九条测试覆盖填充/缺 key/坏 JSON/坏类型/溢出/env 覆盖/string→float/bool）；`go run .` 演示四种场景（参考实现实测输出见 sol-04 文件头验证块）

**提示**：sol-04 目录；反射的三个要点——`reflect.ValueOf(cfg).Elem()` 取可寻址值、`CanSet` 只对可寻址导出字段为 true、`SetXxx` 按 Kind 分派；对照示例 ex05 的加载器看「两种来源、一个转换函数」怎么复用
