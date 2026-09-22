# ph12 阶段项目 —— 可部署 API 服务模板（Dockerfile 多阶段构建）
# 构建：docker build -t ph12-api:latest .
# 运行：docker run --rm -p 58010:58010 -e DB_URL=postgres://u:p@db/app ph12-api:latest
# 验证状态：本机有 docker daemon 时实测；无则标注「未在本环境验证（需 Docker 环境）」

# ---- 阶段 1：builder ----
FROM golang:1.25-alpine AS builder
WORKDIR /src
# 先拷贝依赖清单：层缓存——依赖不变时后续层不重构建。
# 本模块零第三方依赖、无 go.sum，所以只 COPY go.mod（写 go.sum* 会因 glob 匹配零文件导致 build 失败）
COPY go.mod ./
RUN go mod download
COPY . .
# CGO_ENABLED=0 纯静态链接；GOOS=linux 交叉编译；-trimpath 可复现；-s -w 去符号瘦身
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/api ./cmd/api

# ---- 阶段 2：runtime（scratch：只含静态二进制 + 运行用户）----
FROM scratch
COPY --from=builder /out/api /api
USER 65532:65532
EXPOSE 58010
# 探针在 K8s 清单（deploy/k8s/deployment.yaml）：kubelet 直接发 HTTP 请求，
# scratch 镜像无需 shell/wget——这是"探针放编排层"的标准做法
ENTRYPOINT ["/api"]
