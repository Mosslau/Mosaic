// 来源：ph18-api-design-compat examples/ex03-pagination-filter/query.go
// 一句话说明：列表查询的纯逻辑（可脱离 HTTP 单测）。它把"分页 + 过滤 + 排序"做成
// 一个纯函数 query(devices, q)，返回该页数据与总命中数——稳定性规则集中在这里：
// ① 过滤先于分页（total 是过滤后的总数）；② 排序白名单（只允许 id/name/status，
// 任意字段排序会让"按 A 字段排"成为新的契约承诺）；③ 同值决胜字段永远追加 id。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run . -addr 127.0.0.1:18103
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"sort"
	"strings"
)

// sortable 字段白名单：默认按 id（列表契约最稳的默认序）。
var sortableFields = map[string]bool{"id": true, "name": true, "status": true}

// Query 一次列表查询的完整入参。
type Query struct {
	Status string // 空 = 不过滤
	Q      string // 名字模糊匹配；空 = 不过滤
	Sort   string // 白名单字段；空 = id
	Offset int
	Limit  int // 0 时使用默认上限
}

// Page 单页结果 + 分页元数据（envelope 的内容来源，主文档 3.5）。
type Page struct {
	Items  []Device `json:"items"`
	Total  int      `json:"total"` // 过滤后的总数（不是本页条数）
	Offset int      `json:"offset"`
	Limit  int      `json:"limit"`
}

// Apply 对全量数据执行过滤 → 排序 → 切片。返回的切片是副本，不共享底层数组。
func Apply(all []Device, q Query) Page {
	filtered := make([]Device, 0, len(all))
	for _, d := range all {
		if q.Status != "" && d.Status != q.Status {
			continue
		}
		if q.Q != "" && !strings.Contains(d.Name, q.Q) {
			continue
		}
		filtered = append(filtered, d)
	}

	field := q.Sort
	if field == "" || !sortableFields[field] {
		field = "id" // 非白名单字段一律回退默认，而不是报错——见 handler 注释
	}
	sort.Slice(filtered, func(i, j int) bool {
		a, b := filtered[i], filtered[j]
		// 只有主排序字段相等时才落到决胜键；否则直接返回主字段比较。
		switch field {
		case "name":
			if a.Name != b.Name {
				return a.Name < b.Name
			}
		case "status":
			if a.Status != b.Status {
				return a.Status < b.Status
			}
		}
		return a.ID < b.ID // 默认序与决胜字段：同值时按 id，翻页才不重不漏
	})

	start := q.Offset
	if start > len(filtered) {
		start = len(filtered)
	}
	end := start + q.Limit
	if end > len(filtered) {
		end = len(filtered)
	}
	items := append([]Device(nil), filtered[start:end]...)
	return Page{Items: items, Total: len(filtered), Offset: start, Limit: q.Limit}
}
