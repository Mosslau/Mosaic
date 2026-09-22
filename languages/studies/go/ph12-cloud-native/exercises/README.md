# ph12 云原生与部署阶段练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★），与 roadmap 本阶段「练习」小节对齐（写 Dockerfile / Compose 启动 / 部署到 Kubernetes / 接入 Prometheus），并把「可实测的核心」落成纯标准库 Go 代码：健康检查与优雅退出、12-Factor 配置、结构化日志、Prometheus 指标、容器化清单编写。

运行方式：每个参考实现是**独立的 Go module**（目录内自带 go.mod），先进入对应目录再运行（如 `cd sol-01-health-graceful && go test -v`）。请勿在 exercises/ 根目录执行 `go test ./...`——根目录没有 go.mod。

依赖：sol-01~04 **零第三方依赖**（仅标准库，可离线运行）；sol-05 的服务本体也是标准库，Docker/Compose/K8s 清单为纯文本文件（无 go 依赖）。参考实现文件头都写了验证环境与命令；**sol 文件头的覆盖率数字均为本机实测后写入**（ph08/ph10 教训：不许先写后编）。

Docker 相关练习的验证状态：本机 **docker daemon 是否可用以 examples/README.md 与 sol-05 文件头实测记录为准**——有 docker 才实际 build/run，没有则如实标注「未在本环境验证（需 Docker 环境）」。

## 练习 1：健康检查与优雅退出（★）

**目标**：实现带 /healthz（liveness）与 /readyz（readiness）的 HTTP 服务，并用 SIGTERM 优雅退出。

**要求**：

- /healthz 恒 200（进程活着即存活）；/readyz 未就绪 503、就绪后 200（依赖就绪前摘除流量）
- 就绪状态用一个 `atomic.Bool` 控制（读路径零锁零分配），提供 `MarkReady()` 供应用在依赖就绪后调用
- 收到 SIGINT/SIGTERM 后：先把 ready 置 false（/readyz 立即 503）→ `http.Server.Shutdown` 等存量请求完成 → 超时兜底
- 业务接口在未就绪时也返回 503（探针与业务口径一致）

**验收**：`go test -v` 覆盖：healthz 恒 200、readyz 未就绪 503 / 就绪 200、未就绪时业务接口 503、Shutdown 等待在途请求完成（慢 handler 不被硬断）、未知路径 404；`go vet ./...` 零报告。

> 提示：参考 examples/ex01-health-graceful；Shutdown 的"等在途请求"用例参考其测试写法。

## 练习 2：12-Factor 配置加载器（★★）

**目标**：实现环境变量驱动的配置加载（12-Factor 第 3 条），带默认值、必填项校验、类型解析与 fail-fast。

**要求**：

- 配置项：PORT（默认 58002）、DB_URL（**必填**，缺失启动即报错）、LOG_LEVEL（debug/info/warn/error）、SHUTDOWN_TIMEOUT（time.Duration）、ENABLE_METRICS（bool）
- 校验：PORT 1~65535、LOG_LEVEL 枚举、超时为正、布尔可解析；非法值返回带上下文的错误（`fmt.Errorf` + `%w`）
- 必填缺失错误用哨兵/自定义类型，支持 `errors.Is`/`errors.As` 判断
- 配置加载与"装配路由"解耦：`ENABLE_METRICS=false` 时 /metrics 应 404

**验收**：`go test -v` 覆盖：默认值正确、环境变量覆盖生效、必填缺失报错且 errors.Is 可判、五类非法值各报错、指标开关影响路由；`go vet ./...` 零报告。

> 提示：参考 examples/ex02-config-12factor；`Load(getenv func(string) string)` 的函数注入让测试不用动真实环境变量。

## 练习 3：结构化日志（★★）

**目标**：用 log/slog 输出 JSON 结构化日志，掌握级别过滤、请求级上下文（With）与埋点位置。

**要求**：

