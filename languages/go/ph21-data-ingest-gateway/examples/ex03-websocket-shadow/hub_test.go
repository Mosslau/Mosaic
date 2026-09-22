// 来源：ph21-data-ingest-gateway examples/ex03-websocket-shadow/hub_test.go
// 一句话说明：影子中枢的真 TCP 集成测试——鉴权 401、面板订阅收 snapshot、
// 设备上报触发推送、云侧 desired 下发设备 + 影子版本单调、过期 baseVersion 被拒、
// 心跳跨多周期连接存活。每项断言都是主文档 3.4/3.6/4.2 的语义钉住。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"encoding/json"
	"errors"
	"testing"
	"time"
)

func startHub(t *testing.T) *Hub {
	t.Helper()
	h, err := NewHub("127.0.0.1:0", func(vehicle, role, token string) bool {
		return token == "tok-"+vehicle
	}, 0) // 单测心跳单独开
	if err != nil {
		t.Fatal(err)
	}
	h.Start()
	t.Cleanup(h.Stop)
	return h
}

// dialAs 连 hub 并按角色返回（面板/设备）。
func dialAs(t *testing.T, h *Hub, vehicle, role string) *Conn {
	t.Helper()
	c, err := Dial(h.Addr().String(), "/ws/shadow/"+vehicle+"/"+role+"?token=tok-"+vehicle)
	if err != nil {
		t.Fatalf("%s %s 接入: %v", vehicle, role, err)
	}
	t.Cleanup(func() { _ = c.Close() })
	return c
}

// readText 读一个文本帧（跳过控制帧）。
func readText(t *testing.T, c *Conn, timeout time.Duration) map[string]any {
	t.Helper()
	deadline := time.After(timeout)
	for {
		select {
		case <-deadline:
			t.Fatal("读帧超时")
		default:
		}
		// ReadMessage 阻塞，超时靠 hub 保活无法覆盖——用 goroutine + select 封装。
		type res struct {
			op      byte
			payload []byte
			err     error
		}
		ch := make(chan res, 1)
		go func() {
			op, p, err := c.ReadMessage()
			ch <- res{op, p, err}
		}()
		var r res
		select {
		case r = <-ch:
		case <-deadline:
			t.Fatal("读帧超时")
		}
		if r.err != nil {
			t.Fatalf("读帧错误: %v", r.err)
		}
		switch r.op {
		case opText, opBinary:
			var m map[string]any
			if err := json.Unmarshal(r.payload, &m); err != nil {
				t.Fatalf("非法 JSON: %v", err)
			}
			return m
		case opPing:
			_ = c.WriteMessage(opPong, nil)
		case opPong, opClose:
		}
	}
}

func TestHubRejectsBadToken(t *testing.T) {
	h := startHub(t)
	_, err := Dial(h.Addr().String(), "/ws/shadow/veh-001/panel?token=wrong")
	if err == nil {
		t.Fatal("坏 token 应握手失败")
	}
}

func TestReportPushesSnapshotToPanel(t *testing.T) {
	h := startHub(t)
	panel := dialAs(t, h, "veh-001", "panel")
	dev := dialAs(t, h, "veh-001", "device")

	// 面板入会先收初始 snapshot；设备收 connected。
	init := readText(t, panel, 2*time.Second)
	if init["op"] != "snapshot" {
		t.Fatalf("面板初始帧 op=%v", init["op"])
	}
	readText(t, dev, 2*time.Second)

	// 设备上报两帧 → 面板收到两帧 snapshot，version 单调递增，reported 合并且最新值可见。
	lastVersion := float64(0)
	for i, speed := range []int{50, 65} {
		msg, _ := json.Marshal(map[string]any{
			"op": "report", "reported": map[string]any{"speed": speed, "seq": i + 1},
		})
		if err := dev.WriteMessage(opText, msg); err != nil {
			t.Fatal(err)
		}
		snap := readText(t, panel, 2*time.Second)
		v := snap["version"].(float64)
		if v <= lastVersion {
			t.Errorf("第 %d 帧版本 %v 未单调（上版 %v）", i+1, v, lastVersion)
		}
		lastVersion = v
		reported := snap["reported"].(map[string]any)
		if int(reported["speed"].(float64)) != speed {
			t.Errorf("reported.speed = %v, want %d", reported["speed"], speed)
		}
	}
}

