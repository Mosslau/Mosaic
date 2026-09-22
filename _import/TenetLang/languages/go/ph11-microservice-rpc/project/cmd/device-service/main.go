// 设备管理服务实例：启动时向注册中心登记并周期心跳，提供设备状态上报（限流）与查询，
// 收到退出信号时优雅下线（Deregister 后关闭监听）。
// 可同时起多个实例（不同 -addr）验证负载均衡。
//
// 运行：go run ./cmd/device-service -addr 127.0.0.1:53051 -registry 127.0.0.1:54001
package main

import (
	"flag"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"tenetlang/go/ph11-microservice-rpc/project/internal/device"
	"tenetlang/go/ph11-microservice-rpc/project/internal/registry"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:53051", "本服务监听地址")
	regAddr := flag.String("registry", "127.0.0.1:54001", "注册中心地址")
	rate := flag.Int64("rate", 100, "上报限流（次/秒）")
	flag.Parse()

	reg, err := registry.Dial(*regAddr)
	if err != nil {
		log.Fatalf("连接注册中心 %s 失败: %v", *regAddr, err)
	}
	defer reg.Close()

	lis, err := net.Listen("tcp", *addr)
	if err != nil {
		log.Fatalf("监听 %s 失败: %v", *addr, err)
	}

	// ① 登记 + 心跳（每 1s 一次 << TTL 5s）
	if err := reg.Register(device.ServiceName, *addr); err != nil {
		log.Fatalf("注册失败: %v", err)
	}
	hbStop := make(chan struct{})
	go func() {
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				if err := reg.Heartbeat(device.ServiceName, *addr); err != nil {
					log.Printf("心跳失败: %v", err)
				}
			case <-hbStop:
				return
			}
		}
	}()
	log.Printf("设备服务已注册: %s -> %s（限流 %d 次/秒）", device.ServiceName, *addr, *rate)

	// ② 服务主体
	svc := device.NewServer(*rate, time.Second)
	go func() {
		for {
			conn, err := lis.Accept()
			if err != nil {
				return
			}
			go svc.ServeConn(conn)
		}
	}()

	// ③ 优雅下线
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	<-sig
	log.Println("收到退出信号，注销服务并关闭监听")
	if err := reg.Deregister(device.ServiceName, *addr); err != nil {
		log.Printf("注销失败: %v", err)
	}
	close(hbStop)
	lis.Close()
	log.Println("设备服务已退出")
}
