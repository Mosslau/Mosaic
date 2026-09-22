#!/usr/bin/env bash
# 重新生成 proto 代码（pb 文件已提交，日常构建无需执行）
set -euo pipefail
cd "$(dirname "$0")"
protoc \
  --go_out=. --go_opt=paths=source_relative \
  --go-grpc_out=. --go-grpc_opt=paths=source_relative \
  proto/comm.proto
echo "已生成: proto/comm.pb.go 与 proto/comm_grpc.pb.go"
