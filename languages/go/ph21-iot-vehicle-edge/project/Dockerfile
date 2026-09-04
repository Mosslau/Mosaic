# 来源：ph21-iot-vehicle-edge project/Dockerfile
# 多阶段构建：镜像里只留平台二进制（Go 静态二进制哲学，主文档 ph12）。
# 未在本环境验证：本机无 Docker，命令可复现——在有 Docker 的机器上：
#   docker build -t edge-platform .
#   docker run --rm -p 8080:8080 -e GATEWAY_SECRETS=edge-001=dev-secret-1 edge-platform
FROM golang:1.25 AS builder
WORKDIR /app
COPY go.mod ./
COPY . .
ARG VERSION=dev
ARG COMMIT=none
ARG BUILDTIME=unknown
RUN CGO_ENABLED=0 go build -trimpath \
    -ldflags "-X tenetlang/go/ph21-iot-vehicle-edge/project/internal/version.Version=${VERSION} \
              -X tenetlang/go/ph21-iot-vehicle-edge/project/internal/version.Commit=${COMMIT} \
              -X tenetlang/go/ph21-iot-vehicle-edge/project/internal/version.BuildTime=${BUILDTIME}" \
    -o /edge-platform ./cmd/platform

FROM scratch
COPY --from=builder /edge-platform /edge-platform
EXPOSE 8080
ENV PLATFORM_ADDR=:8080
ENTRYPOINT ["/edge-platform"]
