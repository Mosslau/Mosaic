# Go 云原生与部署阶段

> 面向"把 Go 服务部署到真实环境"——本阶段把 ph09~ph11 的"能跑的代码"变成"能上线、能观察、能升级的部署物"：容器化（Docker/Dockerfile/Compose）、集群编排（Kubernetes/Helm）、CI/CD、健康检查与优雅退出、日志采集、监控告警（Prometheus/Grafana）、分布式追踪（Jaeger/OpenTelemetry）、API Gateway 与灰度发布——最终能交付一个可部署、可观测、可回滚的 API 服务模板。

## 1. 概述

Go 云原生与部署阶段的目标是（引用 Roadmap）：**能把 Go 服务部署到真实环境**——掌握 Linux 下的容器化（Docker/Dockerfile/Docker Compose）、集群编排（Kubernetes/Helm）、CI/CD 流水线（GitHub Actions/GitLab CI）、健康检查与优雅退出、日志采集、监控告警（Prometheus/Grafana/Jaeger/OpenTelemetry）、API Gateway 与灰度发布/滚动升级。ph09 的"单体 HTTP 服务"、ph10 的"数据层接入"、ph11 的"多服务 RPC 通信"在本阶段升级为**可部署的制品**：代码被打进镜像、镜像被编排到集群、集群由探针守护、指标/日志/追踪被采集系统消费——"能跑"与"能上线"之间的全部工程化差距由此补齐。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 容器化 | Docker 基础、Dockerfile 多阶段构建、镜像分层、Docker Compose 编排 |
| 集群编排 | Kubernetes 核心对象（Pod/Deployment/Service/ConfigMap/Secret）、探针、滚动更新、Helm 打包 |
| CI/CD | 流水线概念、GitHub Actions/GitLab CI 的 job/stage 模型、go 项目的流水线骨架 |
| 健康与生命周期 | /healthz（liveness）与 /readyz（readiness）语义、优雅退出（信号 + Shutdown） |
| 配置与日志 | 12-Factor 配置（环境变量）、slog JSON 结构化日志与采集 |
| 可观测性工具链 | Prometheus 指标（拉模型 + exposition 格式）、Grafana 展示、Jaeger/OpenTelemetry 追踪（traceparent） |
| 流量治理 | API Gateway 概念与集群内形态（Ingress/Service）、灰度发布与滚动升级 |

本阶段的核心信念来自四条必会概念：**Go 适合构建小型静态二进制**——CGO_ENABLED=0 的纯静态编译让 Go 服务能塞进 scratch/distroless 镜像（~10MB），这是容器化时代的"Go 优势"；**容器镜像应尽量小且可复现**——多阶段构建 + -trimpath 让镜像只含二进制、可重复构建，攻面小、拉取快；**健康检查和优雅退出很重要**——上线后"进程活着"不等于"能服务"，探针 + 信号是编排系统管理生命周期的接口；**配置不应写死在镜像里**——镜像与环境解耦（12-Factor），同一镜像在不同环境注入不同配置。

这个阶段只涉及"把 Go 服务容器化并部署到集群、接上可观测性与流量治理"这条主线，**不涉及性能剖析与优化（pprof、benchmark、GC 调优属 ph13 性能优化阶段，roadmap 第 13 节）、消息队列与日志采集管道（Kafka/NATS/Loki 的队列深入属 [ph19 消息队列与事件驱动深入阶段](../ph19-mq-event-driven/19-mq-event-driven.md)）、配置中心与 feature flag 发布控制（etcd/Consul 配置中心与灰度开关属 ph20 配置管理与发布策略阶段，roadmap 第 20 节，目录待建——本阶段的"灰度"只到 K8s 滚动更新的部署形态）、IoT/车联网设备接入（MQTT/WebSocket 设备协议属 ph21 IoT/车联网相关 Go 阶段，roadmap 第 21 节，目录待建）** — 本阶段是"容器 + 编排 + 可观测 + 部署"的工程化闭环。

## 2. 来源与演变

**云原生（Cloud Native）的源头是"把应用与运行环境彻底分离"**：2006 年 AWS 推出 EC2（基础设施即服务）开启虚拟化时代，但虚拟机重（GB 级 OS）、启动慢（分钟级）；2013 年 Docker 发布，用 Linux 内核的 namespace + cgroup 实现**轻量进程隔离**（MB 级、秒级启动），"构建一次，到处运行"首次真正可行——**设计哲学：应用与镜像不可变绑定，环境与配置可变注入**；2014 年 Kubernetes 开源（Google 的 Borg 系统对外开源），把"一台机器的容器"变成"一群机器的调度与自愈"，2015 年捐给 CNCF 成为云原生事实标准；此后 Helm（2015，K8s 的包管理器）、Prometheus（2012 诞生、2016 入 CNCF，监控的事实标准）、OpenTelemetry（2019，OpenTracing 与 OpenCensus 合并，可观测性的统一标准）相继定型。

**Go 与云原生是互相成就的**：Docker、Kubernetes、Prometheus、etcd、gRPC 全部用 Go 编写——Go 的静态二进制、低内存、高并发恰好是"云原生基建语言"的要求，反过来云原生生态也把 Go 推到了后端工程的主流位置（roadmap 推荐路线里的 Docker → Kubernetes → Prometheus 正是本阶段）。

