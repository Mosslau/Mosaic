// 来源：ph18-api-design-compat project/internal/devices/device.go
// 一句话说明：领域模型与按版本裁剪的 DTO（ph17 3.2 承诺在 ph18 的完整兑现）。
// Device 是服务内部唯一真相源，不带 json tag、不属于任何版本；
// deviceV1/deviceV2 是"传输视图"，字段演进（v2 追加 model/lastSeen）只改 DTO
// 与裁剪函数——领域层与版本层互不绑架（主文档 3.3/3.6）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package devices

// Device 领域模型（内部表示；对外字段集合由各版本 DTO 决定）。
type Device struct {
	ID       string
	Name     string
	Online   bool
	Model    string
	LastSeen int64 // unix 秒
}

// DeviceV1 v1 响应视图：2019 年发布时的字段契约。
type DeviceV1 struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Online bool   `json:"online"`
}

// DeviceV2 v2 响应视图：v1 超集 + model/lastSeen（字段只增不删）。
type DeviceV2 struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	Online   bool   `json:"online"`
	Model    string `json:"model"`
	LastSeen int64  `json:"lastSeen"`
}

// toV1 裁剪成 v1 视图。
func toV1(d Device) DeviceV1 { return DeviceV1{ID: d.ID, Name: d.Name, Online: d.Online} }

// toV2 裁剪成 v2 视图。v2 演进时这段函数改，v1 的裁剪函数不碰。
func toV2(d Device) DeviceV2 {
	return DeviceV2{ID: d.ID, Name: d.Name, Online: d.Online, Model: d.Model, LastSeen: d.LastSeen}
}
