# ph13 阶段项目：日志解析性能优化

## 需求

对应 roadmap ph13「推荐项目」之「日志解析性能优化」。日志采集/清洗服务每天要解析数百万行 JSON 日志，解析耗时与内存分配直接决定吞吐。本项目落地**「先 profile 再优化」的完整闭环**：生成可复现的合成日志 → 用三种解析实现解析同一批数据 → 量化耗时与分配差异 → 校验三者结果一致。

三种解析实现（`internal/parser`）：

| 实现 | 手段 | 定位 |
|------|------|------|
| `ParseNaive` | `encoding/json` → `map[string]any` + `fmt.Sprint` 提取字段 | 基线：通用、每行一个 map + 字段装箱 |
| `ParseStruct` | `encoding/json` → 具名 struct（编译期字段表） | 优化 1：跳过 map 反射路径 |
| `ParseManual` | 手写字节扫描（`strings.Index` + `strconv`） | 优化 2：完全不走 JSON 解码器（牺牲通用性换速度） |

## 功能清单

- [x] `genlog`：固定种子生成合成 JSON 日志（`-gen`），可复现
- [x] `parser`：三种解析实现，坏行跳过容错，结果可互相校验
- [x] `logbench` CLI：`-gen` 生成 / `-bench` 耗时与分配对比 / `-verify` 结果一致性校验
- [x] 测试：三版结果一致、坏行容错、确定性生成（`go test -race ./...` 通过）

## 运行方式（已在 go1.25.6 / darwin / arm64 验证，零第三方依赖）

```bash
cd languages/studies/go/ph13-perf-optimization/project
go test ./... && go test -race ./...          # 验证：测试 + 竞态检测
go run ./cmd/logbench -gen 100000 -out /tmp/logs.jsonl   # 1. 生成 10 万行
go run ./cmd/logbench -bench /tmp/logs.jsonl              # 2. 三种解析耗时/分配对比
go run ./cmd/logbench -verify /tmp/logs.jsonl             # 3. 校验结果一致
```

## 验收标准

- [ ] **10 万行解析 < 1s**：`-gen 100000` 后 `-bench`，三版均满足（实测最慢的 naive 也仅 ~108 ms，见下方实测）
- [ ] **三种解析结果一致**：`-verify` 输出「✓ 三种解析结果一致（100000 条）」，退出码 0
- [ ] **优化有据可查**：能解释 naive → struct → manual 每步优化改了什么、省了什么（对应主文档 3.x 与 5 章）
- [ ] **`go test -race ./...` 通过**（本项目为纯函数无并发，race 验证无数据竞争）

## 实测记录（go1.25.6，Apple M4 Pro，2026-09-01）

**CLI 实测（10 万行/轮，-repeat 5 取最好）**：

| 实现 | 总耗时 | ns/行 | 分配/轮 | 相对 naive |
|------|--------|-------|---------|-----------|
| naive (map) | 107.5 ms | 1075.1 | 111.94 MB | 1x（基线） |
| struct | 64.7 ms | 647.2 | 43.31 MB | 快 1.7x |
| manual | 18.5 ms | 184.6 | 4.01 MB | **快 5.8x** |

**`go test -bench` 实测（1000 行/op，-benchtime=1000x）**：

```
BenchmarkParseNaive-14     1000   ~1075000 ns/op   987569 B/op   28984 allocs/op
BenchmarkParseStruct-14    1000    ~659000 ns/op   434129 B/op    8001 allocs/op
BenchmarkParseManual-14    1000    ~184000 ns/op    40960 B/op       1 allocs/op
```

**结论**：manual 版快约 5.8 倍、分配次数 28984 → 1（-99.997%）、B/op -96%。分配次数是 GC 压力源头（roadmap 必会概念）：map 版每行 29 次分配 → struct 版 8 次 → manual 版只有结果 slice 的 1 次预分配。数字随机器波动，以本机重跑为准。

## 扩展方向（可选）

- 加 `-stats`：解析后按 level/device 聚合统计（条数、平均/最大 latency），用 pprof 定位聚合热点
- 用 `runtime/pprof` 采集本项目 CPU profile，验证「naive 的热点在 encoding/json 反射路径」（衔接示例 ex03）
- 支持多行缓冲读取（`bufio.Reader` 手写 `ReadBytes('\n')`）与并发分片解析（每片一个 goroutine，衔接 ph06 并发）
- 真实日志格式变化时，`ParseManual` 需要同步维护——这就是「通用性 vs 性能」取舍的活教材（见主文档 5 章选型参考）
