// 来源：ph21-data-ingest-gateway examples/ex05-relay-collector/ex05_test.go
// 一句话说明：采集器四件套测试——长度前缀切帧、本地聚合满批触发、spool 有界与
// ack 水位裁剪、断网→入池→恢复→补传→水位归零的端到端故事（主文档 3.5/3.11/4.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"bytes"
	"context"
	"errors"
	"io"
	"log"
	"testing"
)

// ---------- frame ----------

func TestFrameRoundTrip(t *testing.T) {
	payload := []byte(`{"type":"metrics","len":17}`)
	f, err := EncodeFrame(payload)
	if err != nil {
		t.Fatal(err)
	}
	got, err := readFrame(bytes.NewReader(f))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, payload) {
		t.Errorf("帧往返不一致: %q", got)
	}
}

func TestReadFrameRejectsTruncated(t *testing.T) {
	f, _ := EncodeFrame(make([]byte, 50))
	if _, err := readFrame(bytes.NewReader(f[:10])); err == nil {
		t.Error("截断帧应报错")
	}
	// 头部声称 1 字节负载但给空 → 读负载必须 EOF（包装后仍应 errors.Is 命中）。
	if _, err := readFrame(bytes.NewReader([]byte{0, 1})); !errors.Is(err, io.EOF) {
		t.Errorf("空负载截断应报 EOF, got %v", err)
	}
}

func TestEncodeFrameTooBig(t *testing.T) {
	if _, err := EncodeFrame(make([]byte, maxFrameSize+1)); err == nil {
		t.Error("超大帧应报错")
	}
}

// ---------- aggregator ----------

func TestCollectorFlushOnThreshold(t *testing.T) {
	var flushed []Batch
	col := NewCollector("relay-1", 3, func(b Batch) { flushed = append(flushed, b) })
	for i := 1; i <= 5; i++ {
		col.Add(Sample{SourceID: "src-001", Seq: uint64(i)})
	}
	if len(flushed) != 1 {
		t.Fatalf("满 3 条应 flush 1 批, got %d", len(flushed))
	}
	if col.PendingCount() != 2 {
		t.Errorf("剩余缓冲应 2 条, got %d", col.PendingCount())
	}
	if from, to, _ := flushed[0].seqRange(); from != 1 || to != 3 {
		t.Errorf("首批 seq 区间应 [1,3], got [%d,%d]", from, to)
	}
}

// ---------- spool ----------

func TestSpoolBoundedAndWatermark(t *testing.T) {
	s := NewSpool(2)
	if err := s.Enqueue(Batch{BatchID: 1}); err != nil {
		t.Fatal(err)
	}
	if err := s.Enqueue(Batch{BatchID: 2}); err != nil {
		t.Fatal(err)
	}
	if err := s.Enqueue(Batch{BatchID: 3}); !errors.Is(err, ErrSpoolFull) {
		t.Fatalf("超容量应 ErrSpoolFull, got %v", err)
	}
	s.AckUpTo(1)
	if s.Len() != 1 || s.AckSeq() != 1 {
		t.Errorf("ack=1 后应剩 1 批, Len=%d Ack=%d", s.Len(), s.AckSeq())
	}
	s.AckUpTo(1) // 水位只进不退
	if s.AckSeq() != 1 {
		t.Errorf("重复 ack 不应倒退: %d", s.AckSeq())
	}
	s.AckUpTo(2)
	if s.Len() != 0 {
		t.Errorf("ack=2 后应清空, Len=%d", s.Len())
	}
}

// ---------- collector e2e ----------

// flakyUplink 测试用假云端：offline 时全失败；恢复后按 batchID 幂等并回水位。
type flakyUplink struct {
	offline bool
	seen    map[uint64]bool
	ack     uint64
}

func (c *flakyUplink) SendBatch(_ context.Context, b Batch) (uint64, error) {
	if c.offline {
		return c.ack, errors.New("模拟断网")
	}
	if !c.seen[b.BatchID] {
		c.seen[b.BatchID] = true
		if b.BatchID == c.ack+1 {
			c.ack = b.BatchID
		}
	}
	return c.ack, nil
}

func TestCollectorOfflineCacheThenBackfill(t *testing.T) {
	cloud := &flakyUplink{seen: map[uint64]bool{}}
	gw := NewRelay("relay-t", 32, cloud, log.New(io.Discard, "", 0))
	col := NewCollector("relay-t", 2, gw.HandleBatch)

	// 断网期间 8 条样本 → 4 批全部入 spool。
	cloud.offline = true
	for i := 1; i <= 8; i++ {
		col.Add(Sample{SourceID: "src-001", Seq: uint64(i)})
	}
	if _, queued := gw.Stats(); queued != 4 {
		t.Fatalf("断网应入池 4 批, got %d", queued)
	}
	if gw.spool.Len() != 4 {
		t.Fatalf("spool 待补传应 4, got %d", gw.spool.Len())
	}

	// 恢复后补传：全部确认、水位归满、spool 清空。
	cloud.offline = false
	n, all := gw.Flush(context.Background())
	if !all || n != 4 {
		t.Fatalf("补传应 4 批全部确认, n=%d all=%v", n, all)
	}
	if cloud.ack != 4 || gw.spool.Len() != 0 {
		t.Errorf("水位应到 4、spool 应清空: ack=%d len=%d", cloud.ack, gw.spool.Len())
	}
	// 云端幂等：同一批重复投递只记一次（seen 大小 = 4）。
	if len(cloud.seen) != 4 {
		t.Errorf("云端应只生效 4 个唯一批, got %d", len(cloud.seen))
	}
}

func TestCollectorBackfillKeepsOriginalSeqs(t *testing.T) {
	// 断网 3 批（batchID 2/3/4 原号保留，不重新编号）；恢复后按序补传，
	// 云端幂等窗按 batchID 去重，水位推进到全部确认——"补传是重放不是再生成"。
	cloud := &flakyUplink{seen: map[uint64]bool{}}
	gw := NewRelay("relay-t", 8, cloud, log.New(io.Discard, "", 0))
	col := NewCollector("relay-t", 2, gw.HandleBatch)

	// 前两批正常上行（1、2），随后断网两批（3、4）。
	for i := 1; i <= 4; i++ {
		col.Add(Sample{SourceID: "src-001", Seq: uint64(i)})
	}
	cloud.offline = true
	for i := 5; i <= 8; i++ {
		col.Add(Sample{SourceID: "src-001", Seq: uint64(i)})
	}
	queuedPending := gw.spool.Pending()
	if len(queuedPending) != 2 || queuedPending[0].BatchID != 3 || queuedPending[1].BatchID != 4 {
		t.Fatalf("spool 应含原号批 3/4: %+v", queuedPending)
	}
	cloud.offline = false
	if _, all := gw.Flush(context.Background()); !all {
		t.Fatal("补传应全部确认")
	}
	if cloud.ack != 4 || len(cloud.seen) != 4 {
		t.Errorf("水位应 4、云端应 4 个唯一批: ack=%d seen=%d", cloud.ack, len(cloud.seen))
	}
}
