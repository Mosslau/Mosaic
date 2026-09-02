# ph16 阶段项目：API 服务 PGO 实验

## 需求

把「用生产 profile 指导编译」跑成一个端到端实验：一个**设备签名 API 服务**（`cmd/apiserver`）的请求路径上有纯 CPU 接口热点（Signer 接口分派 90% fnvSigner / 10% xorSigner，正是 PGO 去虚拟化能作用的地方），用压测工具（`cmd/loadgen` + `internal/workload`）把服务压到 CPU 忙、期间采集服务端 CPU profile，再用这份 profile 构建 `-pgo` 版二进制，最后对比基线 vs PGO 两份延迟/吞吐报告——对应 Roadmap §16 推荐项目「API 服务 PGO 实验」。

## 功能清单

- [x] `cmd/apiserver`：`GET /api/devices/{id}` 返回设备信息 + 遥测签名（`signDevice` 逐样本走 `Signer.Step`，`//go:noinline` 保持独立函数——内联会吞掉去虚拟化收益，文件头有实测理由）
- [x] `cmd/apiserver`：`/healthz` 探活 + `/debug/pprof/*` 手动挂载（net/http/pprof，压测期间可采 `profile?seconds=N`）
- [x] `cmd/loadgen`：`internal/workload` 的薄 CLI（`-url/-n/-workers/-devices/-timeout`），报 p50/p95/p99/均值/吞吐
- [x] `internal/workload`：HTTP 压测库——代表性负载（把服务压到 CPU 忙）+ 延迟样本报告
- [x] `scripts/pgo-experiment.sh`：一键编排——起服务 → 压测采 profile → `-pgo` 构建 → 基线 vs PGO 双报告 + `go version -m` 印章核对

## 目录结构

```
project/
├── go.mod                      # go 1.25.0（全仓语言版本档）
├── cmd/
│   ├── apiserver/              # API 服务（main.go + main_test.go：httptest 断言 + 签名 benchmark）
│   └── loadgen/                # 压测入口（main.go）
├── internal/
│   └── workload/               # 压测库（workload.go + workload_test.go）
└── scripts/
    └── pgo-experiment.sh       # 一键 PGO 实验编排
```

## 验证环境与命令

- 验证环境：go1.25.6（darwin/arm64），零第三方依赖；go 命令需带仓库统一重定位环境
  （`GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache GOPROXY=https://goproxy.cn,direct GOSUMDB=off`）
- 测试/静态检查：`go test ./... && go vet ./...`（实测通过，2026-09-02）
- 一键实验：`./scripts/pgo-experiment.sh`（产物一律写 /tmp/ph16proj/，服务自动起停）

## 验收标准

- [ ] `go test ./... && go vet ./...` 通过（apiserver 的 main_test 断言签名 digest 确定性与 healthz；workload_test 断言报告结构）
- [ ] 按 `scripts/pgo-experiment.sh` 跑完全流程，产出 `baseline.txt` 与 `pgo.txt` 两份延迟/吞吐报告
- [ ] 对照两份报告能说出 PGO 前后差异（本机实测基线 vs PGO 的 p50/p95/p99 与 req/s；数字随机器与负载波动 ±10~20%，关注趋势而非绝对值）
- [ ] `go version -m apiserver-pgo` 能看到 `-pgo=/tmp/ph16proj/cpu.pprof` 印章（证明 PGO 真实生效，不是碰运气）
- [ ] 能解释为什么本项目形态适合 PGO（接口热点 + 分布倾斜 90/10）——见主文档 §4 与 examples/ex02

## 运行实录（本机 2026-09-02 实测，摘录）

`./scripts/pgo-experiment.sh` 全流程 exit 0：基线压测报告与 PGO 版压测报告均正常产出；
`go version -m` 显示 `-pgo=/tmp/ph16proj/cpu.pprof`。单请求冒烟：

```
$ go run ./cmd/apiserver -addr 127.0.0.1:18090 -devices 2048 -samples 8192 &
$ curl -s http://127.0.0.1:18090/api/devices/1
{"id":1,"name":"device-00001","samples":8192,"digest":"<64位hex>"}
$ curl -s http://127.0.0.1:18090/healthz
{"status":"ok"}
```

## 扩展方向

- 把采集从「手动压测窗口」换成生产流量采样（`default.pgo` 约定：Go 1.21+ 放模块根即可被 `go build` 自动使用）
- 加回归闸：把 `baseline.txt` 的 p50/吞吐钉成基线，CI 里跑 `pgo-experiment.sh` 的对比步骤，退化即失败（骨架思路同 examples/ex05-bench-baseline）
- 对比真实业务 profile 与合成负载 profile 的收益差异（代表性是 PGO 的前提，主文档 §5）