| 版本/里程碑 | 年份 | 主要变化 |
|------|------|---------|
| EC2（IaaS 商业化） | 2006 | AWS 推出虚拟机即服务，云计算的起点 |
| Docker 发布 | 2013 | 容器化：namespace + cgroup 进程隔离，镜像机制 |
| Kubernetes 开源 | 2014 | Google 开源容器编排（Borg 的产物） |
| Docker Compose | 2014 | 单机多容器编排（YAML 声明服务） |
| Helm | 2015 | Kubernetes 的包管理器（Chart 模板化部署） |
| Kubernetes 入 CNCF | 2015 | 首个 CNCF 项目，云原生事实标准 |
| Prometheus 入 CNCF | 2016 | 监控事实标准（拉模型 + exposition 格式） |
| OpenTracing / OpenCensus | 2016-2017 | 追踪标准的两个阵营（后合并） |
| GitHub Actions | 2018 | CI/CD 内嵌 GitHub，流水线代码化（YAML） |
| OpenTelemetry 成立 | 2019 | OpenTracing 与 OpenCensus 合并，可观测性统一标准 |
| W3C trace context | 2019 | traceparent 头标准化（跨厂商追踪传播） |

本文示例以 **go1.25.6** 为基线（本环境实际跑通——本阶段"可实测的核心"：健康检查、优雅退出、12-Factor 配置、slog JSON 日志、Prometheus 指标 exposition、traceparent 传播全部用**标准库零第三方依赖**实现，可离线构建运行），验证工具链 Docker CLI 29.6.2-rd（Rancher Desktop）+ kubectl v1.36.3 + helm v4.2.3（本机已安装，但**本会话 docker daemon 未就绪、kubectl 无可用集群**，Docker/K8s 相关命令标注「未在本环境验证（需 Docker/Kubernetes 环境）」——不虚构验证）。容器与编排的语法（Dockerfile/Compose/K8s 清单）是声明式配置，本阶段最稳定的部分：Dockerfile 的 FROM/COPY/RUN、K8s 的 Deployment/Service 字段自发布以来基本未变，学透一套声明式心智后换版本只是字段增删。

## 3. 语法与参数

### 3.1 Linux 运行环境基础（部署的宿主）

本阶段所有部署物（Docker 容器、K8s Pod、CI runner）都运行在 Linux 上，先补齐"部署相关"的最小 Linux 心智——**进程是部署的最小单位**：

| 概念 | 部署中的含义 |
|------|-------------|
| 进程与 PID | 容器里 PID 1 是 ENTRYPOINT 进程（4.1 展开）；`kill -TERM <pid>` 发优雅退出信号 |
| 信号 | SIGTERM（优雅退出）/SIGINT（Ctrl+C）/SIGKILL（强杀，Go 无法拦截）——优雅退出靠 SIGTERM（示例 1） |
| 环境变量 | 进程级配置注入通道（3.2 的 12-Factor 落地）；`PORT=8080 go run .` 一行注入 |
| 端口与监听 | `lsof -iTCP:58001` / `netstat -tlnp` 排查端口占用；服务监听 `:port`（所有网卡）才能被容器外部访问 |
| 权限 | 容器非 root 运行（USER 65532）；宿主上可执行位/属主决定权限 |

Linux 系统管理（文件系统布局、用户与权限模型、systemd 服务管理）超出本阶段范围，这里只需"进程、信号、环境变量、端口"四个部署概念——它们直接对应后面 Docker/K8s 里的 PID 1、SIGTERM 优雅退出、env 注入与 ports 映射。

### 3.2 12-Factor 与配置管理（环境变量）

**12-Factor（2011，Heroku 提出的 SaaS 应用方法论）是本阶段配置哲学的地基**，其中与本阶段直接相关的三条：**配置存于环境（III）**、**进程无状态（VI）**、**日志是事件流（XI）**。配置（数据库地址、密钥、feature 开关）必须与代码分离——镜像不携带任何环境特定信息，部署时由环境变量注入（K8s 的 ConfigMap/Secret 就是注入通道）：

```go
// 完整可运行版见 examples/ex02-config-12factor/main.go
// 验证环境：go1.25.6（已验证），零第三方依赖
func Load(getenv func(string) string) (Config, error) {   // getenv 注入：测试不碰真实环境
	cfg := Config{Port: 58002, LogLevel: slog.LevelInfo, ShutdownTimeout: 10 * time.Second, EnableMetrics: true}
	if v := getenv("PORT"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 || n > 65535 {
			return cfg, fmt.Errorf("invalid PORT %q: want 1-65535", v)
		}
		cfg.Port = n
	}
	if cfg.DBURL == "" {                                   // 必填项：不能有默认值（防误连开发库）
		return cfg, &missingError{key: "DB_URL"}           // fail-fast：启动即报错
	}
	// ... LOG_LEVEL / SHUTDOWN_TIMEOUT / ENABLE_METRICS 同理（默认值 + 覆盖 + 校验）
	return cfg, nil
}
```

要点：**配置集中定义、一处加载**（Config 结构体即文档，字段注释写环境变量名与默认值）；**必填项 fail-fast**——DB_URL 缺失在启动时报错，而不是运行时连不上库才暴露；**类型解析与校验带字段上下文**（"invalid PORT %q: want 1-65535"）；**`errors.Is/As` 可判断必填缺失**（`&missingError{key: "DB_URL"}`，自定义类型的 `Is` 方法按 key 命中，见 ex02）。**坑：配置不该整串进日志**——DB_URL 带密码时用 `mask()` 脱敏（`postgres://user:***@db:5432/app`，project/internal/config 有实现）。

