# ph12 示例 6 —— Go 多阶段构建 Dockerfile
# 设计要点（对应主文档 3.3 节）：
#  1. 多阶段：builder 阶段带完整 Go 工具链编译，runtime 阶段只复制静态二进制——镜像只含
#     二进制 + 最小 CA 证书，体积从 ~1GB（golang 基础镜像）降到 ~10MB 量级
#  2. CGO_ENABLED=0：纯静态链接，运行时无需 glibc（scratch/distroless 可跑）
#  3. 用 git rev-parse 注入构建信息（vcs 标签，go build -vcs 或 ldflags 注入版本）
#  4. HEALTHCHECK 与 K8s liveness probe 共用 /healthz（语义见示例 1）
# 验证状态：本机 docker daemon 可用时执行 docker build 实测（记录见 examples/README.md）；
#           未验证则按 README 说明标注

# ---- 阶段 1：builder（编译环境）----
FROM golang:1.25-alpine AS builder
WORKDIR /src

# 先只拷贝 go.mod 再 go mod download：利用 Docker 层缓存——依赖层不变就不重拉。
# 本模块零第三方依赖、无 go.sum，所以只 COPY go.mod（写 go.sum* 会因 glob 匹配零文件导致 build 失败）
COPY go.mod ./
RUN go mod download

COPY . .
# -trimpath 去掉构建机绝对路径（可复现构建）；-ldflags 注入版本信息
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/server .

# ---- 阶段 2：runtime（运行环境）----
# 方案 A：scratch（最瘦，无 shell、无调试工具，最适合纯静态 Go 服务）
FROM scratch
# 方案 B：distroless（gcr.io/distroless/static-debian12，带 ca-certificates 与 /etc/passwd，
#          需要 HTTPS 出站（调外部 API）时用它；此处为教学展示 scratch）
# 需要 CA 证书时取消下行注释并删除 scratch 行：
# FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /out/server /server
# 非 root 运行：scratch 无用户表，用 USER 数字 uid（distroless:nonroot 已内置 65532）
USER 65532:65532

EXPOSE 58006
# 健康探针放编排层（compose.yaml 的 healthcheck / K8s 的 livenessProbe）：
# scratch 镜像没有 shell 与 wget/curl，Dockerfile 内嵌 HEALTHCHECK 需要镜像自带探针工具
# 或二进制实现自检子命令（如 /server check），本示例把探针写在编排清单里演示。

ENTRYPOINT ["/server"]
