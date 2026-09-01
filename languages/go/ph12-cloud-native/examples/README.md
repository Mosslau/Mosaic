# examples —— 云原生与部署阶段完整示例

验证环境：go1.25.6（darwin/arm64）。六个示例各自是**独立的 Go module**（目录内自带 go.mod），先进入示例目录再运行——请勿在 examples/ 根目录执行 `go test ./...`（根目录没有 go.mod）。

**实现策略**：示例 1~5 全部基于**标准库**（零第三方依赖，可离线构建运行）——本阶段"可实测的核心"（健康检查与优雅退出、12-Factor 配置、slog 结构化日志、Prometheus 指标 exposition、OpenTelemetry traceparent 上下文）都能用纯标准库演示；示例 6 是容器化（Dockerfile 多阶段构建 + Compose），服务本体是标准库，Docker 构建/运行依赖本机 docker daemon（见下方实测记录）。

| 目录 | 说明 | 运行 |
|------|------|------|
| `ex01-health-graceful/` | 健康检查 + 优雅退出：/healthz（liveness）与 /readyz（readiness）语义与状态码、atomic.Bool 就绪、SIGTERM → 摘 readiness → Shutdown 等在途请求 | `cd ex01-health-graceful && go test -v`；`go run .`（默认 127.0.0.1:58001） |
| `ex02-config-12factor/` | 12-Factor 配置：环境变量加载（默认值/覆盖/必填校验/类型解析/fail-fast）+ 配置驱动路由 | `cd ex02-config-12factor && go test -v`；`go run .` |
| `ex03-slog-json/` | slog JSON 结构化日志：级别过滤、AddSource、With 请求级上下文、handler 埋点、InfoContext | `cd ex03-slog-json && go test -v`；`go run .` |
| `ex04-prometheus-metrics/` | 手工 Prometheus /metrics：counter/gauge/histogram 的 text exposition 0.0.4（HELP/TYPE/标签/桶/+Inf/sum/count） | `cd ex04-prometheus-metrics && go test -v`；`go run .`（127.0.0.1:58004） |
| `ex05-traceparent/` | OpenTelemetry traceparent：W3C trace context 头生成/解析/传播（A→B 两服务串起同一条 trace） | `cd ex05-traceparent && go test -v`；`go run .`（127.0.0.1:58005） |
| `ex06-containerize/` | 容器化：多阶段 Dockerfile（builder→scratch）+ Compose + 最小健康检查服务 | `cd ex06-containerize && go test -v`；`go run .`；Docker 命令见下 |

## 实测数据（本环境跑出，如实记录）

全部示例通过 `gofmt -l`（零差异）、`go vet ./...`（零报告）、`go test ./...`（行为符合预期）；ex04/ex05 另过 `go test -race ./...`（无数据竞争）。覆盖率为本机实际输出（`go test -cover`）：

| 示例 | go test -cover | 备注 |
|------|----------------|------|
| ex01-health-graceful | 47.3% | 5 个用例全过（healthz 恒 200/readyz 503→200/业务口径/Shutdown 等在途/未知路径） |
| ex02-config-12factor | 73.8% | 5 个用例全过（默认值/覆盖/必填 errors.Is/非法值×5/指标开关） |
| ex03-slog-json | 50.0% | 5 个用例全过（JSON 行合法/级别过滤/With 继承/handler 双分支/InfoContext） |
| ex04-prometheus-metrics | 69.8% | 7 个用例全过（exposition 语法/counter 单调/标签排序转义/formatFloat/抓取/计数反映/在途归零） |
| ex05-traceparent | 52.5% | 6 个用例全过（55 字符格式/子 span 继承/round-trip/非法头拒绝/缺头/注入提取/链路打通） |
| ex06-containerize | 47.4% | 3 个用例全过（healthz 200/根路径标识/未知路径 404）；服务本体与 Docker 无关 |

## Docker 实测记录（本环境如实标注）

- 本机装有 **Rancher Desktop**（docker CLI 29.6.2-rd、docker compose v5.3.1、kubectl v1.36.3、helm v4.2.3），但**本会话中 docker daemon 未能就绪**（VM 启动未完成 / daemon API 未响应），故示例 6 与 project 的 Dockerfile/Compose 只做了**语法与结构编写**，未实际 build/run。
- **验证状态：示例 1~5 全部「已验证」；示例 6 的服务本体「已验证」；示例 6 与 project 的 Docker 构建/运行「未在本环境验证（需 Docker 环境）」；K8s 清单（project/deploy/k8s/、sol-05 deploy/k8s/）「未在本环境验证（需 Kubernetes 环境）」——本机 kubectl 无可用集群（cluster-info 连接拒绝）。**
- 有 docker/kubectl 环境时的标准命令（示例 6）：

```bash
# 1. 构建镜像（多阶段：builder 编译 → scratch 运行，约 10MB）
docker build -t ph12-ex06:latest .
# 2. 运行并验证健康检查
docker run --rm -p 58006:58006 ph12-ex06:latest
curl -s http://127.0.0.1:58006/healthz
# 3. Compose 一键起
docker compose up --build
# 4. 看镜像体积对比（多阶段构建收益）
docker images | grep ph12-ex06
```

## 注意事项

- 示例均为**单进程自包含**（程序内起 server、client 调用后退出，无残留进程）；ex01 服务监听 127.0.0.1:58001、ex03 58003、ex04 58004、ex05 58005、ex06 58006——固定高位端口避免冲突，`go run` 结束即释放；测试内用 `127.0.0.1:0`（内核分配随机端口）。
- /metrics 的 Content-Type 必须是 `text/plain; version=0.0.4`——Prometheus 按版本解析；标签值转义防 exposition 注入（ex04 有专门用例）。
- traceparent 是**分布式追踪的唯一跨服务协议**（W3C 标准）：服务端从入站头还原父 span、把响应回传的 trace_id 用于日志关联——ex05 演示的机制与 otel-go SDK 自动埋点做的事一致，只是后者把"生成 span + 传播"封装进了拦截器（ph11 的 gRPC interceptor 接入点）。
