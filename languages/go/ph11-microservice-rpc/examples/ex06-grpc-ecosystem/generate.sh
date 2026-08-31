#!/usr/bin/env bash
# 重新生成 proto 代码（本示例的 pb 文件已提交，日常构建无需执行本脚本）
# 验证环境：protoc 29.3 + protoc-gen-go v1.36.6 + protoc-gen-go-grpc v1.5.1（本机实测通过）
# 安装插件：go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.6 \
#           go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
set -euo pipefail
cd "$(dirname "$0")"
protoc \
  --go_out=. --go_opt=paths=source_relative \
  --go-grpc_out=. --go-grpc_opt=paths=source_relative \
  proto/user.proto
echo "已生成: proto/user.pb.go 与 proto/user_grpc.pb.go"
