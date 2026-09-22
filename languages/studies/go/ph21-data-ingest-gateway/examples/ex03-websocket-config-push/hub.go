// 来源：ph21-data-ingest-gateway examples/ex03-websocket-configState/hub.go
// 一句话说明：实时中枢——监听 TCP，把连接升级为 WebSocket，按 path 分角色：
// /ws/configState 的面板(panel)订阅某数据源配置状态快照、采集端(agent)上报 reported/收 desired；
// 心跳 ticker 对全员发 Ping；配置状态每变一次就推快照给订阅面板（主文档 34）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18880   验证状态：已验证（127.0.0.1 真 TCP 实测）
package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"strings"
	"sync"
	"time"
)

// AuthFunc 采集端/面板连接的鉴权：source 维度的 token 校验（连接态，主文档 3.2）。
type AuthFunc func(source, role, token string) bool

// Hub 采集端配置状态实时中枢。
type Hub struct {
	auth AuthFunc
	ping time.Duration // >0 时周期性对全员发 Ping
	ln   net.Listener

	mu           sync.Mutex
	configStates map[string]*ConfigState       // source → 配置状态
	panels       map[string]map[*Conn]struct{} // source → 订阅的面板连接
	agents       map[string]*Conn              // source → 采集端连接（同数据源新连顶旧，最简策略）
}

// NewHub 创建并监听 addr。
func NewHub(addr string, auth AuthFunc, pingInterval time.Duration) (*Hub, error) {
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("hub 监听 %s: %w", addr, err)
	}
	return &Hub{
		auth: auth, ping: pingInterval, ln: ln,
		configStates: make(map[string]*ConfigState),
		panels:       make(map[string]map[*Conn]struct{}),
		agents:       make(map[string]*Conn),
	}, nil
}

// Addr 实际监听地址。
func (h *Hub) Addr() net.Addr { return h.ln.Addr() }

// Start 启动 accept 循环。
func (h *Hub) Start() {
	go func() {
		for {
			c, err := h.ln.Accept()
			if err != nil {
				return
			}
			go h.handleConn(c)
		}
	}()
}

// Stop 关闭全部连接与监听。
func (h *Hub) Stop() {
	h.mu.Lock()
	defer h.mu.Unlock()
	for v, p := range h.panels {
		for c := range p {
			_ = c.Close()
		}
		delete(h.panels, v)
	}
	for v, d := range h.agents {
		_ = d.Close()
		delete(h.agents, v)
	}
	_ = h.ln.Close()
}

func (h *Hub) handleConn(raw net.Conn) {
	br := bufio.NewReader(raw)
	req, err := readUpgradeRequest(br)
	if err != nil {
		writeHTTPError(raw, 400, "bad upgrade request")
		_ = raw.Close()
		return
	}
	// 路径形如 /ws/configState/{source}/{role}，role ∈ {agent, panel}。
	parts := strings.Split(req.Path, "/")
	if len(parts) != 5 || parts[1] != "ws" || parts[2] != "configState" {
		writeHTTPError(raw, 400, "bad path")
		_ = raw.Close()
		return
	}
	source := parts[3]
	role := parts[4]
	if role != "panel" && role != "agent" {
		writeHTTPError(raw, 400, "bad role")
		_ = raw.Close()
		return
	}
	// 鉴权必须在 101 之前：失败只回 HTTP 401，绝不给握手成功信号（主文档 3.2）。
	if h.auth != nil && !h.auth(source, role, req.Token) {
		log.Printf("hub: 拒绝 %s/%s（鉴权失败）", source, role)
		writeHTTPError(raw, 401, "unauthorized")
		_ = raw.Close()
		return
	}
	writeHTTP101(raw, serverAccept(req.Key))
	c := &Conn{raw: raw, br: br, maskWrite: false}

	h.register(source, role, c)
	defer h.unregister(source, role, c)

	// 入会后立即推一帧初始状态（面板断线重连后由此补最新态）。
	h.pushCurrent(source, role, c)

	// 心跳发送：服务端定时 Ping，客户端回 Pong（读循环自动应答）。
	stopPing := make(chan struct{})
	defer close(stopPing)
	if h.ping > 0 {
		go func() {
			t := time.NewTicker(h.ping)
			defer t.Stop()
			for {
				select {
				case <-t.C:
					if err := c.Ping(); err != nil {
						return
					}
				case <-stopPing:
					return
				}
			}
		}()
	}

	// 读循环：文本 JSON 帧。
	for {
		opcode, payload, err := c.ReadMessage()
		if err != nil {
			return
		}
		switch opcode {
		case opPing: // 对端 ping → 回 pong
			_ = c.WriteMessage(opPong, nil)
		case opPong:
			// 心跳确认，无需动作
		case opClose:
			return
		case opText, opBinary:
			h.handleJSON(source, role, c, payload)
		}
	}
}

