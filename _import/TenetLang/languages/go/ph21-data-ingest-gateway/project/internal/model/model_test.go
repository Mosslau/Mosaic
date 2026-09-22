// 来源：ph21-data-ingest-gateway project/internal/model/model_test.go
// 一句话说明：线路模型测试——合法批通过、空采集器/空批号/空样本/超量程/样本越界全被拒。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package model

import (
	"errors"
	"testing"
)

func sample(sourceID string, seq uint64, value float64) Sample {
	return Sample{SourceID: sourceID, Seq: seq, Value: value, Ts: 1}
}

func TestValidateOK(t *testing.T) {
	b := BatchUpload{CollectorID: "relay-001", BatchID: 7, Samples: []Sample{sample("src-001", 1, 30)}}
	if err := b.Validate(); err != nil {
		t.Fatalf("合法批应通过: %v", err)
	}
}

func TestValidateRejects(t *testing.T) {
	cases := []BatchUpload{
		{BatchID: 1, Samples: []Sample{sample("v", 1, 30)}},                     // 空采集器
		{CollectorID: "e", Samples: []Sample{sample("v", 1, 30)}},               // 批号 0
		{CollectorID: "e", BatchID: 1},                                          // 空样本
		{CollectorID: "e", BatchID: 1, Samples: []Sample{sample("", 1, 30)}},    // 空 sourceID
		{CollectorID: "e", BatchID: 1, Samples: []Sample{sample("v", 0, 30)}},   // seq 0
		{CollectorID: "e", BatchID: 1, Samples: []Sample{sample("v", 1, -5)}},   // 负量值
		{CollectorID: "e", BatchID: 1, Samples: []Sample{sample("v", 1, 1200)}}, // 超量程
	}
	for i, b := range cases {
		if err := b.Validate(); !errors.Is(err, ErrBadBatch) {
			t.Errorf("case %d 应 ErrBadBatch, got %v", i, err)
		}
	}
	// 超批上限。
	big := make([]Sample, MaxSamplesPerBatch+1)
	for i := range big {
		big[i] = sample("v", uint64(i+1), 10)
	}
	if err := (BatchUpload{CollectorID: "e", BatchID: 2, Samples: big}).Validate(); !errors.Is(err, ErrBadBatch) {
		t.Error("超批上限应拒绝")
	}
}
