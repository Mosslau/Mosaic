// 来源：ph21-iot-vehicle-edge examples/ex01-mqtt-minimal/client.go
// 一句话说明：极简 MQTT 客户端——Dial + CONNECT 鉴权、订阅等 SUBACK、发布 QoS0、
// 读循环路由消息到回调、keepalive 心跳与"长时间无响应即判死"。读循环在独立
// goroutine，Subscribe 同步等 broker 确认（主文档 3.1/3.3/4.1）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run . -broker 127.0.0.1:18830   验证状态：已验证（127.0.0.1 真 TCP 实测）
package main

import (
	"context"
	"encoding/binary"
	"errors"
	"fmt"
	"net"
	"sync"
	"sync/atomic"
	"time"
)

// ClientOptions 连接参数（broker 地址、设备身份与 token、keepalive）。
type ClientOptions struct {
	Broker    string        // host:port
	ClientID  string        // 设备唯一 ID（车联网里即 VIN）
	Username  string        // 通常 = 设备 ID
	Password  string        // 连接态鉴权 token（主文档 3.2）
	KeepAlive time.Duration // 心跳周期；<=0 关闭心跳
}

// Client 极简 MQTT 客户端。
type Client struct {
	opts    ClientOptions
	conn    net.Conn
	mu      sync.Mutex // 保护 pending 与 packetID 分配
	pending map[uint16]chan error
	nextID  uint16
	subs    sync.Map     // filter → func(topic string, payload []byte)
	lastRx  atomic.Int64 // 最后收到任何报文的时间（纳秒），判死依据
	closed  atomic.Bool
}

// NewClient 创建客户端（尚未连接）。
func NewClient(opts ClientOptions) *Client {
	return &Client{
		opts:    opts,
		pending: make(map[uint16]chan error),
	}
}

// Connect 建立连接并完成 CONNECT/CONNACK 握手。
// 鉴权失败（rc=5）返回 ErrNotAuthorized——调用方对它是"上报不重试"。
func (c *Client) Connect(ctx context.Context) error {
	var d net.Dialer
	conn, err := d.DialContext(ctx, "tcp", c.opts.Broker)
	if err != nil {
		return fmt.Errorf("mqtt dial %s: %w", c.opts.Broker, err)
	}
	c.conn = conn
	cp := connectPacket{
		ClientID:  c.opts.ClientID,
		Username:  c.opts.Username,
		Password:  c.opts.Password,
		KeepAlive: uint16(c.opts.KeepAlive / time.Second),
	}
	if _, err := conn.Write(cp.encode()); err != nil {
		_ = conn.Close()
		return fmt.Errorf("mqtt CONNECT: %w", err)
	}
	typ, rest, err := readFrame(conn)
	if err != nil {
		_ = conn.Close()
		return fmt.Errorf("mqtt 读 CONNACK: %w", err)
	}
	if typ != typeCONNACK || len(rest) < 2 {
		_ = conn.Close()
		return errors.New("mqtt: 期待 CONNACK")
	}
	if rc := rest[1]; rc != 0 {
		_ = conn.Close()
		if rc == 5 {
			return fmt.Errorf("%w: 设备 %s", ErrNotAuthorized, c.opts.ClientID)
		}
		return fmt.Errorf("mqtt: CONNACK 返回码 %d", rc)
	}
	c.lastRx.Store(time.Now().UnixNano())
	go c.readLoop()
	if c.opts.KeepAlive > 0 {
		go c.keepAliveLoop()
	}
	return nil
}

// Subscribe 订阅主题并在收到 PUBLISH 时回调；同步等 broker 的 SUBACK。
func (c *Client) Subscribe(ctx context.Context, filter string, cb func(string, []byte)) error {
	c.subs.Store(filter, cb)
	c.mu.Lock()
	c.nextID++
	id := c.nextID
	wait := make(chan error, 1)
	c.pending[id] = wait
	c.mu.Unlock()

	if _, err := c.conn.Write(subscribePacket{PacketID: id, Filter: filter}.encode()); err != nil {
		return fmt.Errorf("mqtt SUBSCRIBE: %w", err)
	}
	select {
	case err := <-wait:
		return err
	case <-ctx.Done():
		return ctx.Err()
	}
}

// Publish 以 QoS0 发布一条消息（无确认，发出即返回）。
func (c *Client) Publish(topic string, payload []byte) error {
	_, err := c.conn.Write(publishPacket{Topic: topic, Payload: payload}.encode())
	if err != nil {
		return fmt.Errorf("mqtt PUBLISH: %w", err)
	}
	return nil
}

// Close 断开连接。
func (c *Client) Close() error {
	c.closed.Store(true)
	if c.conn == nil {
		return nil
	}
	_, _ = c.conn.Write(frame(typeDISCONNECT, 0, nil))
	return c.conn.Close()
}

// readLoop 读报文并分发：PUBLISH→订阅回调、SUBACK→通知 Subscribe 等待者、
// PINGRESP→（lastRx 已更新）、PINGREQ→回 PINGRESP。
func (c *Client) readLoop() {
	for {
		typ, rest, err := readFrame(c.conn)
		if err != nil {
			if !c.closed.Load() {
				// 网络异常：心跳/上层负责重连（3.3 的重连是上层策略，本类只管判死）。
			}
			return
		}
		c.lastRx.Store(time.Now().UnixNano())
		switch typ {
		case typePUBLISH:
			pp, err := decodePublish(rest)
			if err != nil {
				return
			}
			// 通配订阅：按 filter 逐个匹配，命中的都回调（与 MQTT 每订阅一份投递一致）。
			c.subs.Range(func(k, v any) bool {
				filter := k.(string)
				if topicMatch(filter, pp.Topic) {
					v.(func(string, []byte))(pp.Topic, pp.Payload)
				}
				return true
			})
		case typeSUBACK:
			if len(rest) < 2 {
				return
			}
			id := binary.BigEndian.Uint16(rest[:2])
			c.mu.Lock()
			wait, ok := c.pending[id]
			delete(c.pending, id)
			c.mu.Unlock()
			if ok {
				wait <- nil
			}
		case typePINGREQ:
			_, _ = c.conn.Write(frame(typePINGRESP, 0, nil))
		case typePINGRESP:
			// 保活确认：lastRx 已更新，无需额外动作
		case typeDISCONNECT:
			return
		}
	}
}

// keepAliveLoop 周期发 PINGREQ；若超过 3×keepalive 没有任何响应则主动断开——
// 让上层重连逻辑有机会介入（网络假死只有应用层心跳能发现）。
func (c *Client) keepAliveLoop() {
	ka := c.opts.KeepAlive
	if ka <= 0 {
		return
	}
	t := time.NewTicker(ka / 2)
	defer t.Stop()
	for range t.C {
		if c.closed.Load() {
			return
		}
		if time.Since(time.Unix(0, c.lastRx.Load())) > ka*3 {
			_ = c.conn.Close() // 判死：让 Connect 的重连循环接手
			return
		}
		_, _ = c.conn.Write(frame(typePINGREQ, 0, nil))
	}
}
