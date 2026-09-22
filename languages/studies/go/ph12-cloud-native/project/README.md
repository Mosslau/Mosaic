# ph12 阶段项目：可部署 API 服务模板

> 对应 Roadmap「云原生与部署阶段」推荐项目之一——**可部署 API 服务模板**（另一个「Kubernetes 部署示例」的清单部分在本项目 deploy/k8s/ 一并给出）。
> 把本阶段全部知识点合成一个"开箱即部署"的 Go 服务：**12-Factor 配置 + /healthz 与 /readyz 探针 + 手工 Prometheus /metrics + slog JSON 日志 + SIGTERM 优雅退出 + Dockerfile 多阶段构建 + K8s 清单（探针/滚动更新/ConfigMap/Secret/Ingress）**。全部代码零第三方依赖（仅标准库），可离线构建运行；Docker/K8s 部署在有对应环境时执行。

## 需求

做一个"能被真实环境直接消费"的 API 服务模板（承接 ph09 单体 HTTP / ph10 数据层 / ph11 微服务通信的部署环节）：

- **配置**：环境变量驱动（12-Factor），默认值 + 必填项（DB_URL）校验 + fail-fast
- **探针**：/healthz（liveness，恒 200）+ /readyz（readiness，依赖就绪 200 / 未就绪 503），业务接口与探针口径一致
- **指标**：/metrics 输出 Prometheus text exposition（counter/gauge/histogram，零第三方库手工实现）
- **日志**：slog JSON 结构化（级别可配、AddSource、请求级字段、DB 密码脱敏）
- **优雅退出**：SIGINT/SIGTERM → 先摘 readiness → Shutdown 等在途请求 → 超时兜底
- **部署**：Dockerfile（多阶段 → scratch，~10MB 镜像）+ compose.yaml + K8s Deployment/Service/Ingress

## 目录结构

```text
project/
├── cmd/api/main.go              # 入口：配置加载 → 日志 → 服务装配 → 优雅退出
├── internal/
│   ├── config/                  # 12-Factor 配置：默认值/覆盖/校验/MaskDBURL
│   ├── metrics/                 # 手工 Prometheus 指标库（counter/gauge/histogram/registry）
│   └── server/                  # HTTP 层：探针 + /metrics + 业务接口 + 指标埋点
├── deploy/k8s/                  # ConfigMap + Secret（演示值）+ Deployment + Service + Ingress
├── Dockerfile                   # 多阶段构建（builder → scratch）
├── compose.yaml                 # 本地单命令起服务
├── go.mod
└── README.md                    # 本文件
```

## 功能清单

- [x] 12-Factor 配置：PORT/ADDR/DB_URL(必填)/LOG_LEVEL/SHUTDOWN_TIMEOUT/ENABLE_METRICS，非法值启动即报错
- [x] /healthz 恒 200（liveness）；/readyz 依赖就绪前 503、就绪后 200（readiness）
- [x] 业务接口在未就绪时也 503（探针与业务口径一致）
- [x] /metrics：counter（请求总数/错误数）+ gauge（在途）+ histogram（延迟），exposition 0.0.4
- [x] slog JSON 日志：AddSource + 请求级字段 + DB_URL 密码脱敏 + 级别过滤
- [x] SIGTERM 优雅退出：摘 readiness → Shutdown 等在途 → 超时兜底
- [x] Dockerfile 多阶段构建（CGO_ENABLED=0、非 root、scratch 运行）
- [x] K8s 清单：滚动更新 + liveness/readiness probe + ConfigMap + Secret（演示资源，见 deploy/k8s/secret.yaml）+ Ingress

## 验收标准

- `go build ./...`、`go vet ./...` 零告警、`go test ./...` 全部通过、`go test -race ./...` 无数据竞争
- `go test -cover ./internal/...` 实测覆盖率（go1.25.6）：**internal/config 86.5%、internal/metrics 84.1%、internal/server 91.7%**（cmd/api 为入口不计量）
- 冒烟（本环境实测通过，测完已 kill 干净、无残留进程与端口）：

```text
DB_URL=postgres://user:pw@db:5432/app /tmp/ph12-api   # 起 127.0.0.1:58010
curl /healthz                    -> 200 {"status":"ok"}
curl /readyz                     -> 200 {"status":"ready"}（500ms 就绪窗口内 503）
curl /api/devices/car-001        -> 200 {"device_id":"car-001","status":"online"}
curl /metrics                    -> # TYPE http_requests_total counter ... histogram 桶分布
kill -TERM <pid>                 -> 日志: "shutting down" → "server exited"；端口释放
日志含 source 字段（file:line）与 db_url 脱敏（postgres://user:***@db:5432/app）
```

- Docker 部署（本机 docker daemon 可用时实测；不可用则如实标注「未在本环境验证（需 Docker 环境）」）：

```bash
# 1. 构建与运行（在 project/ 目录）
docker build -t ph12-api:latest .
docker run --rm -p 58010:58010 -e DB_URL=postgres://u:p@db/app ph12-api:latest
# 2. 容器内健康检查（与 K8s 探针同语义）
curl -s http://127.0.0.1:58010/healthz && curl -s http://127.0.0.1:58010/readyz
```

- Kubernetes 部署（需 K8s 集群；本机无集群则如实标注「未在本环境验证（需 Kubernetes 环境）」）：

```bash
kubectl apply -f deploy/k8s/          # ConfigMap + Secret（演示值）+ Deployment + Service + Ingress
kubectl rollout status deploy/ph12-api
kubectl get pods -l app=ph12-api      # 2/2 Ready（readiness 探针通过；Secret 已随 apply 创建，Deployment 引用可解析）
kubectl get svc ph12-api
```

> Secret（deploy/k8s/secret.yaml）内的 db-url 是**演示值**（base64 明文仅供教学展示 Secret 形态）；生产环境用外部 Secret 管理（sealed-secrets / External Secrets Operator / KMS），不要把真实凭据写进仓库。

## 验证环境

go1.25.6（darwin/arm64），依赖：**零第三方**（全部标准库，可离线构建运行）。

```bash
# 1. 构建与测试
go build ./...
go vet ./...
go test ./... && go test -race ./... && go test -cover ./internal/...

# 2. 本机直接运行（冒烟）
DB_URL=postgres://user:pw@db:5432/app go run ./cmd/api
# 另开终端：
curl -i http://127.0.0.1:58010/healthz
curl -i http://127.0.0.1:58010/readyz
curl -s http://127.0.0.1:58010/metrics
curl -s http://127.0.0.1:58010/api/devices/car-001
# 3. 优雅退出
kill -TERM <pid>
```

## 扩展方向（可选）

- **接真实数据源**：`/api/devices/{id}` 的返回接入 ph10 数据库阶段的连接池与查询（现在为模板占位）
- **gRPC 化**：把 HTTP 接口换成 ph11 的 gRPC 服务，/metrics 与探针保持不变（部署层与协议解耦）
- **接入 OpenTelemetry SDK**：把 traceparent 上下文（examples/ex05 概念版）换成官方 otel-go SDK 的自动埋点，上报 Jaeger（需第三方依赖，本环境未验证）
- **服务网格/API Gateway**：Ingress 换成 Istio/Envoy 的 VirtualService 做金丝雀发布与流量治理（属本阶段 3.8 的延伸）
- **镜像体积对照**：用 `docker images` 对比 golang:1.25-alpine（~300MB）vs 本模板 scratch（~10MB），体会多阶段构建收益
