// 注册中心进程：把 internal/registry 作为独立 JSON-RPC 服务运行，
// 供设备服务实例登记/心跳、网关发现（对应生产 etcd/Consul/Nacos）。
//
// 运行：go run ./cmd/registry -addr 127.0.0.1:54001 -ttl 5s
package main

import (
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"tenetlang/go/ph11-microservice-rpc/project/internal/registry"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:54001", "注册中心监听地址")
	ttl := flag.Duration("ttl", 5*time.Second, "心跳有效期（超时未心跳的实例自动摘除）")
	flag.Parse()

	realAddr, stop, err := registry.ServeTCP(*addr, *ttl)
	if err != nil {
		log.Fatalf("启动注册中心失败: %v", err)
	}
	log.Printf("注册中心已启动: %s（心跳 TTL %v）", realAddr, *ttl)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	<-sig
	stop()
	log.Println("注册中心已停止")
}
