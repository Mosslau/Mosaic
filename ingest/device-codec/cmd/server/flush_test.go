package main

import (
	"context"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/segmentio/kafka-go"

	"github.com/Mosslau/OceanVerse/ingest/device-contracts/vehicle"
)

// counterValue 从 Prometheus 默认注册表读取一个 CounterVec 的当前值(按标签筛选)。
// 用注册表而不是 /metrics 文本, 避免测试依赖 HTTP 层。
func counterValue(t *testing.T, name, label, value string) float64 {
	t.Helper()
	mfs, err := prometheus.DefaultGatherer.Gather()
	if err != nil {
		t.Fatalf("gather 指标失败: %v", err)
	}
	for _, mf := range mfs {
		if mf.GetName() != name {
			continue
		}
		for _, m := range mf.GetMetric() {
			for _, lp := range m.GetLabel() {
				if lp.GetName() == label && lp.GetValue() == value {
					return m.GetCounter().GetValue()
				}
			}
		}
	}
	return 0
}

// ---- 测试替身: 可控失败的 writer / committer --------------------------------

type fakeWriter struct {
	writes [][]kafka.Message
	err    error
}

func (f *fakeWriter) WriteMessages(_ context.Context, msgs ...kafka.Message) error {
	if f.err != nil {
		// 失败时不记录, 模拟"未写出"
		return f.err
	}
	cp := make([]kafka.Message, len(msgs))
	copy(cp, msgs)
	f.writes = append(f.writes, cp)
	return nil
}

func (f *fakeWriter) total() int {
	n := 0
	for _, w := range f.writes {
		n += len(w)
	}
	return n
}

type fakeCommitter struct {
	commits [][]kafka.Message
	err     error
}

func (f *fakeCommitter) CommitMessages(_ context.Context, msgs ...kafka.Message) error {
	if f.err != nil {
		return f.err
	}
	cp := make([]kafka.Message, len(msgs))
	copy(cp, msgs)
	f.commits = append(f.commits, cp)
	return nil
}

func (f *fakeCommitter) total() int {
	n := 0
	for _, c := range f.commits {
		n += len(c)
	}
	return n
}

// newTestState 造一个含 2 条原始消息、1 条产出、1 条 DLQ 的缓冲。
func newTestState() *batchState {
	return &batchState{
		pendingReports: []pendingReport{{
			msg:      kafka.Message{Key: []byte("VIN1"), Value: []byte(`{"vin":"VIN1"}`)},
			typeName: "vehicle_status",
		}},
		pendingDLQ: []pendingDLQItem{{
			msg:   kafka.Message{Key: []byte("VIN2"), Value: []byte(`{"stage":"parse"}`)},
			stage: "parse",
		}},
		pendingMsgs: []kafka.Message{
			{Key: []byte("VIN1"), Value: []byte(`{"vin":"VIN1","proto_ver":"v1"}`)},
			{Key: []byte("VIN2"), Value: []byte(`{"vin":"VIN2","proto_ver":"v1"}`)},
		},
	}
}

// ---- 核心回归: 失败必须保留缓冲(P0 静默丢数据的根因) ------------------------

// TestFlushBatch_DLQFailureDoesNotBlockMainPath DLQ 写失败**不得**拖住主链路(2026-09-20 收窄)。
//
// 修复前的语义: dlq 写失败 → ok=false → 整批(含已成功写出的正常产出)滞留 + 位移不推进 →
// "一条脏数据的 DLQ topic 故障"会把正常数据的实时性一起拖垮。
// 修复后的语义: DLQ 写失败只保留 **DLQ 条目**(逐条重试), 产出照常提交位移并放行。
//
// 数据不丢的根据没有变: 产出仍"写出成功 == 提交成功"才离开缓冲; DLQ 条目仍在缓冲里等重试。
func TestFlushBatch_DLQFailureDoesNotBlockMainPath(t *testing.T) {
	st := newTestState()
	pw := &fakeWriter{}
	dw := &fakeWriter{err: errors.New("dlq topic missing")}
	c := &fakeCommitter{}

	if flushBatch(context.Background(), st, pw, dw, c, time.Now()) {
		t.Error("DLQ 未全部写出时返回值应为 false(调用方据此知道还有未推进的部分)")
	}
	// 主链路必须已推进: 产出写出 + 位移提交
	if pw.total() != 1 {
		t.Errorf("产出应已写出 1 条, 实际 %d", pw.total())
	}
	if c.total() != 2 {
		t.Errorf("产出成功后应提交 2 条位移, 实际 %d", c.total())
	}
	if len(st.pendingMsgs) != 0 {
		t.Errorf("原始消息应已推进(缓冲清空), 实际残留 %d", len(st.pendingMsgs))
	}
	if len(st.pendingReports) != 0 {
		t.Errorf("产出应已清空, 实际残留 %d", len(st.pendingReports))
	}
	// DLQ 条目必须保留(逐条重试), 且不丢
	if len(st.pendingDLQ) != 1 {
		t.Fatalf("DLQ 写失败后条目必须保留待重试, 实际 %d", len(st.pendingDLQ))
	}
	// 失败必须可观测(否则"DLQ 一直写不出去"只剩日志里一行)
	if got := counterValue(t, "codec_dlq_flush_failures_total", "stage", "parse"); got == 0 {
		t.Error("codec_dlq_flush_failures_total{stage=parse} 应 >0")
	}

	// DLQ 恢复后: 只重投 DLQ, 不重复投产出(产出已在上一步 ACK)
	before := pw.total()
	dw.err = nil
	if !flushBatch(context.Background(), st, pw, dw, c, time.Now()) {
		t.Fatal("参考 DLQ 恢复后 flush 应完全成功")
	}
	if len(st.pendingDLQ) != 0 {
		t.Errorf("DLQ 恢复后条目应清空, 实际 %d", len(st.pendingDLQ))
	}
	if pw.total() != before {
		t.Error("产出不得被重复投递(已 ACK 的批次不再回到缓冲)")
	}
	// 注意: 此时 pendingMsgs 已空, 真实主循环里由定时 flush 推进; 这里直接调用的语义是"DLQ 重试"
}

