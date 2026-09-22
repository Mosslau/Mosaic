// 来源：ph21-data-ingest-gateway examples/ex01-mqtt-minimal/broker.go
// 一句话说明：极简 MQTT broker——监听 TCP、校验 CONNECT 鉴权、维护订阅表、
// 按主题/通配符路由 QoS0 PUBLISH、应答 PINGREQ。离线可测：127.0.0.1 真 TCP
// 上跑通"订阅 → 发布 → 路由 → 心跳 → 鉴权拒绝"全流程（主文档 3.1/4.1）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run . -broker 127.0.0.1:18830   验证状态：已验证（127.0.0.1 真 TCP 实测）
package main

import (
	"fmt"
	"io"
	"log"
	"net"
	"strings"
	"sync"
	"time"
)

// AuthFunc broker 侧鉴权回调：返回 true 才放行（主文档 3.2 连接态鉴权）。
type AuthFunc func(username, password string) bool

// connState broker 视角的一个已连接客户端。
type connState struct {
	id        string
	conn      net.Conn
	writeMu   sync.Mutex // 写方向锁：多发布者路由到同一订阅者时串行写
	subs      map[string]bool
	keepalive time.Duration
}

func (c *connState) send(b []byte) error {
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	_, err := c.conn.Write(b)
	return err
}

// Broker 最小 broker：一张订阅表 + 按主题匹配路由。
type Broker struct {
	ln     net.Listener
	auth   AuthFunc
	mu     sync.Mutex
	conns  map[*connState]struct{}
	closed bool
}

// NewBroker 在 addr 上创建（含监听）broker；auth 为 nil 表示放行所有连接。
func NewBroker(addr string, auth AuthFunc) (*Broker, error) {
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("mqtt broker 监听 %s: %w", addr, err)
	}
	return &Broker{ln: ln, auth: auth, conns: make(map[*connState]struct{})}, nil
}

// Addr 返回实际监听地址（传 :0 时用于拿随机端口）。
func (b *Broker) Addr() net.Addr { return b.ln.Addr() }

// Start 启动 accept 循环（不阻塞调用方）。
func (b *Broker) Start() {
	go func() {
		for {
			c, err := b.ln.Accept()
			if err != nil {
				return // 监听关闭即退出
			}
			go b.handleConn(c)
		}
	}()
}

// Stop 关闭监听与全部客户端连接。
func (b *Broker) Stop() {
	b.mu.Lock()
	b.closed = true
	for s := range b.conns {
		_ = s.conn.Close()
	}
	b.mu.Unlock()
	_ = b.ln.Close()
}

func (b *Broker) handleConn(c net.Conn) {
	defer func() { _ = c.Close() }()

	// 1) 首包必须是 CONNECT，超时防恶意占连接。
	_ = c.SetReadDeadline(time.Now().Add(5 * time.Second))
	typ, rest, err := readFrame(c)
	if err != nil || typ != typeCONNECT {
		return
	}
	cp, err := decodeConnect(rest)
	if err != nil {
		return
	}
	// 2) 连接态鉴权：失败回 CONNACK rc=5 并关闭——不进入会话。
	if b.auth != nil && !b.auth(cp.Username, cp.Password) {
		_, _ = c.Write(connackPacket(5))
		log.Printf("broker: 拒绝设备 %q 连接（鉴权失败）", cp.ClientID)
		return
	}
	st := &connState{
		id:        cp.ClientID,
		conn:      c,
		subs:      make(map[string]bool),
		keepalive: time.Duration(cp.KeepAlive) * time.Second,
	}
	if err := st.send(connackPacket(0)); err != nil {
		return
	}
	b.mu.Lock()
	if b.closed {
		b.mu.Unlock()
		return
	}
	b.conns[st] = struct{}{}
	b.mu.Unlock()
	defer func() {
		b.mu.Lock()
		delete(b.conns, st)
		b.mu.Unlock()
	}()

	// 3) 读循环：SUBSCRIBE 登记订阅、PUBLISH 路由、PINGREQ 保活、DISCONNECT 退出。
	for {
		if st.keepalive > 0 { // 服务器侧保活：keepalive×3 无任何报文即踢
			_ = c.SetReadDeadline(time.Now().Add(st.keepalive * 3))
		}
		typ, rest, err := readFrame(c)
		if err != nil {
			if err != io.EOF {
				log.Printf("broker: 设备 %q 连接异常断开: %v", st.id, err)
			}
			return
		}
		switch typ {
		case typeSUBSCRIBE:
			sp, err := decodeSubscribe(rest)
			if err != nil {
				return
			}
			st.subs[sp.Filter] = true
			if err := st.send(subackPacket(sp.PacketID, 0)); err != nil {
				return
			}
			log.Printf("broker: 设备 %q 订阅 %q", st.id, sp.Filter)
		case typePUBLISH:
			pp, err := decodePublish(rest)
			if err != nil {
				return
			}
			b.route(st, pp)
		case typePINGREQ:
			if err := st.send(frame(typePINGRESP, 0, nil)); err != nil {
				return
			}
		case typeDISCONNECT:
			return
		default:
			return // 未知报文：最小实现直接断开
		}
	}
}

// route 把一条 PUBLISH 投递给所有订阅了匹配主题的客户端（MQTT 语义：订阅者含发布者自己）。
func (b *Broker) route(_ *connState, pp publishPacket) {
	b.mu.Lock()
	defer b.mu.Unlock()
	for dst := range b.conns {
		if dst.hasMatch(pp.Topic) {
			_ = dst.send(pp.encode())
		}
	}
}

// hasMatch 判断本连接是否订阅了与 topic 匹配的 filter（支持 + 与 # 通配）。
func (c *connState) hasMatch(topic string) bool {
	for f := range c.subs {
		if topicMatch(f, topic) {
			return true
		}
	}
	return false
}

// topicMatch MQTT 主题匹配：# 匹配任意剩余层级（须在末位），+ 匹配单层。
func topicMatch(filter, topic string) bool {
	fs := strings.Split(filter, "/")
	ts := strings.Split(topic, "/")
	for i := range fs {
		if fs[i] == "#" {
			return true // # 前的层级已全部相等（含 fs 恰为 "#" 的情况）
		}
		if i >= len(ts) {
			return false
		}
		if fs[i] == "+" {
			continue
		}
		if fs[i] != ts[i] {
			return false
		}
	}
	return len(fs) == len(ts)
}
