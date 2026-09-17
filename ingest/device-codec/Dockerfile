# syntax=docker/dockerfile:1
# device-codec 编解码服务镜像(上行): 无端口, 纯 Kafka 消费/生产
#
# ⚠️ 构建上下文必须是**仓库根**:
#     docker build -f ingest/device-codec/Dockerfile -t oceanverse/device-codec:dev .

FROM golang:1.25-alpine AS build
WORKDIR /src

# 国内构建必备: 默认走 goproxy.cn, 可 --build-arg GOPROXY=... 覆盖
ARG GOPROXY=https://goproxy.cn,direct
ENV GOPROXY=${GOPROXY}

COPY ingest/device-contracts/ ingest/device-contracts/
COPY ingest/device-codec/go.mod ingest/device-codec/go.sum ingest/device-codec/
RUN cd ingest/device-codec && go mod download

COPY ingest/device-codec/ ingest/device-codec/
RUN cd ingest/device-codec && CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/device-codec ./cmd/server

FROM alpine:3.21
RUN apk add --no-cache ca-certificates tzdata
COPY --from=build /out/device-codec /usr/local/bin/device-codec
# 无监听端口: 输入/输出都是 Kafka topic(CODEC_SRC_TOPIC / CODEC_DST_TOPIC / CODEC_DLQ_TOPIC)
ENTRYPOINT ["device-codec"]
