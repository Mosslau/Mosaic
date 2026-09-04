// 来源：ph21-iot-vehicle-edge exercises/sol-01-mqtt-device-access/sol01.go
// 一句话说明：练习 1 参考实现——"MQTT 设备接入服务"的接入核心：会话鉴权、
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

// ErrUnauthorized 设备鉴权失败（接入层拒绝，重试无意义）。
var ErrUnauthorized = errors.New("access: unauthorized device")

// Transport 传输抽象：真实 MQTT(paho)/内存假传输都实现它，接入核心只依赖接口。
type Transport interface {
	Connect(deviceID, token string) error
	Subscribe(topic string) error
	Publish(topic string, payload []byte) error
	// OnMessage 注册收消息回调（主题、负载）。
	OnMessage(func(topic string, payload []byte))
	// OnDisconnect 注册断线回调（假传输在心跳超时/Close 时触发）。
	OnDisconnect(func(deviceID string))
	Close() error
}

// AccessCore 接入核心：管理设备会话、鉴权、心跳判活、主题路由。
type AccessCore struct {
	auth        func(deviceID, token string) bool // 设备密钥 allowlist
	timeout     time.Duration                     // 心跳超时阈值
	onTelemetry func(vin string, payload []byte)

	mu      sync.Mutex
	devices map[string]*deviceSession
}

type deviceSession struct {
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
		devices: make(map[string]*deviceSession),
	}
}

// OnTelemetry 注册遥测回调（主题 veh/{vin}/telemetry 解析出 vin 后调用）。
func (a *AccessCore) OnTelemetry(fn func(vin string, payload []byte)) { a.onTelemetry = fn }

// Attach 设备经传输接入：鉴权通过才建立会话；失败返回 ErrUnauthorized。
func (a *AccessCore) Attach(deviceID, token string, t Transport) error {
	if a.auth != nil && !a.auth(deviceID, token) {
		return fmt.Errorf("%w: %s", ErrUnauthorized, deviceID)
	}
	if err := t.Connect(deviceID, token); err != nil {
		return err
	}
	sess := &deviceSession{transport: t, lastSeen: time.Now(), online: true}
	a.mu.Lock()
	a.devices[deviceID] = sess
	a.mu.Unlock()

	// 订阅设备自己的遥测主题（一车一主题，主文档 3.1 主题树约定）。
	topic := "veh/" + deviceID + "/telemetry"
	if err := t.Subscribe(topic); err != nil {
		return err
	}
	sess.subs = append(sess.subs, topic)

	t.OnMessage(func(topic string, payload []byte) {
		a.touch(deviceID) // 任何消息都是心跳
		vin := vinOfTopic(topic)
		if vin != "" && a.onTelemetry != nil {
			a.onTelemetry(vin, payload)
		}
	})
	t.OnDisconnect(func(_ string) { a.markOffline(deviceID) })
	return nil
}

// CheckHeartbeats 扫描会话，超过 timeout 无消息的设备判离线。
func (a *AccessCore) CheckHeartbeats(now time.Time) []string {
	a.mu.Lock()
	defer a.mu.Unlock()
	var down []string
	for id, s := range a.devices {
		if s.online && now.Sub(s.lastSeen) > a.timeout {
			s.online = false
			down = append(down, id)
		}
	}
	return down
}

// OnlineCount 在线设备数。
func (a *AccessCore) OnlineCount() int {
	a.mu.Lock()
	defer a.mu.Unlock()
	n := 0
	for _, s := range a.devices {
		if s.online {
			n++
		}
	}
	return n
}

func (a *AccessCore) touch(deviceID string) {
	a.mu.Lock()
	if s, ok := a.devices[deviceID]; ok {
		s.lastSeen = time.Now()
	}
	a.mu.Unlock()
}

func (a *AccessCore) markOffline(deviceID string) {
	a.mu.Lock()
	if s, ok := a.devices[deviceID]; ok {
		s.online = false
	}
	a.mu.Unlock()
}

// vinOfTopic 从 veh/{vin}/telemetry 解析 vin（解析失败返回空串）。
func vinOfTopic(topic string) string {
	parts := strings.Split(topic, "/")
	if len(parts) == 3 && parts[0] == "veh" && parts[2] == "telemetry" {
		return parts[1]
	}
	return ""
}

// ---------- 内存假传输（练习与测试用；真 broker 时替换为 paho 实现） ----------

// memTransport 内存假传输：把收到的消息投给 OnMessage 回调；可注入断开。
type memTransport struct {
	deviceID string
	recvMu   sync.Mutex
	recv     []string
	onMsg    func(string, []byte)
	onDisc   func(string)
	subs     []string
}

func newMemTransport() *memTransport { return &memTransport{} }

func (m *memTransport) Connect(deviceID, _ string) error { m.deviceID = deviceID; return nil }
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