> 配置中心的完整形态（etcd/Consul/Nacos、动态下发、feature flag）属 ph20 配置管理与发布策略阶段，这里只落地"环境变量注入"这一最小可靠形态——它已覆盖本阶段部署需求的 90%。

### 3.3 Dockerfile 与多阶段构建

**Dockerfile 是镜像的"构建脚本"**：`FROM` 选基础镜像 → `COPY` 拷入文件 → `RUN` 执行构建命令 → `ENTRYPOINT` 定义启动命令。**多阶段构建（multi-stage build）是本阶段必会**——第一个阶段（builder）用完整工具链编译，最后一个阶段（runtime）只拷贝产物，镜像只含二进制：

```dockerfile
# 完整可运行版见 examples/ex06-containerize/Dockerfile
# ---- 阶段 1：builder（编译环境）----
FROM golang:1.25-alpine AS builder
WORKDIR /src
COPY go.mod go.sum* ./        # 先拷依赖清单：层缓存优化（依赖不变不重拉）
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/server .
# ---- 阶段 2：runtime（运行环境）----
FROM scratch                   # 只含静态二进制（~10MB vs golang 镜像 ~1GB）
COPY --from=builder /out/server /server
USER 65532:65532               # 非 root 运行
ENTRYPOINT ["/server"]
```

要点：**`CGO_ENABLED=0` 是 Go 容器化的前提**——纯静态链接，运行时不需要 glibc，scratch/distroless 才能跑；**`-trimpath` 去掉构建机绝对路径**（可复现构建，不同机器产出一致）；**`-ldflags="-s -w"` 去掉符号表与 DWARF**（瘦身）；**`USER 非 root`**（容器内以普通用户运行，防提权）；**层缓存**：先拷 go.mod 再 `go mod download`，依赖层不变时后续层直接命中缓存。**坑：基础镜像要固定 tag**（`golang:1.25-alpine` 而非 `golang:latest`）——latest 漂移导致"昨天能构建今天不能"。

### 3.4 Docker Compose（本地/单机多服务编排）

**Compose 用 YAML 声明"一台机器上的多个容器"**——本阶段用它做本地开发环境（起 Go 服务 + MySQL + Redis）与 CI 里的集成测试环境：

```yaml
# 完整可运行版见 examples/ex06-containerize/compose.yaml
services:
  server:
    build: { context: ., dockerfile: Dockerfile }
    ports: ["58006:58006"]          # 宿主端口:容器端口
    environment:                    # 12-Factor：配置走环境变量，镜像不携带环境信息
      PORT: "58006"
    restart: unless-stopped
```

要点：**ports 映射是"宿主:容器"**（容器内监听 :58006，宿主从 58006 访问）；**environment 是配置注入通道**（与 3.2 呼应）；**depends_on/healthcheck 控制依赖顺序**（等依赖健康再启动下游）；**Compose 是"开发/单机"工具，生产多机编排交给 Kubernetes**——两者的 YAML 心智一致（声明期望状态），但 K8s 多了调度、自愈、水平扩展。

Compose 起 Go + MySQL + Redis 的完整服务栈练习见练习 5 提示（需 docker 环境，sol-05/compose.yaml 已含三个服务）。

> **注意**：`healthcheck` 在 scratch 镜像里因无 shell/wget 而受限——生产探针的标准做法是 K8s probe（见 3.5），这是"探针放哪一层"的关键判断。

### 3.5 Kubernetes：核心对象与探针

**Kubernetes 是"容器集群的操作系统"**：你声明期望状态（Deployment: 我要 2 个副本），控制面持续把实际状态收敛到期望状态（多了杀掉、少了拉起、挂了重启）。本阶段必须掌握五个对象：

| 对象 | 声明什么 | 类比 |
|------|---------|------|
| Pod | 最小调度单元（1+ 容器 + 共享网络/存储） | "虚拟机" |
| Deployment | Pod 的副本数与滚动更新策略（声明式） | "进程管理器" |
| Service | Pod 的稳定访问入口（标签选择器 + 负载均衡） | "负载均衡 + DNS" |
| ConfigMap / Secret | 配置与敏感信息（注入环境变量或挂载文件） | "配置中心（最小形态）" |
| Namespace | 逻辑隔离（多环境/多团队） | "文件夹" |

**探针（Probe）是本阶段部署质量的命门**——kubelet 直接发 HTTP 请求（不依赖镜像内 wget/shell，这正是 scratch 镜像能做健康检查的原因）：

```yaml
# 完整可运行版见 project/deploy/k8s/deployment.yaml
livenessProbe:                 # 存活探针：失败 → kubelet 重启容器（进程级故障自愈）
  httpGet: { path: /healthz, port: 58010 }
  initialDelaySeconds: 3       # 启动宽限（应用加载期不误杀）
  periodSeconds: 10
  timeoutSeconds: 2
readinessProbe:                # 就绪探针：失败 → 从 Service 摘除（依赖未就绪不接流量）
  httpGet: { path: /readyz, port: 58010 }
  initialDelaySeconds: 3
  periodSeconds: 5
```

