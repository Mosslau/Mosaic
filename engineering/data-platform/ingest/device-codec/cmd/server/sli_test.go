package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Mosslau/Mosaic/ingest/device-codec/internal/metrics"
)

// 本文件锁定 codec 侧的上行延迟 SLI(《接入层设计》§9):
//   - codec_ingest_to_decode_seconds: 信封 ingest_ts_ms(EMQX 接收, 毫秒) → 解码完成,**精确**
//   - codec_device_to_decode_seconds: 设备 ts(秒级) → 解码完成,**1 秒分辨率**, 测的是数据陈旧度
// 两条的语义差别是刻意设计的, 不能混用(见 metrics.DeviceToDecode 注释)。

// scrapeCodecMetrics 取一次 codec /metrics 文本。
func scrapeCodecMetrics(t *testing.T) string {
	t.Helper()
	rec := httptest.NewRecorder()
	metrics.Handler().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	return rec.Body.String()
}

// codecCount 取某条 series 的 _count; 不存在返回 0。
func codecCount(t *testing.T, body, series string) float64 {
	t.Helper()
	for _, line := range strings.Split(body, "\n") {
		if strings.HasPrefix(line, series+" ") {
			var v float64
			if _, err := fmt.Sscanf(line, series+" %g", &v); err != nil {
				t.Fatalf("解析指标行失败 %q: %v", line, err)
			}
			return v
		}
	}
	return 0
}

// sliEnvelope 构造信封。ingestTsMS==0 时**不带该字段**, 用于模拟 raw topic 里的存量旧信封。
func sliEnvelope(t *testing.T, frame []byte, ingestTsMS int64) []byte {
	t.Helper()
	m := map[string]any{
		"vin":       frameVIN(t, frame),
		"ts":        time.Now().Unix(),
		"proto_ver": "v1",
		"payload":   base64.StdEncoding.EncodeToString(frame),
	}
	if ingestTsMS != 0 {
		m["ingest_ts_ms"] = ingestTsMS
	}
	raw, err := json.Marshal(m)
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

// TestSLI_IngestToDecodeObserved 信封带 ingest_ts_ms 时, 必须观测到平台段延迟。
func TestSLI_IngestToDecodeObserved(t *testing.T) {
	before := codecCount(t, scrapeCodecMetrics(t), "codec_ingest_to_decode_seconds_count")

	raw := sliEnvelope(t, mustGoldenFrame(t), time.Now().Add(-50*time.Millisecond).UnixMilli())
	if _, dlqs := process(raw); len(dlqs) != 0 {
		t.Fatalf("合法帧不应进 DLQ: %+v", dlqs)
	}

	after := codecCount(t, scrapeCodecMetrics(t), "codec_ingest_to_decode_seconds_count")
	if after <= before {
		t.Errorf("带 ingest_ts_ms 的信封应观测到 ingest_to_decode 样本: before=%v after=%v", before, after)
	}
}

// TestSLI_OldEnvelopeWithoutIngestTs 兼容存量信封: 没有 ingest_ts_ms 字段时**不观测**
// (而不是观测出一个约 56 年的样本污染分位数)。
func TestSLI_OldEnvelopeWithoutIngestTs(t *testing.T) {
	before := codecCount(t, scrapeCodecMetrics(t), "codec_ingest_to_decode_seconds_count")

	raw := sliEnvelope(t, mustGoldenFrame(t), 0)
	if strings.Contains(string(raw), "ingest_ts_ms") {
		t.Fatal("测试构造有误: 旧信封不应含 ingest_ts_ms")
	}
	if _, dlqs := process(raw); len(dlqs) != 0 {
		t.Fatalf("旧信封仍应正常解码: %+v", dlqs)
	}

	after := codecCount(t, scrapeCodecMetrics(t), "codec_ingest_to_decode_seconds_count")
	if after != before {
		t.Errorf("缺 ingest_ts_ms 时不得观测: before=%v after=%v", before, after)
	}
}

// TestSLI_DeviceToDecodeObserved 端到端(粗)指标也要有样本 —— 它是发现
// "数据已陈旧"的信号(设备时钟错/帧在重试里滞留): 黄金帧内时间远早于"现在"。
func TestSLI_DeviceToDecodeObserved(t *testing.T) {
	before := codecCount(t, scrapeCodecMetrics(t), "codec_device_to_decode_seconds_count")

	raw := sliEnvelope(t, mustGoldenFrame(t), time.Now().UnixMilli())
	if _, dlqs := process(raw); len(dlqs) != 0 {
		t.Fatalf("合法帧不应进 DLQ: %+v", dlqs)
	}

	after := codecCount(t, scrapeCodecMetrics(t), "codec_device_to_decode_seconds_count")
	if after <= before {
		t.Errorf("应观测到 device_to_decode 样本: before=%v after=%v", before, after)
	}
}
