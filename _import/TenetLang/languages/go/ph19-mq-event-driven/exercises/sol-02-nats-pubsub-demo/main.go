// 来源：ph19-mq-event-driven exercises/sol-02-nats-pubsub-demo（练习 2 参考实现）
// 一句话说明：main —— 离线 NATS 三连：通配订阅接收遥测、队列组分摊任务、
// 请求-应答查电量。roadmap §19 练习 2「NATS 发布订阅 demo」落地。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"context"
	"fmt"
	"time"
)

func main() {
	b := NewBroker()
	// subject 均为合法值，Subscribe/Publish 不会返回错误（真实工程请检查 error；
	// 演示省略以保持主线清晰——注释即文档，不偷偷吞错误）。
	pub := func(subject string, data []byte) {
		_ = b.Publish(subject, data)
	}

	// 1. 发布-订阅：两个消费者订阅不同粒度的模式，各收各的。
	fleetWide, _ := b.Subscribe("fleet.>", "")           // 收全部
	carOnly, _ := b.Subscribe("fleet.car-001.>", "")     // 只收 car-001
	telemetry, _ := b.Subscribe("fleet.*.telemetry", "") // 所有车的遥测

	fmt.Println("== 发布-订阅（subject 通配）==")
	pub("fleet.car-001.telemetry", []byte("speed=50"))
	pub("fleet.car-002.telemetry", []byte("speed=70"))
	pub("fleet.car-001.gps", []byte("lat=31.2"))
	fmt.Printf("   fleetWide 收到 %d 条；carOnly 收到 %d 条；telemetry 收到 %d 条\n",
		drainCount(fleetWide), drainCount(carOnly), drainCount(telemetry))

	// 2. 队列组：同一队列多个 worker，任务轮询分摊。
	w1, _ := b.Subscribe("job.dispatch", "workers")
	w2, _ := b.Subscribe("job.dispatch", "workers")
	fmt.Println("== 队列组（job.dispatch, 队列 workers）==")
	for i := 0; i < 4; i++ {
		pub("job.dispatch", []byte(fmt.Sprintf("task-%d", i)))
	}
	fmt.Printf("   w1 接 %d 个任务，w2 接 %d 个任务（共 4 个，轮询分摊）\n",
		drainCount(w1), drainCount(w2))

	// 3. 请求-应答：客户端向 "device.battery" 请求，服务端回执。
	srv, _ := b.Subscribe("device.battery", "")
	go func() {
		for m := range srv.Ch {
			_ = b.PublishReply(m.Reply, "", []byte("battery=83%"))
		}
	}()
	fmt.Println("== 请求-应答 ==")
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	resp, err := b.Request(ctx, "device.battery", []byte("who-am-i"))
	if err != nil {
		fmt.Println("   request failed:", err)
		return
	}
	fmt.Printf("   应答：%s\n", resp.Data)
}

// drainCount 清空订阅缓冲并计数：缓冲取尽即返回；订阅被关闭（ok=false）也结束。
func drainCount(s *Sub) int {
	n := 0
	for {
		select {
		case _, ok := <-s.Ch:
			if !ok {
				return n
			}
			n++
		default:
			return n
		}
	}
}
