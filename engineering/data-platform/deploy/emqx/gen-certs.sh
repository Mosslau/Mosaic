#!/usr/bin/env bash
# gen-certs.sh — 生成 OceanVerse 本地联调用自签 CA + EMQX 服务器证书
# 仅用于本地开发! 生产用车企 CA 或正式 CA 签发(设计文档 §8.2)。
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p certs

DAYS=3650
# SAN 覆盖三种访问形态: 宿主机直连 / 容器间 / webhook 调试
SAN="DNS:localhost,DNS:emqx,DNS:ov-emqx,DNS:host.docker.internal,DNS:host.lima.internal,IP:127.0.0.1"

if [ ! -f certs/ca.crt ]; then
  # ① 自签 CA
  openssl req -x509 -newkey rsa:2048 -nodes -days $DAYS \
    -keyout certs/ca.key -out certs/ca.crt \
    -subj "/CN=OceanVerse-Dev-CA/O=OceanVerse/C=CN"
  echo "✅ CA 生成"
fi

# ② 服务器证书(用 CA 签发)
openssl req -newkey rsa:2048 -nodes \
  -keyout certs/server.key -out certs/server.csr \
  -subj "/CN=emqx/O=OceanVerse/C=CN"

openssl x509 -req -days $DAYS \
  -in certs/server.csr -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
  -out certs/server.crt -extfile <(printf "subjectAltName=%s" "$SAN")

rm -f certs/server.csr certs/ca.srl
chmod 600 certs/*.key
echo "✅ 服务器证书生成: certs/{ca.crt,server.crt,server.key}"
echo "   校验: openssl verify -CAfile certs/ca.crt certs/server.crt"
openssl verify -CAfile certs/ca.crt certs/server.crt
