# syntax=docker/dockerfile:1
# 车端接入网关镜像: 多阶段构建, 最终产物为静态二进制 + CA 证书

FROM golang:1.25-alpine AS build
WORKDIR /src
# 先拷 go.mod/go.sum 利用层缓存(依赖不变则跳过下载)
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/device-gateway ./cmd/server

FROM alpine:3.21
RUN apk add --no-cache ca-certificates tzdata
COPY --from=build /out/device-gateway /usr/local/bin/device-gateway
EXPOSE 8080
# 全部配置走环境变量, 见 README 配置表
ENTRYPOINT ["device-gateway"]
