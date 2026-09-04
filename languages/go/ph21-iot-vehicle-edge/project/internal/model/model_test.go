// 来源：ph21-iot-vehicle-edge project/internal/model/model_test.go
// 一句话说明：线路模型测试——合法批通过、空网关/空批号/空样本/超量程/样本越界全被拒。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package model

import (
	"errors"
	"testing"
)

func sample(vin string, seq uint64, speed float64) Sample {
	return Sample{Vin: vin, Seq: seq, Speed: speed, Ts: 1}
}

func TestValidateOK(t *testing.T) {
	b := BatchUpload{GatewayID: "edge-001", BatchID: 7, Samples: []Sample{sample("veh-001", 1, 30)}}
	if err := b.Validate(); err != nil {
		t.Fatalf("合法批应通过: %v", err)
	}
}

func TestValidateRejects(t *testing.T) {
	cases := []BatchUpload{
		{BatchID: 1, Samples: []Sample{sample("v", 1, 30)}},                  // 空网关
		{GatewayID: "e", Samples: []Sample{sample("v", 1, 30)}},              // 批号 0
		{GatewayID: "e", BatchID: 1},                                         // 空样本
		{GatewayID: "e", BatchID: 1, Samples: []Sample{sample("", 1, 30)}},   // 空 vin
		{GatewayID: "e", BatchID: 1, Samples: []Sample{sample("v", 0, 30)}},  // seq 0
		{GatewayID: "e", BatchID: 1, Samples: []Sample{sample("v", 1, -5)}},  // 负速度
		{GatewayID: "e", BatchID: 1, Samples: []Sample{sample("v", 1, 500)}}, // 超量程
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
	if err := (BatchUpload{GatewayID: "e", BatchID: 2, Samples: big}).Validate(); !errors.Is(err, ErrBadBatch) {
		t.Error("超批上限应拒绝")
	}
}
