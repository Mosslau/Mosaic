// 来源：ph21-data-ingest-gateway examples/ex05-relay-collector/metrics.go
// 一句话说明：采集端样本与上行批模型——样本带单调 seq（幂等键），批是"同数据源一段
// 连续 seq 的打包上行"。seq 出生即固定，补传是重放同一 seq 区间（主文档 3.3/4.3）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...   测试：go test ./...   静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿）
package main

import (
	"encoding/binary"
	"errors"
	"fmt"
	"io"
)

// Sample 一条采集端指标样本。Seq 由采集器在采集时分配（本地单调、重启由 spool 续）。
type Sample struct {
	SourceID string  `json:"sourceID"`
	Seq      uint64  `json:"seq"`
	Value    float64 `json:"value"`
	Ts       int64   `json:"ts"`
}

// Batch 上行批：同一采集器、同一批内是若干样本（云端按 (sourceID, batchID) 幂等）。
type Batch struct {
	BatchID     uint64   `json:"batch_id"`
	CollectorID string   `json:"collector_id"`
	Samples     []Sample `json:"samples"`
}

// 帧长度前缀切帧（主文档 3.5）：先 2 字节大端长度再负载。
const (
	frameHeadSize = 2
	maxFrameSize  = 1 << 16
)

// EncodeFrame 把负载包成 [2B 长度][负载] 帧。
func EncodeFrame(payload []byte) ([]byte, error) {
	if len(payload) > maxFrameSize {
		return nil, fmt.Errorf("帧负载 %d 超上限 %d", len(payload), maxFrameSize)
	}
	buf := make([]byte, frameHeadSize, frameHeadSize+len(payload))
	binary.BigEndian.PutUint16(buf, uint16(len(payload)))
	return append(buf, payload...), nil
}

// readFrame 按长度前缀切帧：读不满就报错，绝不把残余字节粘到下一帧。
// io.ReadFull 是本函数正确性的关键——短读会返回错误而不是静默返回半帧。
func readFrame(r io.Reader) ([]byte, error) {
	var hdr [frameHeadSize]byte
	if _, err := io.ReadFull(r, hdr[:]); err != nil {
		return nil, fmt.Errorf("读帧头: %w", err)
	}
	n := int(binary.BigEndian.Uint16(hdr[:]))
	if n > maxFrameSize { // 长度上限校验：防恶意/损坏采集端申请超大 buffer
		return nil, fmt.Errorf("帧长 %d 超上限 %d", n, maxFrameSize)
	}
	payload := make([]byte, n)
	if _, err := io.ReadFull(r, payload); err != nil {
		return nil, fmt.Errorf("读帧负载: %w", err)
	}
	return payload, nil
}

// concatSamples 辅助断言：批内样本 seq 连续区间（[from,to]）。
func (b Batch) seqRange() (uint64, uint64, error) {
	if len(b.Samples) == 0 {
		return 0, 0, errors.New("空批")
	}
	from, to := b.Samples[0].Seq, b.Samples[0].Seq
	for _, s := range b.Samples[1:] {
		if s.Seq < from {
			from = s.Seq
		}
		if s.Seq > to {
			to = s.Seq
		}
	}
	return from, to, nil
}