func (h *Hub) register(source, role string, c *Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if h.configStates[source] == nil {
		h.configStates[source] = NewConfigState(map[string]any{"online": true})
	}
	if role == "panel" {
		if h.panels[source] == nil {
			h.panels[source] = make(map[*Conn]struct{})
		}
		h.panels[source][c] = struct{}{}
	} else {
		if old, ok := h.agents[source]; ok {
			_ = old.Close() // 同数据源新采集端连接顶掉旧连接（单采集端语义）
		}
		h.agents[source] = c
	}
}

func (h *Hub) unregister(source, role string, c *Conn) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if role == "panel" {
		if m, ok := h.panels[source]; ok {
			delete(m, c)
			if len(m) == 0 {
				delete(h.panels, source)
			}
		}
		return
	}
	if h.agents[source] == c {
		delete(h.agents, source)
	}
}

// 入会帧的 JSON 载荷结构。
type frameJSON struct {
	Op       string         `json:"op"`
	Reported map[string]any `json:"reported,omitempty"`
	Desired  map[string]any `json:"desired,omitempty"`
}

func (h *Hub) handleJSON(source, role string, c *Conn, payload []byte) {
	var f frameJSON
	if err := json.Unmarshal(payload, &f); err != nil {
		return
	}
	switch {
	case role == "agent" && f.Op == "report":
		h.applyReport(source, f.Reported)
	case role == "agent" && f.Op == "desired_ack":
		log.Printf("hub: %s 已确认 desired 生效", source)
	}
}

// applyReport 采集端上报 → 配置状态合并 → 推快照给订阅面板。
func (h *Hub) applyReport(source string, reported map[string]any) {
	h.mu.Lock()
	s := h.configStates[source]
	h.mu.Unlock()
	if s == nil {
		return
	}
	s.Report(reported)
	h.broadcastSnapshot(source)
}

// SetDesired 云侧指令入口（ops 服务调用，带 baseVersion 防并发覆盖）。
func (h *Hub) SetDesired(source string, desired map[string]any, baseVersion int64) (int64, error) {
	h.mu.Lock()
	s := h.configStates[source]
	h.mu.Unlock()
	if s == nil {
		return 0, errors.New("configState 不存在")
	}
	v, err := s.ApplyDesired(desired, baseVersion)
	if err != nil {
		return 0, err
	}
	// 推 desired 给采集端（若在线），推新快照给面板。
	h.mu.Lock()
	dev := h.agents[source]
	h.mu.Unlock()
	if dev != nil {
		msg, _ := json.Marshal(map[string]any{"op": "desired", "desired": desired, "version": v})
		_ = dev.WriteMessage(opText, msg)
	}
	h.broadcastSnapshot(source)
	return v, nil
}

func (h *Hub) broadcastSnapshot(source string) {
	desired, reported, version := func() (map[string]any, map[string]any, int64) {
		h.mu.Lock()
		defer h.mu.Unlock()
		s := h.configStates[source]
		if s == nil {
			return nil, nil, 0
		}
		d, r, v := s.Snapshot()
		return d, r, v
	}()
	if reported == nil {
		return
	}
	msg, _ := json.Marshal(map[string]any{
		"op": "snapshot", "source": source,
		"reported": reported, "desired": desired, "version": version,
	})
	h.mu.Lock()
	defer h.mu.Unlock()
	for c := range h.panels[source] {
		_ = c.WriteMessage(opText, msg)
	}
}

// pushCurrent 给刚入会的连接推一帧当前配置状态。
func (h *Hub) pushCurrent(source, role string, c *Conn) {
	h.mu.Lock()
	s := h.configStates[source]
	h.mu.Unlock()
	if s == nil {
		return
	}
	desired, reported, version := s.Snapshot()
	var msg []byte
	if role == "panel" {
		msg, _ = json.Marshal(map[string]any{
			"op": "snapshot", "source": source,
			"reported": reported, "desired": desired, "version": version,
		})
	} else {
		msg, _ = json.Marshal(map[string]any{
			"op": "connected", "source": source,
			"desired": desired, "version": version,
		})
	}
	_ = c.WriteMessage(opText, msg)
}