// TestFlushBatch_WriteFailureKeepsBuffer 是本次修复的核心回归测试。
// 修复前: 写失败后 pending 三切片被无条件 [:0] 清空 → 位移未提交但这批消息已离开流水线,
// 下一次成功 flush 提交更高 offset → 永久静默丢数据(at-least-once 承诺失效)。
func TestFlushBatch_WriteFailureKeepsBuffer(t *testing.T) {
	st := newTestState()
	pw := &fakeWriter{err: errors.New("kafka: connection refused")}
	dw := &fakeWriter{}
	c := &fakeCommitter{}

	ok := flushBatch(context.Background(), st, pw, dw, c, time.Now())

	if ok {
		t.Fatal("写失败时 flushBatch 必须返回 false")
	}
	// 不变量 1: 缓冲原样保留(一条都不能少)。
	// DLQ 会**先于**产出被尝试写出(见 flushBatch 顺序), 故此时 DLQ 条目已被投出并从缓冲移除 ——
	// 但它对应的原始消息仍在 pendingMsgs 里, 位移未提交 → 重读时会重新产出 DLQ(至多一次重复投递),
	// 不存在"丢了"的路径。
	if len(st.pendingMsgs) != 2 || len(st.pendingReports) != 1 {
		t.Fatalf("写失败后缓冲必须保留, got msgs=%d reports=%d", len(st.pendingMsgs), len(st.pendingReports))
	}
	// 不变量 2: 位移绝不提交(否则消息永远不会被重读)
	if c.total() != 0 {
		t.Fatalf("写失败时不得提交位移, 实际提交了 %d 条", c.total())
	}
	// 不变量 3: 必须退避(避免失败风暴刷屏)
	if !st.retryNotBefore.After(time.Now().Add(-time.Second)) {
		t.Fatal("失败后必须设置退避截止时间")
	}
	if st.failures != 1 {
		t.Fatalf("连续失败计数应为 1, got %d", st.failures)
	}
}

// TestFlushBatch_CommitFailureKeepsBuffer 位移提交失败同样不能清空缓冲。
func TestFlushBatch_CommitFailureKeepsBuffer(t *testing.T) {
	st := newTestState()
	pw, dw := &fakeWriter{}, &fakeWriter{}
	c := &fakeCommitter{err: errors.New("offset commit failed")}

	ok := flushBatch(context.Background(), st, pw, dw, c, time.Now())

	if ok {
		t.Fatal("位移提交失败时 flushBatch 必须返回 false")
	}
	if len(st.pendingMsgs) != 2 || len(st.pendingReports) != 1 {
		t.Fatalf("提交失败后缓冲必须保留, got msgs=%d reports=%d", len(st.pendingMsgs), len(st.pendingReports))
	}
	if pw.total() != 1 {
		t.Fatalf("产出应已写出 1 条, got %d", pw.total())
	}
}

// TestFlushBatch_RetryAfterBackoffSucceeds 退避期内不重试, 退避结束后重试成功并清空。
func TestFlushBatch_RetryAfterBackoffSucceeds(t *testing.T) {
	st := newTestState()
	pw := &fakeWriter{err: errors.New("boom")}
	dw, c := &fakeWriter{}, &fakeCommitter{}
	t0 := time.Now()

	if flushBatch(context.Background(), st, pw, dw, c, t0) {
		t.Fatal("首次应失败")
	}
	// 退避窗口内: 不应重试(不产生新的写入尝试)
	if flushBatch(context.Background(), st, pw, dw, c, t0.Add(10*time.Millisecond)) {
		t.Fatal("退避窗口内不应重试")
	}
	if len(st.pendingMsgs) != 2 {
		t.Fatal("退避窗口内缓冲必须保持")
	}
	// 退避结束后恢复: 重试成功 → 清空 + 提交位移
	pw.err = nil
	if !flushBatch(context.Background(), st, pw, dw, c, t0.Add(time.Second)) {
		t.Fatal("退避结束后恢复重试应成功")
	}
	if len(st.pendingMsgs) != 0 || len(st.pendingReports) != 0 || len(st.pendingDLQ) != 0 {
		t.Fatal("成功后缓冲必须清空")
	}
	if c.total() != 2 {
		t.Fatalf("成功后应提交 2 条位移, got %d", c.total())
	}
	if st.failures != 0 {
		t.Fatalf("成功后连续失败计数必须归零, got %d", st.failures)
	}
}

