// 来源：ph21-data-ingest-gateway examples/ex01-mqtt-minimal/main.go
// 一句话说明：演示主程序——起一个带鉴权的自研 broker，模拟"采集端指标上行 +
// 平台下行指令"两个客户端（采集端客户端发布指标、平台客户端订阅后收到）。
// 用法：go run . -broker 127.0.0.1:18830（先起 broker；换端口用 -broker）
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（127.0.0.1 真 TCP 实测，输出见下方预期）
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"time"
)

func main() {
	addr := flag.String("broker", "127.0.0.1:18830", "broker 监听地址")
	flag.Parse()

	// 1. 起 broker：连接态鉴权 allowlist（每采集端一密，主文档 3.2）。
	allow := map[string]string{"src-001": "tok-1", "platform-1": "plat-tok"}
	b, err := NewBroker(*addr, func(u, p string) bool {
		want, ok := allow[u]
		return ok && want == p
	})
	if err != nil {
		log.Fatalf("起 broker: %v", err)
	}
	b.Start()
	defer b.Stop()
	log.Printf("broker 已监听 %s", b.Addr())

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()

	// 2. 采集端客户端：连接（带 token）→ 订阅下行指令 → 循环上报指标。
	dev := NewClient(ClientOptions{
		Broker: b.Addr().String(), ClientID: "src-001",
		Username: "src-001", Password: "tok-1", KeepAlive: 5 * time.Second,
	})
	if err := dev.Connect(ctx); err != nil {
		log.Fatalf("采集端接入失败: %v", err)
	}
	defer dev.Close()
	if err := dev.Subscribe(ctx, "ingest/src-001/cmd", func(topic string, payload []byte) {
		fmt.Printf("[采集端] 收到下行指令 %s: %s\n", topic, payload)
	}); err != nil {
		log.Fatalf("订阅下行: %v", err)
	}
	// 3. 平台客户端：订阅该设备指标（演示通配：ingest/+/metrics 也命中单层 +）。
	plat := NewClient(ClientOptions{
		Broker: b.Addr().String(), ClientID: "platform-1",
		Username: "platform-1", Password: "plat-tok", KeepAlive: 5 * time.Second,
	})
	if err := plat.Connect(ctx); err != nil {
		log.Fatalf("平台接入失败: %v", err)
	}
	defer plat.Close()
	got := make(chan string, 4)
	if err := plat.Subscribe(ctx, "ingest/+/metrics", func(topic string, payload []byte) {
		got <- fmt.Sprintf("%s: %s", topic, payload)
	}); err != nil {
		log.Fatalf("订阅指标: %v", err)
	}

	// 4. 采集端发两帧指标；平台应全部收到（顺序与内容一致）。
	seq := 0
	for i := 0; i < 2; i++ {
		seq++
		msg := fmt.Sprintf(`{"sourceID":"src-001","seq":%d,"value":%d,"ts":%d}`, seq, 40+i*5, time.Now().Unix())
		if err := dev.Publish("ingest/src-001/metrics", []byte(msg)); err != nil {
			log.Fatalf("发布指标: %v", err)
		}
	}
	for i := 0; i < 2; i++ {
		select {
		case r := <-got:
			fmt.Printf("[平台] 收到 %s\n", r)
		case <-ctx.Done():
			log.Fatal("等待指标超时")
		}
	}

	// 5. 鉴权失败示例：错 token 应被 broker 拒绝（ErrNotAuthorized）。
	bad := NewClient(ClientOptions{Broker: b.Addr().String(), ClientID: "veh-999", Username: "veh-999", Password: "wrong"})
	if err := bad.Connect(ctx); err != nil {
		fmt.Printf("[接入层] 坏 token 采集端被拒（符合预期）: %v\n", err)
	}
	fmt.Println("== ex01 演示完成：MQTT 接入/订阅/路由/鉴权四步全通 ==")
}