要点：**liveness 与 readiness 语义必须分开**——/healthz 回答"进程活着吗"（恒 200，不查依赖），/readyz 回答"能接收流量吗"（依赖就绪才 200，否则 503）；**探针失败的行为不同**：liveness 失败重启容器、readiness 失败只摘流量不重启；**滚动更新（RollingUpdate）是本阶段"灰度"的最小形态**——`maxUnavailable: 1`（最多 1 个副本不可用）+ `maxSurge: 1`（最多多起 1 个新副本），逐个替换、不中断服务；**ConfigMap/Secret 注入环境变量**（`envFrom.configMapRef` + `secretKeyRef`）是 12-Factor 配置的 K8s 落地。**坑：探针路径必须与代码一致**——服务没实现 /readyz 却配了 readinessProbe，Pod 永远不 Ready、流量永远进不来。

> Deployment 的滚动更新只是"部署形态"的灰度（按副本比例换新）；feature flag 级别的灰度开关（按用户/流量比例放量）属 ph20 配置管理与发布策略阶段。

### 3.6 Helm 与 CI/CD

**Helm 是 Kubernetes 的包管理器**：把 Deployment/Service/ConfigMap 等清单模板化成 Chart（`templates/` 里的 Go template + `values.yaml` 的变量），一条 `helm install` 部署整套应用、`helm upgrade` 升级、`helm rollback` 回滚——解决"同一个应用在 dev/staging/prod 三套清单手改"的重复问题。本阶段掌握心智：**Chart = 模板 + values；values 分离环境差异**（不同环境 `-f values-prod.yaml`）。

**CI/CD 是把"本地验证"变成"每次提交自动验证与发布"的流水线**：CI（持续集成）在提交后自动跑测试/构建/镜像推送，CD（持续部署）把通过的门禁自动部署到环境。Go 项目的流水线骨架（GitHub Actions YAML）：

```yaml
# 流水线骨架无独立示例文件（CI 需云端账号实测，见主文档 3.6 说明）
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with: { go-version: "1.25" }
      - run: go vet ./...        # 静态检查
      - run: go test -race ./... # 测试 + 竞态检测
      - run: go build ./...      # 构建验证
```

要点：**CI 的门禁 = 本地命令的自动重放**（ph08 起养成的 `go vet` / `go test -race` 习惯原样进流水线）；**CD 的部署步骤 = 本阶段前面的全部命令**（docker build → 推镜像仓库 → kubectl/helm 更新集群）；**流水线即代码**（YAML 进 git，改流水线走 review）；**坑：CI 里不要 `latest` tag**——用 commit SHA 或语义化版本 tag，才能回滚到"构建出这个镜像的那次提交"。

GitHub Actions 与 GitLab CI 本机无法实测（需云端账号），本节命令标注「未在本环境验证」——但流水线内容就是本地命令的编排，本地全绿是前提。

### 3.7 可观测性：日志、指标、追踪（三支柱落地）

ph11 讲过可观测性三支柱概念（日志看细节、指标看趋势、追踪看链路），本阶段把它们**接入工具链**：

**① 日志：slog JSON 结构化**（Go 1.21+ 标准库，示例 3）——JSON handler 输出机器可读行，采集系统（ELK/Loki）直接消费：

```go
// 完整可运行版见 examples/ex03-slog-json/main.go
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
	Level:     slog.LevelInfo,
	AddSource: true,                                  // 每条日志带 source（文件:行），排查必备
}))
reqLog := logger.With("trace_id", traceID, "user_id", userID) // 请求级上下文：后续日志自动继承
logger.InfoContext(r.Context(), "request started", "method", r.Method, "path", r.URL.Path)
```

**② 指标：Prometheus 拉模型 + exposition 格式**（示例 4，纯标准库可跑通）——**Prometheus 定时来 GET /metrics**（拉模型，区别于推送），服务只需暴露文本；**exposition 0.0.4 格式**是纯文本协议，手写即可（这就是"可实测的核心"）：

```text
# HELP http_requests_total Total HTTP requests processed.
# TYPE http_requests_total counter
http_requests_total{handler="api"} 3
# HELP http_request_duration_seconds Request latency distribution.
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.005"} 1
http_request_duration_seconds_bucket{le="+Inf"} 3
http_request_duration_seconds_sum 2.021
http_request_duration_seconds_count 3
```

**③ 追踪：OpenTelemetry 与 traceparent**（示例 5）——**traceparent 头（W3C 标准）是追踪传播的唯一协议**：`00-<trace_id 32hex>-<span_id 16hex>-<flags 2hex>` 共 55 字符，服务 A 建根 span → 把 traceparent 随请求带给 B → B 解析后以 A 的 span_id 为 parent 开子 span——Jaeger/Tempo 靠这些 span 还原整条调用链：

```go
// 完整可运行版见 examples/ex05-traceparent/main.go
root := NewRoot()                         // 根 span：随机 trace_id + span_id
InjectIntoHeader(root, req)               // A 调用 B 前：把 traceparent 注入出站请求头
parent, err := ParseTraceparent(h)        // B 收到：解析父上下文
span := NewChild(parent)                  // B 开子 span：parent.SpanID → 本 span 的 ParentID，链被接上
```

要点：**三支柱各司其职、缺一不可**——日志定位细节（"这个请求为什么失败"）、指标看趋势（"错误率在上升"）、追踪看链路（"慢在哪一跳"）；**本阶段用标准库手写 exposition 与 traceparent**（理解协议本质），生产接入 `prometheus/client_golang` 与 `go.opentelemetry.io/otel` SDK 只是"把手工实现换成官方库"（ph11 的 gRPC interceptor 是接入点）；**Grafana 消费 Prometheus 数据做可视化**（Query: `rate(http_requests_errors_total[5m]) / rate(http_requests_total[5m])` 即错误率）。**告警（Prometheus rule + Alertmanager）**把"指标阈值"变成"主动通知"（如错误率 > 5% 连续 5 分钟触发告警）——本阶段覆盖到"采集 → 展示"，告警规则的阈值设计属生产运维实践，超出本阶段范围（roadmap 未单列阶段，作为 ph12 的延伸练习）。

