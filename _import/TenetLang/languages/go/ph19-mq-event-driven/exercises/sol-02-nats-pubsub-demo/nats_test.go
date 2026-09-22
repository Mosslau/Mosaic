// 来源：ph19-mq-event-driven exercises/sol-02-nats-pubsub-demo（练习 2 参考实现）
// 一句话说明：练习 2 验收的可执行版本——通配匹配表、发布订阅扇出、队列组分摊、
// 请求-应答往返（主文档 3.2；真 broker 用 nats.go 的服务端语义验证见文件头）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...    验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"context"
	"testing"
	"time"
)

// TestMatches 通配匹配判定表：精确、* 单级、> 尾部任意、否定情形。
func TestMatches(t *testing.T) {
	cases := []struct {
		subject, pattern string
		want             bool
	}{
		{"fleet.car-001.telemetry", "fleet.car-001.telemetry", true},
		{"fleet.car-001.telemetry", "fleet.*.telemetry", true},
		{"fleet.car-001.telemetry", "fleet.>", true},
		{"fleet.car-001.gps", "fleet.car-001.telemetry", false},
		{"fleet.car-001.telemetry", "fleet.car-002.telemetry", false},
		{"fleet.car-001.telemetry", "fleet.*", false}, // * 只匹配一级
		{"a.b.c", ">", true},
		{"a.b.c", "a.>", true},
		{"a.b.c", "a.*.c", true},
		{"a.b.c.d", "a.*.c", false},
	}
	for _, tc := range cases {
		if got := Matches(tc.subject, tc.pattern); got != tc.want {
			t.Errorf("Matches(%q, %q)=%v, want %v", tc.subject, tc.pattern, got, tc.want)
		}
	}
}

// TestPubSubFanout 普通订阅扇出：同一条消息每个订阅者各收一份。
func TestPubSubFanout(t *testing.T) {
	b := NewBroker()
	var subs []*Sub
	for i := 0; i < 3; i++ {
		s, err := b.Subscribe("fleet.*.telemetry", "")
		if err != nil {
			t.Fatal(err)
		}
		subs = append(subs, s)
	}
	if err := b.Publish("fleet.car-001.telemetry", []byte("sample")); err != nil {
		t.Fatal(err)
	}
	for _, s := range subs {
		select {
		case m := <-s.Ch:
			if string(m.Data) != "sample" {
				t.Fatalf("got %q", m.Data)
			}
		case <-time.After(time.Second):
			t.Fatal("fan-out subscriber got nothing")
		}
	}
}

// TestQueueGroupLoadBalance 队列组分摊：6 条消息两个成员各收 3 条，不重复不漏。
func TestQueueGroupLoadBalance(t *testing.T) {
	b := NewBroker()
	s1, _ := b.Subscribe("jobs", "workers")
	s2, _ := b.Subscribe("jobs", "workers")
	for i := 0; i < 6; i++ {
		if err := b.Publish("jobs", []byte("task")); err != nil {
			t.Fatal(err)
		}
	}
	c1, c2 := count(s1), count(s2)
	if c1 != 3 || c2 != 3 {
		t.Fatalf("queue group counts = %d/%d, want 3/3（轮询均摊）", c1, c2)
	}
}

// count 清空订阅缓冲并计数：缓冲取尽即返回（default 分支），
// 订阅已关闭（Unsubscribe）时收到 ok=false 也正常结束。
func count(s *Sub) int {
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

// TestQueueGroupNotFanout 队列组不是扇出：同一条消息组内只一人收到。
func TestQueueGroupNotFanout(t *testing.T) {
	b := NewBroker()
	s1, _ := b.Subscribe("jobs", "workers")
	s2, _ := b.Subscribe("jobs", "workers")
	_ = b.Publish("jobs", []byte("one"))
	total := count(s1) + count(s2)
	if total != 1 {
		t.Fatalf("queue group delivered %d copies, want 1", total)
	}
}

// TestRequestReply 请求-应答：服务端订阅 jobs 回执，客户端经 _INBOX 拿到应答。
func TestRequestReply(t *testing.T) {
	b := NewBroker()
	srv, err := b.Subscribe("job.execute", "")
	if err != nil {
		t.Fatal(err)
	}
	go func() {
		for m := range srv.Ch {
			// 服务端把结果发回 m.Reply（_INBOX 地址）。
			if err := b.PublishReply(m.Reply, "", []byte("ack:"+string(m.Data))); err != nil {
				return
			}
		}
	}()
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	resp, err := b.Request(ctx, "job.execute", []byte("clean"))
	if err != nil {
		t.Fatal(err)
	}
	if string(resp.Data) != "ack:clean" {
		t.Fatalf("reply=%q, want ack:clean", resp.Data)
	}
	// 关闭服务端订阅，让 goroutine 从 range 退出，测试无泄漏。
	b.Unsubscribe(srv)
}

// TestUnsubscribeStopsDelivery 退订后不再收到新消息。
func TestUnsubscribeStopsDelivery(t *testing.T) {
	b := NewBroker()
	s, _ := b.Subscribe("jobs", "")
	b.Unsubscribe(s)
	_ = b.Publish("jobs", []byte("x"))
	if n := count(s); n != 0 {
		t.Fatalf("received %d after unsubscribe", n)
	}
}
