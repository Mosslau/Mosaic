// 来源：ph21-data-ingest-gateway exercises/sol-01-mqtt-agent-access/sol01.go
// 一句话说明：练习 1 参考实现——"MQTT 采集端接入服务"的接入核心：会话鉴权、
// 心跳超时判离线、主题路由回调；传输层抽象为接口 + 内存假传输（主文档 3.1/3.2）。
// 连真 MQTT broker 时只替换 transport（如 paho），核心逻辑不变。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"
)

// ErrUnauthorized 采集端鉴权失败（接入层拒绝，重试无意义）。
var ErrUnauthorized = errors.New("access: unauthorized agent")

// Transport 传输抽象：真实 MQTT(paho)/内存假传输都实现它，接入核心只依赖接口。
type Transport interface {
	Connect(agentID, token string) error
	Subscribe(topic string) error
	Publish(topic string, payload []byte) error
	// OnMessage 注册收消息回调（主题、负载）。
	OnMessage(func(topic string, payload []byte))
	// OnDisconnect 注册断线回调（假传输在心跳超时/Close 时触发）。
	OnDisconnect(func(agentID string))
	Close() error
}

// AccessCore 接入核心：管理采集端会话、鉴权、心跳判活、主题路由。
type AccessCore struct {
	auth      func(agentID, token string) bool // 采集端密钥 allowlist
	timeout   time.Duration                    // 心跳超时阈值
	onMetrics func(sourceID string, payload []byte)

	mu     sync.Mutex
	agents map[string]*agentSession
}

type agentSession struct {
	transport Transport
	lastSeen  time.Time
	online    bool
	subs      []string
}

// NewAccess 建接入核心。auth 为 nil 表示放行全部。
func NewAccess(timeout time.Duration, auth func(string, string) bool) *AccessCore {
	return &AccessCore{
		auth:    auth,
		timeout: timeout,
		agents:  make(map[string]*agentSession),
	}
}

// OnMetrics 注册指标回调（主题 ingest/{sourceID}/metrics 解析出 sourceID 后调用）。
func (a *AccessCore) OnMetrics(fn func(sourceID string, payload []byte)) { a.onMetrics = fn }

// Attach 采集端经传输接入：鉴权通过才建立会话；失败返回 ErrUnauthorized。
func (a *AccessCore) Attach(agentID, token string, t Transport) error {
	if a.auth != nil && !a.auth(agentID, token) {
		return fmt.Errorf("%w: %s", ErrUnauthorized, agentID)
	}
	if err := t.Connect(agentID, token); err != nil {
		return err
	}
	sess := &agentSession{transport: t, lastSeen: time.Now(), online: true}
	a.mu.Lock()
	a.agents[agentID] = sess
	a.mu.Unlock()

	// 订阅采集端自己的指标主题（一个数据源一主题，主文档 3.1 主题树约定）。
	topic := "ingest/" + agentID + "/metrics"
	if err := t.Subscribe(topic); err != nil {
		return err
	}
	sess.subs = append(sess.subs, topic)

	t.OnMessage(func(topic string, payload []byte) {
		a.touch(agentID) // 任何消息都是心跳
		sourceID := sourceIDOfTopic(topic)
		if sourceID != "" && a.onMetrics != nil {
			a.onMetrics(sourceID, payload)
		}
	})
	t.OnDisconnect(func(_ string) { a.markOffline(agentID) })
	return nil
}

// CheckHeartbeats 扫描会话，超过 timeout 无消息的采集端判离线。
func (a *AccessCore) CheckHeartbeats(now time.Time) []string {
	a.mu.Lock()
	defer a.mu.Unlock()
	var down []string
	for id, s := range a.agents {
		if s.online && now.Sub(s.lastSeen) > a.timeout {
			s.online = false
			down = append(down, id)
		}
	}
	return down
}

// OnlineCount 在线采集端数。
func (a *AccessCore) OnlineCount() int {
	a.mu.Lock()
	defer a.mu.Unlock()
	n := 0
	for _, s := range a.agents {
		if s.online {
			n++
		}
	}
	return n
}

func (a *AccessCore) touch(agentID string) {
	a.mu.Lock()
	if s, ok := a.agents[agentID]; ok {
		s.lastSeen = time.Now()
	}
	a.mu.Unlock()
}

func (a *AccessCore) markOffline(agentID string) {
	a.mu.Lock()
	if s, ok := a.agents[agentID]; ok {
		s.online = false
	}
	a.mu.Unlock()
}

// sourceIDOfTopic 从 ingest/{sourceID}/metrics 解析 sourceID（解析失败返回空串）。
func sourceIDOfTopic(topic string) string {
	parts := strings.Split(topic, "/")
	if len(parts) == 3 && parts[0] == "ingest" && parts[2] == "metrics" {
		return parts[1]
	}
	return ""
}

// ---------- 内存假传输（练习与测试用；真 broker 时替换为 paho 实现） ----------

// memTransport 内存假传输：把收到的消息投给 OnMessage 回调；可注入断开。
type memTransport struct {
	agentID string
	recvMu  sync.Mutex
	recv    []string
	onMsg   func(string, []byte)
	onDisc  func(string)
	subs    []string
}

func newMemTransport() *memTransport { return &memTransport{} }

func (m *memTransport) Connect(agentID, _ string) error { m.agentID = agentID; return nil }
func (m *memTransport) Subscribe(topic string) error {
	m.subs = append(m.subs, topic)
	return nil
}
func (m *memTransport) Publish(topic string, payload []byte) error {
	m.recvMu.Lock()
	m.recv = append(m.recv, topic+":"+string(payload))
	m.recvMu.Unlock()
	return nil
}
func (m *memTransport) OnMessage(f func(string, []byte)) { m.onMsg = f }
func (m *memTransport) OnDisconnect(f func(string))      { m.onDisc = f }
func (m *memTransport) Close() error                     { return nil }

// simulate 模拟从"网络"收到一帧消息（等价于 broker 把 PUBLISH 投给订阅者）。
func (m *memTransport) simulate(topic string, payload []byte) {
	if m.onMsg != nil {
		m.onMsg(topic, payload)
	}
}

func (m *memTransport) got() []string {
	m.recvMu.Lock()
	defer m.recvMu.Unlock()
	return append([]string(nil), m.recv...)
}
