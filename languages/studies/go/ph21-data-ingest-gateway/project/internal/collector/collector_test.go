// 来源：ph21-data-ingest-gateway project/internal/collector/collector_test.go
// 一句话说明：采集器核心测试——聚合满批、spool 有界与水位、断网→入池→恢复→补传
// e2e（fake uplink）、HTTP 上行传输的 401/503/200-ack 语义。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package collector

import (
	"context"
	"errors"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"testing"

	"tenetlang/go/ph21-data-ingest-gateway/project/internal/auth"
	"tenetlang/go/ph21-data-ingest-gateway/project/internal/model"
)

func gsample(sourceID string, seq uint64) model.Sample {
	return model.Sample{SourceID: sourceID, Seq: seq, Value: 30}
}

func TestCollectorFlushOnThreshold(t *testing.T) {
	var got []model.BatchUpload
	c := NewCollector(3, func(b model.BatchUpload) { got = append(got, b) })
	for i := 1; i <= 4; i++ {
		c.Add("relay-001", gsample("src-001", uint64(i)))
	}
	if len(got) != 1 || got[0].BatchID != 1 {
		t.Fatalf("应 flush 1 批且批号 1, got %+v", got)
	}
}

func TestSpoolWatermarkAndBounded(t *testing.T) {
	s := NewSpool(2)
	if err := s.Enqueue(model.BatchUpload{BatchID: 1}); err != nil {
		t.Fatal(err)
	}
	if err := s.Enqueue(model.BatchUpload{BatchID: 2}); err != nil {
		t.Fatal(err)
	}
	if err := s.Enqueue(model.BatchUpload{BatchID: 3}); !errors.Is(err, ErrSpoolFull) {
		t.Fatalf("超容量应 ErrSpoolFull, got %v", err)
	}
	s.AckUpTo(1)
	if s.Len() != 1 || s.AckSeq() != 1 {
		t.Errorf("ack=1 后 Len=%d Ack=%d", s.Len(), s.AckSeq())
	}
	s.AckUpTo(1) // 只进不退
	if s.AckSeq() != 1 {
		t.Error("重复 ack 不应倒退")
	}
}

// fakeUplink 可开关的假上行。
type fakeUplink struct {
	offline bool
	seen    map[uint64]bool
	ack     uint64
}

func (f *fakeUplink) SendBatch(_ context.Context, b model.BatchUpload) (uint64, error) {
	if f.offline {
		return f.ack, errors.New("net down")
	}
	if !f.seen[b.BatchID] {
		f.seen[b.BatchID] = true
		if b.BatchID == f.ack+1 {
			f.ack = b.BatchID
		}
	}
	return f.ack, nil
}

func TestCollectorOfflineThenBackfill(t *testing.T) {
	cloud := &fakeUplink{seen: map[uint64]bool{}}
	gw := NewRelay("relay-t", 32, cloud, log.New(io.Discard, "", 0))
	col := NewCollector(2, gw.HandleBatch)

	cloud.offline = true
	for i := 1; i <= 8; i++ { // 8 条 → 4 批全部入 spool
		col.Add("relay-t", gsample("src-001", uint64(i)))
	}
	if gw.Pending() != 4 {
		t.Fatalf("应 4 批待传, got %d", gw.Pending())
	}
	cloud.offline = false
	if n, all := gw.Flush(context.Background()); !all || n != 4 {
		t.Fatalf("补传应 4 批全确认, n=%d all=%v", n, all)
	}
	if cloud.ack != 4 || gw.Pending() != 0 {
		t.Errorf("水位应 4、spool 应空: ack=%d pending=%d", cloud.ack, gw.Pending())
	}
	if _, queued, _ := gw.Stats(); queued != 4 {
		t.Errorf("入池计数应 4, got %d", queued)
	}
}

// ---------- HTTP 传输层 ----------

func TestHTTPUplinkAuthFailure(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}))
	defer ts.Close()
	up := NewHTTPUplink(ts.URL, "relay-001", "wrong-secret")
	_, err := up.SendBatch(context.Background(), model.BatchUpload{CollectorID: "relay-001", BatchID: 1, Samples: []model.Sample{gsample("v", 1)}})
	if !errors.Is(err, auth.ErrUnauthorized) {
		t.Fatalf("401 应包 ErrUnauthorized, got %v", err)
	}
}

func TestHTTPUplink503Retryable(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer ts.Close()
	up := NewHTTPUplink(ts.URL, "relay-001", "s")
	_, err := up.SendBatch(context.Background(), model.BatchUpload{CollectorID: "relay-001", BatchID: 1, Samples: []model.Sample{gsample("v", 1)}})
	if err == nil || errors.Is(err, auth.ErrUnauthorized) {
		t.Fatalf("503 应为可重试错误, got %v", err)
	}
}

func TestHTTPUplinkAckOK(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = io.WriteString(w, `{"ack":7}`)
	}))
	defer ts.Close()
	up := NewHTTPUplink(ts.URL, "relay-001", "s")
	ack, err := up.SendBatch(context.Background(), model.BatchUpload{CollectorID: "relay-001", BatchID: 7, Samples: []model.Sample{gsample("v", 1)}})
	if err != nil || ack != 7 {
		t.Fatalf("应解析 ack=7, got %d err=%v", ack, err)
	}
}
