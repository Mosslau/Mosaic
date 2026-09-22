package handler

import (
	"fmt"
	"net/http"
	"testing"
	"time"
)

// topic 契约的统一判据测试(2026-09-20 收敛)。
//
// 背景: 修复前 JSON 通道(mqtt_ingest.go 的 ④)与二进制通道(bin_ingest.go 的 ③)各写了一套
// topic 解析 —— 前者 strings.Split 后自行判 3 段、对 VIN 长度**无约束**; 后者要求 >=5。
// 同一份 topic 契约两套判据; 更糟的是 JSON 通道在 topic 形态意外时 topicV 为空会
// **静默跳过** VIN 一致性校验(等于给越权留了一条不报错的路)。
// 现在两条通道共用 topicVIN/splitTopic, 判据与契约同源(vehicle.VINMinLen)。

func TestMQTTIngest_TopicVINTooShort(t *testing.T) {
	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	// 载荷不带 vin, 只能从 topic 回填 —— 而 topic 的 VIN 只有 4 字符(< VINMinLen=5)
	payload := fmt.Sprintf(`{"ts":%d,"type":"vehicle_status","data":{"soc":66}}`, time.Now().Unix())
	w := mqttPost(t, h, testWebhookToken, emqxEnvelope("dev-OV77", "ov/OV77/status", payload))

	if w.Code != http.StatusBadRequest {
		t.Fatalf("过短 VIN 的 topic 应 400, 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs.messages) != 0 {
		t.Error("非法 topic 不得投递 Kafka")
	}
}

func TestMQTTIngest_UnknownTopicSuffix(t *testing.T) {
	fs := &fakeSender{}
	h := NewMQTTIngestHandler(fs, testWebhookToken)

	payload := fmt.Sprintf(`{"ts":%d,"type":"vehicle_status","data":{"soc":66}}`, time.Now().Unix())
	w := mqttPost(t, h, testWebhookToken, emqxEnvelope("dev-OV00000001", "ov/OV00000001/status2", payload))

	if w.Code != http.StatusBadRequest {
		t.Fatalf("未知 topic 后缀应 400, 实际 %d, body=%s", w.Code, w.Body)
	}
	if len(fs.messages) != 0 {
		t.Error("未知后缀不得投递 Kafka")
	}
}

// TestMQTTIngest_MalformedTopicNeverSkipsVINCheck 是本组最重要的一条回归。
//
// 修复前: topic 形态意外(段数不是 3) → topicV 为空 → `if topicV != "" && report.VIN != topicV`
// 整条校验被**静默跳过**, 载荷里的任意 VIN 都会被采信并写入 Kafka。
// 现在: 形态非法一律 400, 绝不存在"没有身份锚点"的分支。
func TestMQTTIngest_MalformedTopicNeverSkipsVINCheck(t *testing.T) {
	for _, topic := range []string{
		"ov/OV00000001",              // 段数不足
		"ov/OV00000001/status/extra", // 段数过多
		"OV00000001/status",          // 缺 ov 前缀
		"ov//status",                 // VIN 为空
		"ov/OV00000001/",             // 后缀为空
		"",                           // 空 topic
	} {
		fs := &fakeSender{}
		h := NewMQTTIngestHandler(fs, testWebhookToken)
		// 载荷声明的 VIN 与任何 topic 都无关 —— 修复前这条会被采信
		payload := fmt.Sprintf(`{"vin":"OV00000001","ts":%d,"type":"vehicle_status","data":{"soc":66}}`, time.Now().Unix())
		w := mqttPost(t, h, testWebhookToken, emqxEnvelope("dev-x", topic, payload))

		if w.Code != http.StatusBadRequest {
			t.Errorf("topic %q 形态非法应 400(不得放行载荷 VIN), 实际 %d", topic, w.Code)
		}
		if len(fs.messages) != 0 {
			t.Errorf("topic %q 非法时不得投递 Kafka", topic)
		}
	}
}

// TestTopicVIN_SameRuleForBothChannels 两条通道对同一 VIN 长度给出**相同**判定
// (修复前 bin 用 4、JSON 用 5, 4 字符 VIN 在一个通道被拒、在另一个通道放行)。
func TestTopicVIN_SameRuleForBothChannels(t *testing.T) {
	cases := []struct {
		vin  string
		want bool
	}{
		{"OV77", false},      // 4 字符: 修复前 bin 通道放行、JSON 通道拒绝
		{"OV777", true},      // 5 字符: 契约下界
		{"OV00000001", true}, // 常规
		{"", false},          // 空
	}
	for _, c := range cases {
		_, okBin := topicVIN("ov/"+c.vin+"/bin", "bin", topicVINMinLen("bin"))
		_, okJSON := topicVIN("ov/"+c.vin+"/status", "status", topicVINMinLen("status"))
		if okBin != c.want || okJSON != c.want {
			t.Errorf("VIN %q: bin=%v json=%v, 期望两者一致且为 %v", c.vin, okBin, okJSON, c.want)
		}
	}
}
