// 来源：ph18-api-design-compat exercises/sol-01-device-query-api（练习 1 参考实现）
// 一句话说明：查询纯逻辑 query。设计约束如下（这些行就是 API 的"隐含规范"，练习 3
// 会把它们补进 OpenAPI 文档）：
//
//	分页：offset 从 0 开始；limit 默认 20、最大 100，超出截断；
//	过滤：status 白名单精确匹配，plate 子串模糊匹配；过滤先于分页，total 是过滤后总数；
//	排序：sort 白名单 {id,plate,status}，空或未知值回退 id；同值按 id 决胜。
//
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18201
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"sort"
	"strings"
)

var sortable = map[string]bool{"id": true, "plate": true, "status": true}

// Query 一次查询的全部入参（与 HTTP 参数一一对应，便于纯函数测试）。
type Query struct {
	Status string
	Plate  string
	Sort   string
	Offset int
	Limit  int
}

// Page 分页响应 envelope：items 是本页数据，total 是过滤后的总数。
type Page struct {
	Items  []Device `json:"items"`
	Total  int       `json:"total"`
	Offset int       `json:"offset"`
	Limit  int       `json:"limit"`
}

// Apply 过滤 → 排序 → 切片。返回 Items 是底层数组的副本。
func Apply(fleet []Device, q Query) Page {
	filtered := make([]Device, 0, len(fleet))
	for _, v := range fleet {
		if q.Status != "" && v.Status != q.Status {
			continue
		}
		if q.Plate != "" && !strings.Contains(v.Plate, q.Plate) {
			continue
		}
		filtered = append(filtered, v)
	}

	field := q.Sort
	if !sortable[field] {
		field = "id"
	}
	sort.Slice(filtered, func(i, j int) bool {
		a, b := filtered[i], filtered[j]
		switch field {
		case "plate":
			if a.Plate != b.Plate {
				return a.Plate < b.Plate
			}
		case "status":
			if a.Status != b.Status {
				return a.Status < b.Status
			}
		}
		return a.ID < b.ID // 默认序与决胜键
	})

	start := q.Offset
	if start > len(filtered) {
		start = len(filtered)
	}
	end := start + q.Limit
	if end > len(filtered) {
		end = len(filtered)
	}
	return Page{
		Items:  append([]Device(nil), filtered[start:end]...),
		Total:  len(filtered),
		Offset: start,
		Limit:  q.Limit,
	}
}
