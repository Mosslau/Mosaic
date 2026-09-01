# ph12 练习 5 —— Dockerfile（多阶段构建，与 examples/ex06 同构）
# 在 sol-05-containerize/ 目录执行：docker build -t sol05:latest .
# 验证状态：本机有 docker daemon 时实测；无则标注「未在本环境验证（需 Docker 环境）」

# 阶段 1：builder —— 编译（带完整 Go 工具链，层缓存优化：依赖不变不重拉）
FROM golang:1.25-alpine AS builder
WORKDIR /src
COPY service/go.mod service/go.sum* ./
RUN go mod download
COPY service/ ./
# CGO_ENABLED=0：纯静态链接，scratch 可跑；-trimpath 可复现；-ldflags -s -w 瘦身
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/server .

# 阶段 2：runtime —— 只含静态二进制（~10MB 量级 vs golang 镜像 ~1GB）
FROM scratch
COPY --from=builder /out/server /server
USER 65532:65532
EXPOSE 59005
# 探针放编排层（compose/K8s），不放 Dockerfile HEALTHCHECK：scratch 无 shell/wget
ENTRYPOINT ["/server"]