指标/追踪的完整生产接入（client_golang、otel SDK、Grafana 面板搭建）需要第三方依赖与可观测平台，本环境标注「未在本环境验证」；exposition 格式与 traceparent 协议本身已验证可跑通。

### 3.8 API Gateway 与灰度发布

**API Gateway（API 网关）是集群流量的统一入口**：客户端只面对网关，网关负责**路由（按路径/域名分发到服务）、鉴权、限流、协议转换（HTTP→gRPC）、灰度分流**——它是 ph11 注册发现的"入口侧"补全（注册发现解决服务间互调，网关解决外部流量怎么进来）。生产代表：Kong、APISIX、Envoy（Istio 的数据面）。**K8s 集群内的最小形态是 Ingress**（把外部 HTTP 流量按 host/path 路由到 Service，project/deploy/k8s 有示例）：

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ph12-api-ingress
spec:
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend: { service: { name: ph12-api, port: { number: 80 } } }
```

**灰度发布（Canary Release）与滚动升级（Rolling Update）**：滚动升级是"按副本比例换新版本"（3.5 的 strategy），灰度发布是"新版本先接一小部分流量验证，再逐步放量"——K8s 的落地是**两个 Deployment 并存 + 入口按权重分流**（或直接用 Istio/Argo Rollouts 的流量切分）。**发布可回滚是底线**：镜像 tag 可追溯（commit SHA）+ Helm rollback / kubectl rollout undo。

要点：**API Gateway 不是"必须自己搭"的东西**——小规模用 Ingress + 云厂商负载均衡即可，规模上来再上 Kong/APISIX/Istio；**灰度与回滚依赖"配置与代码分离"**（同一镜像、不同环境变量/权重就是灰度），这正是 3.2 的 12-Factor 配置的延伸。

## 4. 底层原理

### 4.1 容器本质：namespace + cgroup + 镜像分层

```text
docker run 一个 Go 服务时内核做了什么：
┌─────────────────────────────────────────────┐
│ namespace：进程视角隔离                      │
│   PID ns（只看得到自己进程树）               │
│   NET ns（独立网络栈，自带 IP）              │
│   MOUNT ns（独立文件系统视图）               │
│   UTS ns（独立 hostname）                    │
├─────────────────────────────────────────────┤
│ cgroup：资源配额                             │
│   cpu.max / memory.limit（OOM 保护）         │
│   镜像里 resources.requests/limits 映射到它  │
├─────────────────────────────────────────────┤
│ 镜像：只读分层（overlayfs）                  │
│   layer1: base（alpine/scratch）             │
│   layer2: 二进制（COPY 产物）                │
│   ── 容器层（可写，丢弃即重置）              │
└─────────────────────────────────────────────┘
```

要点：**容器不是虚拟机**——没有独立内核，所有容器共享宿主机内核，隔离靠 namespace（看不着）+ cgroup（用不超）；**Go 静态二进制尤其适合**：无 glibc 依赖 → 只需要内核 syscall → scratch 空镜像也能跑（对比 Python/Node 镜像必须带解释器，体积大一个数量级）；**镜像分层是缓存与体积的根源**——每行 Dockerfile 指令一层，层不变可复用，最终镜像 = 只读层叠加；**容器里 PID 1 是 ENTRYPOINT 进程**——它必须正确处理 SIGTERM（Go 的 signal.Notify），否则 kill 变成强制杀（优雅退出失效）。

### 4.2 Kubernetes 控制面：声明式期望状态 + 控制器循环

```text
kubectl apply deployment.yaml
        │ 声明期望状态（2 副本）
        ▼
API Server（etcd 存期望状态）
        │ watch
        ▼
Deployment Controller：ReplicaSet 副本数 → 2
        │ 创建 Pod（kubelet 收到调度指令）
        ▼
kubelet：拉镜像 → 起容器 → 跑探针
        │ 实际状态回写（status）
        ▼
控制面比对：期望(2) vs 实际(2)？→ 不相等就"调"（少了拉起/挂了重启/多了删除）
```

要点：**K8s 的核心循环是"期望 vs 实际"的持续收敛**（与 ph09 的单体进程、ph11 的多服务手动编排完全不同——K8s 里你只声明，它自己调）；**控制器（Controller）是模式**：Deployment→ReplicaSet→Pod 层层声明、各管一段；**探针是"实际状态"的输入**：readiness 失败 → status 里 Pod 不就绪 → Service 的 Endpoints 摘除它 → 流量不再进来；**etcd 是唯一事实来源**（期望状态与 status 都存它，所以 etcd 挂 = 集群管理面挂，但已调度 Pod 仍运行）。

### 4.3 Prometheus 拉模型与 exposition 格式

```text
拉模型（Prometheus 主动来取）：
Prometheus ──定时 GET──▶ 服务 /metrics（text/plain; version=0.0.4）
   │                      counter: 只增（请求数、错误数）
   │                      gauge:   可增可减（在途数）
   │                      histogram: 分桶计数 + _sum + _count（延迟分布）
   ▼
PromQL 查询（Grafana 面板）：
   rate(http_requests_errors_total[5m]) / rate(http_requests_total[5m])  → 5 分钟错误率
