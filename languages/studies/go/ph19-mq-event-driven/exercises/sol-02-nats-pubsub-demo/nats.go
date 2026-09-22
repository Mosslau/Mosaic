// 来源：ph19-mq-event-driven exercises/sol-02-nats-pubsub-demo（练习 2 参考实现）
// 一句话说明：NATS core 语义的离线实现——subject 分层 + * 与 > 通配匹配、
// 发布-订阅扇出、队列组（queue group）负载分摊、请求-应答（_INBOX）。
// 真 broker 切换：用 nats.go 时同一套 subject/队列语义由服务端实现——
//
//	go get github.com/nats-io/nats.go@latest
//	docker run -d -p 4222:4222 nats:2.10
//	nc, _ := nats.Connect("nats://127.0.0.1:4222")
//	sub, _ := nc.SubscribeSync("fleet.*.telemetry"); 生产端 nc.Publish(...)
//	队列组 nc.QueueSubscribe("fleet.telemetry", "workers", ...)
//	请求应答 nc.Request(subject, data, timeout)（未在本环境验证）。
//
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync"
)

// Msg 一条 NATS 消息：Subject 是投递目标；Reply 用于请求-应答回信地址。
type Msg struct {
	Subject string
	Reply   string
	Data    []byte
}

// Sub 一次订阅：Ch 是投递缓冲，消费方从这里取消息。
// 快速消费者跟不上时队列会满——满则丢弃并计数（见 Dropped），
// 这正是 NATS "尽力而为投递、不持久化" 的服务端语义（主文档 3.2）。
type Sub struct {
	id      int64
	subject string // 订阅主题，可含通配
	queue   string // 空 = 普通订阅；非空 = 队列组成员
	Ch      chan Msg
}

// Subject 返回订阅的 subject 串（打印用）。
func (s *Sub) Subject() string { return s.subject }

// Queue 返回队列组名（空串表示普通订阅）。
func (s *Sub) Queue() string { return s.queue }

// Broker 内存 NATS：维护订阅表，负责匹配与投递。
type Broker struct {
	mu      sync.Mutex
	next    int64
	subs    map[int64]*Sub
	rr      map[string]int // 队列组轮询指针：key = subject|queue
	dropped int
}

// NewBroker 建空 broker。
func NewBroker() *Broker {
	return &Broker{subs: make(map[int64]*Sub), rr: make(map[string]int)}
}

// Subscribe 订阅 subject（可含 * / >），queue 非空时加入该队列组。
func (b *Broker) Subscribe(subject, queue string) (*Sub, error) {
	if err := validateSubject(subject); err != nil {
		return nil, err
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	b.next++
	s := &Sub{
		id:      b.next,
		subject: subject,
		queue:   queue,
		Ch:      make(chan Msg, 128),
	}
	b.subs[s.id] = s
	return s, nil
}

// Unsubscribe 取消订阅。
func (b *Broker) Unsubscribe(s *Sub) {
	b.mu.Lock()
	defer b.mu.Unlock()
	delete(b.subs, s.id)
	close(s.Ch)
}

// Publish 向 subject 发布一条消息（无回信地址）。
func (b *Broker) Publish(subject string, data []byte) error {
	return b.publish(Msg{Subject: subject, Data: data})
}

// PublishReply 带 Reply 地址发布（请求-应答的服务端回信用）。
func (b *Broker) PublishReply(subject, reply string, data []byte) error {
	return b.publish(Msg{Subject: subject, Reply: reply, Data: data})
}

// publish 匹配并投递：
//   - 普通订阅（queue==""）：全部收到（fan-out）
//   - 队列组（同一 subject 模式 + 同一 queue）：轮流只给一个成员（分摊）
func (b *Broker) publish(m Msg) error {
	if err := validateSubject(m.Subject); err != nil {
		return err
	}
	b.mu.Lock()
	defer b.mu.Unlock()

	// 1. 收集命中订阅并按 id 排序（投递顺序确定，队列组轮询才能严格均摊）。
	var matched []*Sub
	for _, s := range b.subs {
		if Matches(m.Subject, s.subject) {
			matched = append(matched, s)
		}
	}
	sort.Slice(matched, func(i, j int) bool { return matched[i].id < matched[j].id })

	plain := make([]*Sub, 0)
	groups := make(map[string][]*Sub)
	for _, s := range matched {
		if s.queue == "" {
			plain = append(plain, s)
		} else {
			key := s.subject + "|" + s.queue
			groups[key] = append(groups[key], s)
		}
	}

	// 2. 普通订阅扇出。
	for _, s := range plain {
		b.deliver(s, m)
	}

	// 3. 队列组轮询：每组这轮只派一个成员，指针前进（均摊）。
	for key, members := range groups {
		idx := b.rr[key] % len(members)
		b.rr[key] = idx + 1
		b.deliver(members[idx], m)
	}
	return nil
}

// deliver 尽力投递：缓冲满则丢弃并计数。
func (b *Broker) deliver(s *Sub, m Msg) {
	select {
	case s.Ch <- m:
	default:
		b.dropped++ // NATS 语义：慢消费者 = 丢消息，不背压生产者
	}
}

// Dropped 累计丢弃数（快消费者观测指标，主文档 3.7）。
func (b *Broker) Dropped() int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.dropped
}

// Request 请求-应答：为本次请求建一个 _INBOX 临时订阅，发消息后等应答。
func (b *Broker) Request(ctx context.Context, subject string, data []byte) (Msg, error) {
	b.mu.Lock()
	b.next++
	reply := fmt.Sprintf("_INBOX.%d", b.next)
	b.mu.Unlock()

	sub, err := b.Subscribe(reply, "")
	if err != nil {
		return Msg{}, err
	}
	defer b.Unsubscribe(sub)
	if err := b.PublishReply(subject, reply, data); err != nil {
		return Msg{}, err
	}
	select {
	case m := <-sub.Ch:
		return m, nil
	case <-ctx.Done():
		return Msg{}, ctx.Err()
	}
}

// Matches 判断 subject 是否命中订阅模式。
// NATS 规则：'*' 匹配单个 token；'>' 匹配尾部一个或多个 token（只能出现在末尾）。
func Matches(subject, pattern string) bool {
	st := strings.Split(subject, ".")
	pt := strings.Split(pattern, ".")
	for i, tok := range pt {
		if tok == ">" {
			return true // 尾部任意长度：剩余 token 全命中
		}
		if i >= len(st) {
			return false // 模式比 subject 长
		}
		if tok != "*" && tok != st[i] {
			return false
		}
	}
	return len(st) == len(pt)
}

// validateSubject 简易校验：空 token、非法通配位置直接拒绝（真实服务端同理）。
func validateSubject(s string) error {
	if s == "" {
		return fmt.Errorf("empty subject")
	}
	toks := strings.Split(s, ".")
	for i, tok := range toks {
		if tok == "" {
			return fmt.Errorf("subject %q has empty token", s)
		}
		if tok == ">" && i != len(toks)-1 {
			return fmt.Errorf("'>' must be the last token in %q", s)
		}
	}
	return nil
}