func TestSetDesiredPushesToDeviceAndPanel(t *testing.T) {
	h := startHub(t)
	panel := dialAs(t, h, "veh-002", "panel")
	dev := dialAs(t, h, "veh-002", "device")
	readText(t, panel, 2*time.Second) // 初始 snapshot
	readText(t, dev, 2*time.Second)   // connected

	// 云侧设 desired：baseVersion 取当前影子版本（CAS 语义）。
	base := shadowVersion(t, h, "veh-002")
	v, err := h.SetDesired("veh-002", map[string]any{"speed_limit": 80}, base)
	if err != nil {
		t.Fatalf("SetDesired: %v", err)
	}
	// 设备收到 desired 下发。
	d := readText(t, dev, 2*time.Second)
	if d["op"] != "desired" || int(d["desired"].(map[string]any)["speed_limit"].(float64)) != 80 {
		t.Errorf("设备 desired 帧异常: %v", d)
	}
	if d["version"].(float64) != float64(v) {
		t.Errorf("desired 版本 %v, want %d", d["version"], v)
	}
	// 面板收到新快照（含 desired）。
	snap := readText(t, panel, 2*time.Second)
	if snap["desired"].(map[string]any)["speed_limit"].(float64) != 80 {
		t.Errorf("面板快照未含 desired: %v", snap)
	}
}

// shadowVersion 取某车影子当前版本（测试辅助；轮询等影子在 accept goroutine 里建成）。
func shadowVersion(t *testing.T, h *Hub, vehicle string) int64 {
	t.Helper()
	deadline := time.Now().Add(time.Second)
	for {
		h.mu.Lock()
		s := h.shadows[vehicle]
		h.mu.Unlock()
		if s != nil {
			_, _, v := s.Snapshot()
			return v
		}
		if time.Now().After(deadline) {
			t.Fatalf("影子 %s 迟迟未建", vehicle)
		}
		time.Sleep(5 * time.Millisecond)
	}
}

func TestStaleDesiredRejected(t *testing.T) {
	h := startHub(t)
	dialAs(t, h, "veh-003", "device")
	time.Sleep(50 * time.Millisecond)
	base := shadowVersion(t, h, "veh-003")
	// 两次带同一 baseVersion 的提交：第二次必为 stale。
	if _, err := h.SetDesired("veh-003", map[string]any{"remote_lock": true}, base); err != nil {
		t.Fatalf("第一次提交: %v", err)
	}
	if _, err := h.SetDesired("veh-003", map[string]any{"remote_lock": false}, base); !errors.Is(err, ErrStaleUpdate) {
		t.Fatalf("过期 baseVersion 应 ErrStaleUpdate, got %v", err)
	}
}

func TestHeartbeatKeepsConnectionAlive(t *testing.T) {
	h, err := NewHub("127.0.0.1:0", func(vehicle, role, token string) bool {
		return token == "tok-"+vehicle
	}, 50*time.Millisecond)
	if err != nil {
		t.Fatal(err)
	}
	h.Start()
	defer h.Stop()
	c := dialAs(t, h, "veh-004", "panel")
	readText(t, c, 2*time.Second) // 初始 snapshot
	// 跨多个 ping 周期（>250ms）后仍能收发 → 客户端自动 pong 让服务端不判死。
	time.Sleep(300 * time.Millisecond)
	dev := dialAs(t, h, "veh-004", "device")
	msg, _ := json.Marshal(map[string]any{"op": "report", "reported": map[string]any{"speed": 1}})
	if err := dev.WriteMessage(opText, msg); err != nil {
		t.Fatal(err)
	}
	if snap := readText(t, c, 2*time.Second); snap["op"] != "snapshot" {
		t.Fatalf("心跳后连接不可用: %v", snap)
	}
}