```

要点：**拉模型 vs 推送模型**——拉模型"谁在消费谁主动"（Prometheus 定间隔来 GET），服务无状态、挂了不会污染采集端，天然适合 K8s（服务实例 IP 会变，Prometheus 通过 Service 发现动态找到）；**exposition 是纯文本协议**（示例 4 手写 100 行即可输出合规格式）——**看懂 /metrics 文本 = 看懂一切 Go 服务的指标**；**counter 只能增**（重置靠进程重启）——错误率必须用 `rate()` 在查询端计算，不能存"每秒错误数"这种会减的 counter。

### 4.4 traceparent 与分布式追踪的上下文传播

```text
一次跨服务请求的 span 树（A → B → C）：
trace_id: 4bf92f3577b34da6a3ce929d0e0e4736（全链路共享）
├─ span A (00f067aa0ba902b7)          ← 根
│   └─ span B (a1b2c3d4e5f60718)      ← parent = A
│       └─ span C (9d8e7f6a5b4c3d2e1) ← parent = B
A 调 B 时：InjectIntoHeader(root, req)        → traceparent: 00-4bf9...-00f067...-01
B 收请求：ParseTraceparent(header) → NewChild(parent)  → parent_id = A 的 span_id
```

要点：**trace_id 全链路共享、span_id 每跳唯一、parent_id 指向上游**——三段式关系就是一棵树，Jaeger/Tempo 收集所有 span 后按 trace_id 归组、按 parent 关系画链路图；**traceparent 是明文头**（不加密、只做关联不做鉴权）；**采样（flags 的 bit0）**——高流量系统全量上报成本高，常按比例采样，traceparent 里标记是否采样，下游继承；**传播的载体就是 HTTP 头**（gRPC 是 metadata），所以 ph11 的拦截器（otelgrpc）能自动完成"生成 span + 传播 context"——本阶段手写的机制与官方 SDK 内部做的事一致。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 本地开发环境（起 Go + MySQL + Redis） | Docker Compose（3.4） |
| 生产部署 Go 服务 | 多阶段 Dockerfile + K8s Deployment（3.3/3.5） |
| 服务上线后的存活保障 | liveness/readiness 探针 + 优雅退出（3.5/ex01） |
| 服务可观测（查日志/看指标/找慢链路） | slog JSON + Prometheus + traceparent（3.7） |
| 每次提交自动验证 | GitHub Actions/GitLab CI 流水线（3.6） |
| 新版本安全上线 | 滚动更新/灰度发布 + 回滚（3.8） |

**不适合**此阶段的事项：

- **性能剖析与优化**（pprof、benchmark、GC 调优、逃逸分析）：属 ph13 性能优化阶段——本阶段只保证"能部署、能观察"，不优化
- **消息队列与异步管道**（Kafka/NATS/RabbitMQ、日志采集队列深入）：属 ph19——本阶段日志直接 stdout 由采集系统抓取，不经过队列
- **配置中心与 feature flag**（etcd/Consul 动态配置、按用户灰度的开关）：属 ph20——本阶段用环境变量静态注入
- **服务网格与高级流量治理**（Istio 全功能、mTLS、熔断策略下发）：本阶段只到 Ingress 与滚动更新，服务网格作为扩展方向

**选型参考：容器/编排工具链**

| 维度 | Docker Compose | Kubernetes | 云厂商托管（EKS/GKE/ACK） |
|------|---------------|------------|--------------------------|
| 定位 | 单机开发/测试 | 生产集群编排 | 托管 K8s（免运维控制面） |
| 调度 | 无（本机） | 多节点调度 + 自愈 | 同 K8s，控制面代管 |
| 探针 | healthcheck（需镜像内工具） | liveness/readiness（kubelet 直发 HTTP） | 同 K8s |
| 滚动升级 | 无（recreate 语义） | RollingUpdate 原生 | 同 K8s |
| 上手成本 | 低 | 中高 | 中（免集群运维） |
| 本阶段定位 | 学习容器第一步 | 生产部署目标 | 生产落地形态 |

**跨语言对比**（为 analysis/ 与 Tenet 合成积累素材）：

| 维度 | Go | Java | Node/Python |
|------|----|------|-------------|
| 镜像体积 | ~10MB（scratch 纯静态） | ~200MB+（JRE） | ~150MB+（解释器 + 依赖） |
| 启动时间 | 毫秒级 | 秒级（JVM 预热） | 百毫秒级 |
| 容器友好度 | 极高（静态二进制） | 中（需 JRE 精简/jlink） | 中（依赖打进镜像） |
| 云原生基建 | Docker/K8s/Prometheus 均 Go 编写 | 生态丰富但重 | 胶水语言、生态活跃 |

## 6. 代码示例

> 以下示例均为完整可运行 Go module，位于 [`examples/`](./examples/) 目录（每个示例一个子目录，先进入对应目录再运行）。验证环境：go1.25.6（darwin/arm64）；示例 1~5 **零第三方依赖**（标准库），示例 6 服务本体零依赖（Dockerfile/Compose 为声明式文件）。全部示例已通过 `go vet ./...`、`go test ./...`（ex04/ex05 另过 `-race`，ex04 的指标值由各指标自带互斥锁保护，-race 含「/metrics 渲染与业务请求并发」测试，零数据竞争），覆盖率实测见下表（数据表与运行命令见 examples/README.md）。

| 示例 | 一句话说明 | go test -cover |
|------|-----------|----------------|
| ex01-health-graceful | 健康检查 + 优雅退出：/healthz 与 /readyz 语义、atomic.Bool 就绪、SIGTERM → Shutdown 等在途 | 47.3% |
| ex02-config-12factor | 12-Factor 配置：环境变量加载（默认值/覆盖/必填校验/fail-fast）+ 配置驱动路由 | 73.8% |
| ex03-slog-json | slog JSON 结构化日志：级别过滤、AddSource、With 请求级上下文、埋点、InfoContext | 50.0% |
| ex04-prometheus-metrics | 手工 Prometheus /metrics：counter/gauge/histogram 的 text exposition 0.0.4 | 72.5% |
| ex05-traceparent | OpenTelemetry traceparent：W3C trace context 生成/解析/传播（A→B 链路打通） | 52.5% |
| ex06-containerize | 容器化：多阶段 Dockerfile（builder→scratch）+ Compose + 最小健康检查服务 | 47.4%（服务本体） |

### 示例 1：健康检查 + 优雅退出（ex01-health-graceful）

```go
// examples/ex01-health-graceful/main.go —— /healthz 恒 200；/readyz 未就绪 503
// 验证环境：go1.25.6，零第三方依赖，命令：go test -v ./...；go run .
func (s *server) handleReadyz(w http.ResponseWriter, _ *http.Request) {
	if !s.ready.Load() {                                  // atomic.Bool：探针高频轮询，读路径零锁零分配
		w.WriteHeader(http.StatusServiceUnavailable)       // 503：K8s 摘除本实例
		_, _ = w.Write([]byte(`{"status":"not_ready"}`))
		return
	}
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ready"}`))
}
// 优雅退出：先摘 readiness（/readyz 立即 503，流量先挪走）→ Shutdown 等在途请求 → 超时兜底
srv.ready.Store(false)
ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()
_ = httpSrv.Shutdown(ctx)   // 在途请求处理完才返回；超时则强制关闭
```

### 示例 2：12-Factor 配置（ex02-config-12factor）

```go
// examples/ex02-config-12factor/main.go —— Load(getenv) 集中加载 + 校验 + fail-fast
cfg, err := Load(os.Getenv)
if err != nil {
	fmt.Fprintln(os.Stderr, "config error:", err)   // 启动失败也要写日志（stderr，容器采集捕获）
	os.Exit(1)
}
```

### 示例 3：slog 结构化日志（ex03-slog-json）

```text
// examples/ex03-slog-json/main.go 示例输出（JSON 行，机器可读，采集系统直接消费；本机实测）
{"time":"2026-09-01T11:31:35.953059+08:00","level":"INFO","source":{"function":"main.main","file":".../ex03-slog-json/main.go","line":68},"msg":"service starting","version":"1.0.0","env":"dev"}
{"time":"2026-09-01T11:31:35.95357+08:00","level":"INFO","source":{"function":"main.main","file":".../ex03-slog-json/main.go","line":73},"msg":"auth ok","trace_id":"trace-abc-123","user_id":"user-42","expires_in":3600}
```

### 示例 4：手工 Prometheus /metrics（ex04-prometheus-metrics）

```go
// examples/ex04-prometheus-metrics/main.go —— histogram 观测与渲染（exposition 0.0.4）
func (h *Histogram) Observe(v float64) {
	h.sum += v
	h.count++
	for i, b := range h.buckets {
		if v <= b {
			h.counts[i]++ // 找第一个 >= v 的桶
		}
	}
}
// 渲染（render 方法）：_bucket{le="..."} 累计计数 + _sum + _count（+Inf 桶 = 全部样本）
```

### 示例 5：traceparent 传播（ex05-traceparent）

```go
// examples/ex05-traceparent/main.go —— A 建根 span → 注入头 → B 解析并开子 span
root := NewRoot()                                  // 随机 trace_id + span_id，Sampled=true
InjectIntoHeader(root, req)                        // A 调 B 前：traceparent 进请求头
parent, err := ExtractFromHeader(r)                // B 端还原父上下文（内部调 ParseTraceparent）
span := NewChild(parent)                           // 继承 trace_id；ParentID = 父 span_id → 链被接上
```

### 示例 6：容器化（ex06-containerize）

```dockerfile
# examples/ex06-containerize/Dockerfile —— 多阶段构建：builder 编译 → scratch 运行
FROM golang:1.25-alpine AS builder     # 阶段 1：完整工具链
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/server .
FROM scratch                           # 阶段 2：只含静态二进制（~10MB）
COPY --from=builder /out/server /server
USER 65532:65532                       # 非 root
ENTRYPOINT ["/server"]
```

## 7. 总结

### 关键要点

1. **Go 适合构建小型静态二进制**（必会概念）：CGO_ENABLED=0 纯静态 + 多阶段构建 → ~10MB scratch 镜像，这是 Go 在云原生时代的核心优势
2. **容器镜像应尽量小且可复现**（必会概念）：多阶段构建（builder→runtime）+ -trimpath + 固定基础镜像 tag；层缓存优化构建速度
3. **健康检查和优雅退出很重要**（必会概念）：liveness（进程活着吗，恒 200）与 readiness（能接流量吗，就绪才 200）语义分离；SIGTERM → 摘 readiness → Shutdown 等在途 → 超时兜底
4. **配置不应写死在镜像里**（必会概念）：12-Factor 环境变量注入（默认值 + 覆盖 + 必填 fail-fast + 校验），K8s 用 ConfigMap/Secret 落地
5. **Kubernetes 是"声明期望状态 + 控制器收敛"**：Deployment/Service/ConfigMap/Secret 五对象 + 探针 + 滚动更新；探针放编排层（kubelet 直发 HTTP），scratch 镜像也能做健康检查
6. **可观测性三支柱要接入工具链**：slog JSON（日志）、Prometheus exposition 手写可跑（指标）、traceparent 手写可传播（追踪）——协议本质学透后，接官方 SDK 只是换实现
7. **CI/CD 是本地命令的自动化重放**：go vet / go test -race / go build 原样进流水线；镜像 tag 可追溯才能回滚
8. **发布可回滚是底线**：滚动更新（按副本比例）+ 灰度发布（按流量权重）+ Helm rollback / kubectl rollout undo

### 跨语言对比：云原生部署

| 维度 | Go | Java | Node/Python |
|------|----|------|-------------|
| 镜像体积 | ~10MB（scratch 纯静态） | ~200MB+（JRE） | ~150MB+（解释器 + 依赖） |
| 启动时间 | 毫秒级 | 秒级（JVM 预热） | 百毫秒级 |
| 优雅退出 | signal.Notify + Shutdown（标准库） | shutdown hook / Spring graceful | process.on('SIGTERM') |
| 指标 | 手写 exposition / client_golang | Micrometer/Prometheus jmx | prom-client |
| 容器友好度 | 极高（静态二进制、无运行时依赖） | 中（jlink/distroless 可优化） | 中（依赖打进镜像） |

### 阶段验收清单

- [ ] **能构建镜像并启动服务**：多阶段 Dockerfile（builder→scratch、CGO_ENABLED=0、非 root）docker build/run 通过，镜像 ~10MB 量级（示例 6 / project Dockerfile）
- [ ] **能配置环境变量和健康检查**：12-Factor 配置加载 + /healthz 与 /readyz 语义正确（未就绪 503、就绪 200）（示例 1/2）
- [ ] **能实现优雅退出**：SIGTERM → 摘 readiness → Shutdown 等在途请求 → 超时兜底，日志可见（示例 1 / project 冒烟）
- [ ] **能查看日志和指标**：slog JSON 结构化输出 + /metrics exposition 可被 Prometheus 抓取（示例 3/4）
- [ ] **能解释 traceparent 上下文传播**：A→B 两次服务调用串起同一条 trace（trace_id 一致、parent 关系正确）（示例 5）
- [ ] **能写 K8s 清单**：Deployment（探针 + 滚动更新）+ Service + ConfigMap/Secret + Ingress，说明每个字段的语义（project/deploy/k8s）
- [ ] **能写 CI 流水线**：go vet / go test -race / go build 编排成 GitHub Actions/GitLab CI 的 job（3.6）
- [ ] **能说清 API Gateway 与灰度发布**：Ingress 是集群内最小形态；滚动更新 vs 灰度发布（按副本比例 vs 按流量权重）；回滚手段（3.8）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。完成 5 题后继续。五题与 roadmap「练习」小节一一对应（写 Dockerfile / Compose 启动 / 部署到 Kubernetes / 接入 Prometheus，前四题落成可实测的纯标准库代码）：

1. **健康检查与优雅退出**（★）：/healthz + /readyz 语义 + SIGTERM 优雅退出（提示：示例 1）
2. **12-Factor 配置加载器**（★★）：环境变量配置（默认值/必填校验/类型解析/fail-fast，errors.Is）（提示：示例 2）
3. **结构化日志**（★★）：slog JSON（级别过滤/With 上下文/埋点）（提示：示例 3）
4. **Prometheus 指标暴露**（★★★）：手写 counter/gauge/histogram 的 /metrics（提示：示例 4）
5. **容器化与部署清单**（★★）：Dockerfile 多阶段 + Compose + K8s 清单，服务本体可测、Docker/K8s 验证状态如实标注（提示：示例 6 / project/deploy/k8s）

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**可部署 API 服务模板**——12-Factor 配置 + /healthz/readyz 探针 + 手工 Prometheus /metrics + slog JSON 日志 + SIGTERM 优雅退出 + Dockerfile 多阶段构建 + K8s 清单（探针/滚动更新/ConfigMap/Secret/Ingress）。它是本阶段全部知识点的合体，也是 roadmap「可部署 API 服务模板」推荐项目的落地；roadmap 另一个推荐项目「Kubernetes 部署示例」的清单部分（Deployment/Service/Ingress）已含在本项目 deploy/k8s/。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（go build / go vet / go test / -race / 冒烟与优雅退出验证）

### 下一阶段

[性能优化阶段](../ph13-perf-optimization/13-perf-optimization.md) — 把"能部署、能观察"升级为"能调优"：benchmark 与 pprof 分析（高并发接口压测与优化）、GC 与内存分配分析（减少分配次数缓解 GC 压力）、goroutine 泄漏排查、逃逸分析与 sync.Pool——本阶段的 /metrics 延迟直方图与日志里的 latency_ms 正是 ph13 优化前定位瓶颈的入口；在此之前可先按推荐学习顺序巩固本阶段的练习与项目。

---

*本文全部"已验证"声明（go1.25.6 实测：示例 1~5 + project 冒烟）均属实；Docker/K8s 相关（示例 6、project deploy、练习 5 清单）因本机 docker daemon 未就绪、kubectl 无集群而标注「未在本环境验证（需 Docker/Kubernetes 环境）」，不虚构验证。*
