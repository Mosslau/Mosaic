# ph03 Slice、Map、Struct 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：Go 1.22.2（darwin/arm64），无外部依赖。每个 sol-* 都是独立的 package main，用 `go run sol-0X-*.go` 逐文件运行。

## 练习 1：slice 扩容实验（★）

**目标**：观察并记录 append 过程中 len/cap 的变化规律。
**要求**：写一个程序，分别用 `var s []int`（nil 起始）和 `s := make([]int, 0, 8)`（预分配容量）两种方式，循环 append 0~9，每次打印 len/cap；对比两次输出的 cap 序列差异。
**验收**：能说出 nil 起始时 cap 按 1→2→4→8→16 翻倍；预分配 cap=8 时前 8 次 append 不触发扩容、cap 保持 8，第 9 次才扩容。

## 练习 2：学生管理系统（★★）

**目标**：用 `map[int]Student` 实现 ID 索引的增删改查。
**要求**：定义 `Student` struct（含 ID、Name、Score）；实现「增、查、改、删」四个动作——查用 ok 模式区分「不存在」与「零值」，改需回写（struct 是值类型），删用 `delete`；最后按 ID 升序列出所有学生。
**验收**：查询存在的 ID 能打印姓名分数；查询不存在的 ID 输出「未找到」；删除后再查询仍输出「未找到」；列表按 ID 有序。

## 练习 3：设备状态表（★★）

**目标**：用 map + struct 管理设备 ID、类型、状态和资源利用率。
**要求**：定义 `Device` struct（ID、Type、Status、CPU、Mem）；实现添加设备、更新状态/指标（回写）、按 Status 筛选（返回 `[]Device`，结果按 ID 排序保证稳定）、统计在线设备数与总数。
**验收**：`filterByStatus(devices, "online")` 只返回 Status 为 online 的设备且按 ID 有序；更新某设备后查询显示新值。

## 练习 4：map + struct 管理设备数据（★★★）

**目标**：用 struct 组合表达设备，map 做 DEVICE_ID 快速索引。
**要求**：定义 `Motor`、`Component`、`Device`（Device 匿名嵌入前两者）；用 `map[string]Device` 以 DEVICE_ID 为键管理设备组；实现增、查（直接访问提升字段）、改（回写）、删；实现 `fleetStats` 统计平均电量与运行中（`Enabled` 为 true）设备数；按 DEVICE_ID 排序列出全部设备。
**验收**：能按 DEVICE_ID 查询并直接读 `v.Speed`、`v.Level` 等提升字段；`fleetStats` 返回的平均电量与运行中数量正确；删除后列表规模减一。
