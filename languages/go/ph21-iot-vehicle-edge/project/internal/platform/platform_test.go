// 来源：ph21-iot-vehicle-edge project/internal/platform/platform_test.go
// 一句话说明：平台核心测试——批级幂等（重复批不二次生效但 ack 原样回）、坏批计数、
// 样本换算入库、告警计数、水位推进、鉴权失败计数与统计快照。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package platform

import (
	"errors"
	"testing"
	"time"

	"tenetlang/go/ph21-iot-vehicle-edge/project/internal/auth"
	"tenetlang/go/ph21-iot-vehicle-edge/project/internal/model"
)

// batch 构造上行批：样本 seq 从 seqBase 起单调（模拟车辆 seq 跨批递增，避免撞去重窗）。
func batch(gw string, id uint64, vin string, seqBase int, speeds ...float64) model.BatchUpload {
	var ss []model.Sample
	for i, sp := range speeds {
		ss = append(ss, model.Sample{Vin: vin, Seq: uint64(seqBase + i + 1), Speed: sp})
	}
	return model.BatchUpload{GatewayID: gw, BatchID: id, Samples: ss}
}

func TestHandleBatchIngestsAndDedups(t *testing.T) {
	c := NewCore(map[string]string{"edge-001": "s1"})
	now := time.Now()

	ack, err := c.HandleBatch(batch("edge-001", 1, "veh-001", 0, 30.0/3.6, 90.0/3.6), now)
	if err != nil || ack != 1 {
		t.Fatalf("首批应生效 ack=1, got %d err=%v", ack, err)
	}
	// 同批重放（网关断网重试原样重发）→ 幂等：不二次入库，ack 原样回 1。
	ack, err = c.HandleBatch(batch("edge-001", 1, "veh-001", 0, 30.0/3.6, 90.0/3.6), now)
	if err != nil || ack != 1 {
		t.Fatalf("重复批应幂等返回 ack=1, got %d err=%v", ack, err)
	}
	if got := c.Store().SampleCount(); got != 2 {
		t.Errorf("入库样本应 2（重复批不二次生效）, got %d", got)
	}
	if v, ok := c.Store().LatestSpeed("veh-001"); !ok || v != 90 {
		t.Errorf("最新速度应 90km/h, got %v ok=%v", v, ok)
	}
	ing, clean, dup, _, _, _ := c.Count.Snapshot()
	if ing != 2 || clean != 2 || dup != 1 { // dup=1：批级重放拦一次，样本不再重复处理
		t.Errorf("计数异常: ing=%d clean=%d dup=%d", ing, clean, dup)
	}
}

func TestHandleBatchBadBatch(t *testing.T) {
	c := NewCore(map[string]string{"edge-001": "s1"})
	bad := model.BatchUpload{GatewayID: "edge-001", BatchID: 2}
	if _, err := c.HandleBatch(bad, time.Now()); !errors.Is(err, ErrBadRequest) {
		t.Fatalf("坏批应 ErrBadRequest, got %v", err)
	}
	if _, _, _, _, b, _ := c.Count.Snapshot(); b != 1 {
		t.Errorf("坏批计数应 1, got %d", b)
	}
}

func TestWatermarkPerGateway(t *testing.T) {
	c := NewCore(map[string]string{"edge-001": "s1", "edge-002": "s2"})
	if _, err := c.HandleBatch(batch("edge-001", 3, "v1", 0, 30), time.Now()); err != nil {
		t.Fatal(err)
	}
	if _, err := c.HandleBatch(batch("edge-002", 1, "v2", 0, 30), time.Now()); err != nil {
		t.Fatal(err)
	}
	if ack := c.Store().Ack("edge-001"); ack != 3 {
		t.Errorf("edge-001 水位应 3, got %d", ack)
	}
	if ack := c.Store().Ack("edge-002"); ack != 1 {
		t.Errorf("edge-002 水位应 1, got %d", ack)
	}
}

func TestAlertCounting(t *testing.T) {
	c := NewCore(map[string]string{"edge-001": "s1"})
	// 135km/h → 超 120 warn；180km/h → 超 120 且超 160（2 条）。
	_, _ = c.HandleBatch(batch("edge-001", 1, "veh-001", 0, 135.0/3.6), time.Now())
	_, _ = c.HandleBatch(batch("edge-001", 2, "veh-001", 1, 180.0/3.6), time.Now()) // seq2 继续单调
	if _, _, _, _, _, alerts := c.Count.Snapshot(); alerts != 3 {
		t.Errorf("告警计数应 3, got %d", alerts)
	}
}

func TestVerifyGatewayAuth(t *testing.T) {
	c := NewCore(map[string]string{"edge-001": "s1"})
	if err := c.VerifyGateway("edge-001", "bad-token", time.Now()); !errors.Is(err, auth.ErrUnauthorized) {
		t.Fatalf("坏 token 应拒绝, got %v", err)
	}
	if _, _, _, fail, _, _ := c.Count.Snapshot(); fail != 1 {
		t.Errorf("鉴权失败计数应 1, got %d", fail)
	}
}

func TestAlertCountingOverspeedOnly(t *testing.T) {
	c := NewCore(map[string]string{"edge-001": "s1"})
	if _, err := c.HandleBatch(batch("edge-001", 1, "veh-001", 0, 100.0/3.6), time.Now()); err != nil {
		t.Fatal(err)
	}
	if _, _, _, _, _, alerts := c.Count.Snapshot(); alerts != 0 {
		t.Errorf("限速内不应告警, got %d", alerts)
	}
}
