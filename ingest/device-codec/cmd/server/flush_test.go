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

	"github.com/segmentio/kafka-go"

	"github.com/Mosslau/OceanVerse/ingest/device-contracts/vehicle"
)

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
	// 不变量 1: 缓冲原样保留(一条都不能少)
	if len(st.pendingMsgs) != 2 || len(st.pendingReports) != 1 || len(st.pendingDLQ) != 1 {
		t.Fatalf("写失败后缓冲必须保留, got msgs=%d reports=%d dlq=%d",
			len(st.pendingMsgs), len(st.pendingReports), len(st.pendingDLQ))
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
	if len(st.pendingMsgs) != 2 || len(st.pendingReports) != 1 || len(st.pendingDLQ) != 1 {
		t.Fatalf("提交失败后缓冲必须保留, got msgs=%d reports=%d dlq=%d",
			len(st.pendingMsgs), len(st.pendingReports), len(st.pendingDLQ))
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

// TestFlushBatch_DLQFailureKeepsBuffer DLQ 写不出去同样不能丢(否则原始帧无法事后重放)。
func TestFlushBatch_DLQFailureKeepsBuffer(t *testing.T) {
	st := newTestState()
	pw := &fakeWriter{}
	dw := &fakeWriter{err: errors.New("dlq topic missing")}
	c := &fakeCommitter{}

	if flushBatch(context.Background(), st, pw, dw, c, time.Now()) {
		t.Fatal("DLQ 写失败时 flushBatch 必须返回 false")
	}
	if len(st.pendingMsgs) != 2 || len(st.pendingDLQ) != 1 {
		t.Fatal("DLQ 写失败后缓冲必须保留")
	}
	if c.total() != 0 {
		t.Fatal("DLQ 写失败时不得提交位移")
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
