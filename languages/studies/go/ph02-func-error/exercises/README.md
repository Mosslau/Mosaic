# ph02 函数与错误处理 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：Go 1.22.2（darwin/arm64），无外部依赖。每个 sol-* 都是独立的 package main，用 `go run sol-0X-*.go` 逐文件运行。

## 练习 1：安全除法（★）

**目标**：实现带错误返回的整数除法。
**要求**：实现 `divide(a, b int) (int, error)`，除零时用 `errors.New` 返回错误；在 `main` 中演示一次正常除法和一次除零，用 `if err != nil` 分别处理两条路径。
**验收**：`divide(10, 3)` 输出商 3；`divide(5, 0)` 输出错误信息而非 panic。

## 练习 2：文件读取错误处理（★★）

**目标**：读取文件并用 `defer` 保证关闭，逐层包装错误。
**要求**：实现 `readLines(path string) ([]string, error)`：打开失败、读取失败分别用 `fmt.Errorf("...: %w", err)` 包装并携带路径上下文；打开成功后立即 `defer f.Close()`。`main` 中先创建一个临时文件再读取，另外演示读取一个不存在的路径，用 `errors.Is(err, os.ErrNotExist)` 区分「文件不存在」与其他错误。
**验收**：正常读取时打印文件内容行；路径不存在时输出「文件不存在: ...」，其他错误输出包装后的完整错误链。

## 练习 3：配置解析错误处理（★★）

**目标**：解析 `key=value` 格式配置，返回带上下文的错误链。
**要求**：实现 `parseConfig(input string) (map[string]string, error)`：跳过空行与 `#` 开头的注释行；遇到不含 `=` 的行返回错误，错误信息必须包含行号与原始行内容；用哨兵错误 `ErrInvalidConfig` 加 `%w` 包装，供调用方用 `errors.Is` 判定。`main` 中分别演示一份合法配置和一份含坏行的配置。
**验收**：合法配置解析出全部键值对；坏行配置触发 `errors.Is(err, ErrInvalidConfig)` 为 true，且错误信息含行号。

## 练习 4：自定义业务错误（★★★）

**目标**：为车辆/设备业务对象定义自定义错误类型，并用 `errors.As` 提取结构化字段。
**要求**：定义 `VehicleError` 结构体（含 `Code int`、`Vin string`、`Message string` 字段），实现 `Error() string` 方法；实现 `checkVehicle(vin string, soc float64) error`：VIN 为空返回 `Code=1001` 的错误，电量 `soc` 低于 20 返回 `Code=2001` 的低电量错误；`main` 中用 `errors.As` 取出 `*VehicleError`，按 `Code` 分支处理（如低电量提示「请充电」）。
**验收**：空 VIN 输出 code=1001 的错误；`soc=15` 时 `errors.As` 成功提取并输出「车辆 <vin> 电量过低（code=2001），请充电」。

## 练习 5：defer 执行顺序与参数求值（★）

**目标**：验证 `defer` 的 LIFO 顺序与参数即时求值。
**要求**：在一个函数里注册至少 3 个 `defer`，其中至少一个带参数（如 `defer fmt.Println("defer:", i)`），注册后修改该变量；预测输出顺序，再运行验证。另写一个 `defer` 闭包（不带参数、引用变量），对比闭包捕获与参数求值的差异。
**验收**：能用一句话解释每一行输出为什么是那个值、按什么顺序出现。