// TestFlushBatch_EmptyBufferNoop 空缓冲不触发任何写入/提交。
func TestFlushBatch_EmptyBufferNoop(t *testing.T) {
	st := &batchState{}
	pw, dw, c := &fakeWriter{}, &fakeWriter{}, &fakeCommitter{}
	if !flushBatch(context.Background(), st, pw, dw, c, time.Now()) {
		t.Fatal("空缓冲应视为成功(无操作)")
	}
	if pw.total()+dw.total()+c.total() != 0 {
		t.Fatal("空缓冲不得产生写入或提交")
	}
}

// ---- process / handleMessage ------------------------------------------------

func TestProcess_UnknownProtoVerGoesToEnvelopeDLQ(t *testing.T) {
	_, dlqs := process([]byte(`{"vin":"VIN1","proto_ver":"v9","payload":"IyM="}`))
	if len(dlqs) != 1 || dlqs[0].Stage != "envelope" {
		t.Fatalf("未知 proto_ver 应进 envelope DLQ, got %+v", dlqs)
	}
	if !strings.Contains(dlqs[0].Reason, "v9") {
		t.Fatalf("DLQ 原因应包含实际版本号, got %q", dlqs[0].Reason)
	}
}

func TestProcess_BadBase64GoesToEnvelopeDLQ(t *testing.T) {
	_, dlqs := process([]byte(`{"vin":"VIN1","proto_ver":"v1","payload":"!!!not-base64!!!"}`))
	if len(dlqs) != 1 || dlqs[0].Stage != "envelope" {
		t.Fatalf("base64 失败应进 envelope DLQ, got %+v", dlqs)
	}
}

func TestProcess_BadFrameGoesToParseDLQ(t *testing.T) {
	// 合法 base64 但不是 GB/T 32960 帧(无 ## 起始符)
	_, dlqs := process([]byte(`{"vin":"VIN1","proto_ver":"v1","payload":"AAAA"}`))
	if len(dlqs) != 1 || dlqs[0].Stage != "parse" {
		t.Fatalf("帧解析失败应进 parse DLQ, got %+v", dlqs)
	}
}

// goldenFrameHex 58B 黄金样本帧(与 gbt32960 包、simframe、映射文档示例一致): 0x08 + 0x09。
// 这里内嵌而非跨包引用, 避免 cmd 层测试依赖 internal 包的测试辅助函数。
const goldenFrameHex = "232302fe" +
	"4f56323032363030303100000000000000" +
	"01" + "0021" +
	"1a09110c1e00" +
	"080101025a26dd00040001040ccc0cd00cc10cc7" +
	"0901010002474b" +
	"65"

// TestHandleMessage_ValidFrameProducesReports 走通"信封 → 帧 → L2 产出"整条路径。
func TestHandleMessage_ValidFrameProducesReports(t *testing.T) {
	frame, err := hex.DecodeString(goldenFrameHex)
	if err != nil {
		t.Fatalf("黄金样本 hex 非法: %v", err)
	}
	env, err := json.Marshal(rawEnvelope{
		VIN: "OV20260001", Ts: 1758000000, ProtoVer: "v1", Cmd: 0x01,
		Payload: base64.StdEncoding.EncodeToString(frame),
	})
	if err != nil {
		t.Fatal(err)
	}

	st := &batchState{}
	handleMessage(st, kafka.Message{Key: []byte("OV20260001"), Value: env})

	if len(st.pendingReports) == 0 {
		t.Fatalf("合法帧应产出 L2 报告, got reports=%d dlq=%d", len(st.pendingReports), len(st.pendingDLQ))
	}
	if len(st.pendingMsgs) != 1 {
		t.Fatalf("原始消息应入待提交队列, got %d", len(st.pendingMsgs))
	}
	// 产出必须是合法 JSON 且能解回契约
	var vr vehicle.VehicleReport
	if err := json.Unmarshal(st.pendingReports[0].msg.Value, &vr); err != nil {
		t.Fatalf("产出应为合法 VehicleReport JSON: %v", err)
	}
	if vr.VIN == "" || vr.Type == "" {
		t.Fatalf("产出缺少 VIN/type: %+v", vr)
	}
}

// TestShouldFlush 攒批阈值: 200 条触发。
func TestShouldFlush(t *testing.T) {
	st := &batchState{}
	if shouldFlush(st) {
		t.Fatal("空缓冲不应触发 flush")
	}
	st.pendingMsgs = make([]kafka.Message, 199)
	if shouldFlush(st) {
		t.Fatal("199 条不应触发 flush")
	}
	st.pendingMsgs = append(st.pendingMsgs, kafka.Message{})
	if !shouldFlush(st) {
		t.Fatal("200 条应触发 flush")
	}
}
