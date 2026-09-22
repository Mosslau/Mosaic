// 来源：ph21-data-ingest-gateway project/internal/model/model.go
// 一句话说明：跨采集器/云端共享的线路模型——BatchUpload 是上行线格式（采集器聚合
// 出的批，JSON），Sample 是其中一条采集端样本。清洗校验在平台侧做，见 platform。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 测试：go test ./...   验证状态：已验证（go1.25.6 本机实测全绿）
package model

import (
	"errors"
	"fmt"
)

// Sample 一条采集端样本。Seq 由采集器在采集端分配且终身不变（幂等键，主文档 3.3/4.3）。
type Sample struct {
	SourceID string  `json:"sourceID"`
	Seq      uint64  `json:"seq"`
	Value    float64 `json:"value"` // 原始计数（采集端单位：0.1%）
	Ts       int64   `json:"ts"`
}

// BatchUpload 采集代理上行的一批样本（线格式）。
type BatchUpload struct {
	CollectorID string   `json:"collector_id"`
	BatchID     uint64   `json:"batch_id"`
	Samples     []Sample `json:"samples"`
}

// ErrBadBatch 线路报文不合法（坏数据进"接入台账"，主文档 3.7 纪律）。
var ErrBadBatch = errors.New("model: 非法上行批")

const (
	// MaxSamplesPerBatch 单批上限：聚合器与校验共用同一纪律。
	MaxSamplesPerBatch = 256
	// ValueMin / ValueMax 采集量值量程（0.1% 计数）。
	ValueMin = 0.0
	ValueMax = 1000.0
)

// Validate 校验上行批：采集器/批号/样本集合/每条样本的量程与序号。
func (b BatchUpload) Validate() error {
	if b.CollectorID == "" {
		return fmt.Errorf("%w: 采集器 ID 为空", ErrBadBatch)
	}
	if b.BatchID == 0 {
		return fmt.Errorf("%w: 批号非法", ErrBadBatch)
	}
	if len(b.Samples) == 0 || len(b.Samples) > MaxSamplesPerBatch {
		return fmt.Errorf("%w: 批内样本数 %d 非法", ErrBadBatch, len(b.Samples))
	}
	for i, s := range b.Samples {
		if s.SourceID == "" {
			return fmt.Errorf("%w: 第 %d 条 sourceID 为空", ErrBadBatch, i)
		}
		if s.Seq == 0 {
			return fmt.Errorf("%w: 第 %d 条 seq 非法", ErrBadBatch, i)
		}
		if s.Value < ValueMin || s.Value > ValueMax {
			return fmt.Errorf("%w: 第 %d 条 value=%v 超量程 [%v,%v]",
				ErrBadBatch, i, s.Value, ValueMin, ValueMax)
		}
	}
	return nil
}

// CleanSample 清洗后（换算为 %%、以到达时间对齐）的可入库样本。
type CleanSample struct {
	SourceID string
	Seq      uint64
	ValuePct float64
	TsUnix   int64 // 平台到达时间（对齐时基；采集端时钟偏差见主文档 3.7）
}
