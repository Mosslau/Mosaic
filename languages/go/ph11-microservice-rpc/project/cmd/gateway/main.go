// 采集网关：从注册中心发现设备服务实例 → 轮询负载均衡 → 带超时/熔断/重试地上报设备状态，
// 然后查询最新状态。每轮报告前 Refresh 一次（重新发现实例，轮询位置从新列表开始）。
//
// 运行：go run ./cmd/gateway -registry 127.0.0.1:54001 -rounds 3
package main

import (
	"flag"
	"fmt"
	"log"
	"time"

	"tenetlang/go/ph11-microservice-rpc/project/internal/device"
	"tenetlang/go/ph11-microservice-rpc/project/internal/registry"
)

func main() {
	regAddr := flag.String("registry", "127.0.0.1:54001", "注册中心地址")
	rounds := flag.Int("rounds", 3, "演示轮数（每轮上报 3 个设备）")
	flag.Parse()

	reg, err := registry.Dial(*regAddr)
	if err != nil {
		log.Fatalf("连接注册中心 %s 失败: %v", *regAddr, err)
	}
	defer reg.Close()

	// 弹性客户端：超时 1s、瞬时失败重试 2 次
	client := device.NewClient(reg, time.Second, 2)

	for round := 1; round <= *rounds; round++ {
		if err := client.Refresh(); err != nil {
			log.Fatalf("Refresh 失败: %v", err)
		}
		instances, _ := reg.Discover(device.ServiceName)
		fmt.Printf("轮次 %d：发现 %d 个设备服务实例 %v\n", round, len(instances), instances)

		for _, devID := range []string{"car-001", "car-002", "car-003"} {
			st := &device.Status{DeviceID: devID, Speed: float64(60 + round*5), Ts: time.Now().Unix()}
			if err := client.Report(st); err != nil {
				fmt.Printf("  上报 %s -> 失败: %v\n", devID, err)
				continue
			}
			fmt.Printf("  上报 %s -> ok\n", devID)
		}
		time.Sleep(300 * time.Millisecond)
	}

	// 服务间查询演示：状态被 LB 分摊到各实例（无共享存储），跨实例汇总查询
	// （单实例 GetStatus 也可能命中"没收到该设备上报"的实例，这正是无共享存储的代价）
	results, err := client.GetAll("car-001")
	if err != nil {
		log.Printf("GetAll(car-001) 失败: %v", err)
		return
	}
	for _, r := range results {
		fmt.Printf("查询 car-001 -> %s 上最新状态: speed=%.0f ts=%d\n", r.Addr, r.Status.Speed, r.Status.Ts)
	}
}
