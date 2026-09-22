# syntax=docker/dockerfile:1
# 车端接入网关镜像: 多阶段构建, 最终产物为静态二进制 + CA 证书
#
# ⚠️ 构建上下文必须是**仓库根**(契约模块在 ingest/device-contracts, go.mod 的 replace 指过去):
#     docker build -f ingest/device-gateway/Dockerfile -t oceanverse/device-gateway:dev .
#   (历史写法——在模块目录内 `docker build .`——在契约拆分后失效:
#    replace ../device-contracts 落在构建上下文之外, 会报 replacement directory does not exist)

FROM golang:1.25-alpine AS build
WORKDIR /src

# 国内构建必备: 默认走 goproxy.cn(与 README「Go 模块代理」一致), 可 --build-arg GOPROXY=... 覆盖
ARG GOPROXY=https://goproxy.cn,direct
ENV GOPROXY=${GOPROXY}

# 先拷 go.mod + 被 replace 的契约模块, 吃满层缓存(依赖与契约不变则跳过下载)
COPY ingest/device-contracts/ ingest/device-contracts/
COPY ingest/device-gateway/go.mod ingest/device-gateway/go.sum ingest/device-gateway/
RUN cd ingest/device-gateway && go mod download

COPY ingest/device-gateway/ ingest/device-gateway/
RUN cd ingest/device-gateway && CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/device-gateway ./cmd/server

FROM alpine:3.21
RUN apk add --no-cache ca-certificates tzdata
COPY --from=build /out/device-gateway /usr/local/bin/device-gateway
EXPOSE 8080 18081
# 全部配置走环境变量, 见 README 配置表(本机开发常用 GATEWAY_PORT=18080)
ENTRYPOINT ["device-gateway"]