- `NewJSONHandler` + `AddSource`（日志带 source 文件:行）+ 可配置级别
- 请求级 logger：`With("trace_id", ..., "user_id", ...)`，后续日志自动继承
- 业务 handler 埋三处点：进入（method/path）、参数缺失（Warn 但继续 400）、完成（latency_ms）
- 低于配置级别的日志必须被丢弃（测试验证）

**验收**：`go test -v` 覆盖：每行是合法 JSON 且含 msg/level/time、级别过滤生效、With 字段继承到后续日志、handler 成功/失败路径日志正确、`InfoContext` API 可用；`go vet ./...` 零报告。

> 提示：参考 examples/ex03-slog-json；注意 slog 没有 FromContext（那是第三方 otel 生态的集成点），context 版本 API 是 `InfoContext`。

## 练习 4：Prometheus 指标暴露（★★★）

**目标**：不引第三方库，手写 counter / gauge / histogram 并输出 Prometheus text exposition 格式（0.0.4），让 Prometheus 可直接抓取。

**要求**：

- Counter：只增不减（Inc/Add）；Gauge：可增可减（Inc/Dec/Set）；Histogram：分桶累计计数 + _sum + _count
- 输出带 `# HELP` / `# TYPE` 注释；多标签按 key 排序；标签值转义引号与反斜杠；`+Inf` 桶
- /metrics 的 Content-Type 为 `text/plain; version=0.0.4; charset=utf-8`
- 业务 handler 埋点：请求总数（按 handler 标签）、错误总数、在途数（gauge）、延迟直方图
- 线程安全：指标与业务并发写，`-race` 干净

**验收**：`go test -v` 覆盖：exposition 语法完整（HELP/TYPE/桶分布/sum/count）、counter 单调、标签排序与转义、/metrics 可抓取且反映最新计数、在途数归零；`go vet ./...` 零报告、`go test -race` 无数据竞争。

> 提示：参考 examples/ex04-prometheus-metrics；验证抓取语义：发 N 个请求后 /metrics 里计数要等于 N。

## 练习 5：容器化与部署清单（★★）

**目标**：把练习 1 的健康检查服务打包——写 Dockerfile（多阶段构建）、compose.yaml（Go + MySQL + Redis 服务栈，对应 roadmap「用 Compose 启动 Go + MySQL + Redis」练习）、K8s Deployment + Service 清单，理解"镜像 = 只含静态二进制"与"探针写在哪一层"。

**要求**：

- `service/` 子目录放一个最小 Go 服务（/healthz + /readyz + 优雅退出，可 `go test` 验证）
- Dockerfile：builder（golang 镜像编译，`CGO_ENABLED=0`）→ scratch/distroless 运行；非 root；`-trimpath -ldflags "-s -w"`
- compose.yaml：端口映射 + 环境变量注入 + restart 策略；**补 MySQL 与 Redis 两个依赖服务**（固定镜像 tag、healthcheck + `depends_on: condition: service_healthy` 控制启动顺序、DB_URL/REDIS_ADDR 经环境变量注入——12-Factor 落地）
- deploy/k8s/：Deployment（replicas=2、livenessProbe 打 /healthz、readinessProbe 打 /readyz、滚动更新 strategy）+ Service（ClusterIP）
- 说明性注释：为什么探针放编排层而不是 Dockerfile HEALTHCHECK（scratch 无 shell/wget）

**验收**：`cd service && go test -v ./...` 通过、`go vet ./...` 零报告；`docker compose up --build`（起 Go + MySQL + Redis 三容器）与 `kubectl apply` 在**有 docker/k8s 的环境**执行（本机没有则 sol 文件头如实标注「未在本环境验证（需 Docker/Kubernetes 环境）」——禁止虚构验证）。

> 提示：参考 examples/ex06-containerize 的 Dockerfile/compose 与 project/deploy/k8s/ 的清单；滚动更新 strategy 用 `RollingUpdate` + maxUnavailable/maxSurge 说明。

---

五道练习与 `sol-*` 参考实现一一对应（sol-01 ~ sol-05），全部做完再对照复盘。sol-05 的 Docker/K8s 验证状态以文件头为准。
