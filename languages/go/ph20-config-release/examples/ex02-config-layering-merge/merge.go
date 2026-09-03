// 来源：ph20-config-release examples/ex02-config-layering-merge/merge.go
// 一句话说明：分层合并的两种语义——"键级覆盖（map 递归合并、标量/数组整替换）"
// 与"env/flag 扁平键只能落到已存在的叶子"。default→file→env→flag 逐层叠加，
// 每层高者胜，来源可追溯（主文档 3.2）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 运行：go run .          验证状态：已验证（go1.25.6 本机实测全绿，gofmt 合规）
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"strings"
)

// 四层的名字（按优先级从低到高）。Trace 里会用到它们标注每键来源。
const (
	SourceDefault = "default" // 代码内嵌默认
	SourceFile    = "file"    // 配置文件（dev/test/prod 各自一份）
	SourceEnv     = "env"     // 环境变量（12-factor III）
	SourceFlag    = "flag"    // 命令行参数（最高优先：调试/单次覆盖）
)

// Trace 记录「每个叶子键最终由哪一层提供」，键是点路径（如 features.dark）。
// 发布排障时"这个值到底从哪来的"就查它。
type Trace map[string]string

// MergeInto 把 src 层递归合并进 dst（高层优先，直接改 dst）。
// 合并规则（三层语义，缺一不可）：
//  1. 两边同名且都是 map[string]any → 递归合并 = 字段级覆盖，只动重叠子键；
//  2. 标量或数组 → src 整体替换 dst（数组没有"逐元素合并"，整替换才可预期）；
//  3. 任一新键 → 置入并记录来源。
//
// trace 在每次真正"落值"的叶子上记录 srcName。
func MergeInto(dst, src map[string]any, srcName string, trace Trace) {
	mergeInto(dst, src, srcName, trace, "")
}

func mergeInto(dst, src map[string]any, srcName string, trace Trace, prefix string) {
	for k, sv := range src {
		path := k
		if prefix != "" {
			path = prefix + "." + k
		}
		// 规则 1：两层同名子 map → 递归字段级合并。
		if dv, ok := dst[k].(map[string]any); ok {
			if srcMap, ok := sv.(map[string]any); ok {
				mergeInto(dv, srcMap, srcName, trace, path)
				continue
			}
		}
		// 规则 2/3：标量、数组、或"本来不是 map 现在给了 map"都做整体替换。
		// src 里是 map 时先 clone 一份（避免外层的 src 被后续层 mutate），
		// clone 过程同时把子叶子的来源记进 trace。
		if srcMap, ok := sv.(map[string]any); ok {
			clone := make(map[string]any, len(srcMap))
			mergeInto(clone, srcMap, srcName, trace, path)
			dst[k] = clone
			continue
		}
		dst[k] = sv
		trace[path] = srcName
	}
}

// ErrUnknownKey 是 ApplyDotted 对"配置树里没有这个键"的拒绝：env/flag 拼写错误
// 必须启动即报错，而不是默默新建一个无人消费的键（防"改了个寂寞"）。
var ErrUnknownKey = errors.New("unknown config key")

// ErrNotReplaceable 表示目标键是复合值（map/数组）——env 是字符串世界，
// 只能替换叶子标量，不允许用字符串把整个对象/数组换掉。
var ErrNotReplaceable = errors.New("key holds composite value")

// ApplyDotted 用 env/flag 的扁平键（features.dark）更新结构化配置树里的叶子。
// raw 是字符串，按"目标叶子当前的类型"做类型感知解析：
//
//	叶子是 bool → ParseBool；是 int → Atoi；是 string → 原样；
//	叶子是 map/数组 → 拒绝（env/flag 不能整替换复合值）。
//
// 这样"文件层给类型、env/flag 层给字符串"的鸿沟被桥接在合并点，而不是各字段各自解析。
func ApplyDotted(root map[string]any, dotted, raw, srcName string, trace Trace) error {
	segs := strings.Split(dotted, ".")
	cur := root
	for _, seg := range segs[:len(segs)-1] {
		next, ok := cur[seg].(map[string]any)
		if !ok {
			return fmt.Errorf("%w: %s（路径在 %q 处中断）", ErrUnknownKey, dotted, seg)
		}
		cur = next
	}
	leaf := segs[len(segs)-1]
	existing, ok := cur[leaf]
	if !ok {
		return fmt.Errorf("%w: %s", ErrUnknownKey, dotted)
	}
	v, err := coerceToType(existing, raw)
	if err != nil {
		return fmt.Errorf("%s=%q: %w", dotted, raw, err)
	}
	cur[leaf] = v
	trace[dotted] = srcName
	return nil
}

// coerceToType 按目标叶子类型解析字符串。existing 不匹配时报错——这比"悄悄存
// 成字符串、消费时才崩"早一个阶段暴露类型不匹配。
func coerceToType(existing any, raw string) (any, error) {
	switch existing.(type) {
	case bool:
		b, err := strconv.ParseBool(raw)
		if err != nil {
			return nil, fmt.Errorf("需要 bool 却得到 %q", raw)
		}
		return b, nil
	case int:
		n, err := strconv.Atoi(raw)
		if err != nil {
			return nil, fmt.Errorf("需要整数却得到 %q", raw)
		}
		return n, nil
	case string:
		return raw, nil
	default:
		return nil, ErrNotReplaceable
	}
}

// decodeJSONTree 解析 JSON 层并把所有数字统一为 int：
// 教学取舍——本示例只讨论整数型配置（port/percent/超时秒数），
// 把 json.Number 归一成 int 让"类型"在整棵树上保持单一表示。
// 配置含小数/浮点的项目应把类型改为 float64 并同步 coerceToType。
func decodeJSONTree(data []byte) (map[string]any, error) {
	dec := json.NewDecoder(strings.NewReader(string(data)))
	dec.UseNumber()
	var raw any
	if err := dec.Decode(&raw); err != nil {
		return nil, fmt.Errorf("decode json: %w", err)
	}
	clean, err := cleanNumbers(raw)
	if err != nil {
		return nil, err
	}
	tree, ok := clean.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("config root 必须是 JSON 对象")
	}
	return tree, nil
}

func cleanNumbers(v any) (any, error) {
	switch t := v.(type) {
	case json.Number:
		n, err := strconv.Atoi(t.String())
		if err != nil {
			return nil, fmt.Errorf("JSON 数字 %q 非整数（本示例仅支持整数型配置）", t.String())
		}
		return n, nil
	case map[string]any:
		for k, val := range t {
			c, err := cleanNumbers(val)
			if err != nil {
				return nil, err
			}
			t[k] = c
		}
		return t, nil
	case []any:
		for i, val := range t {
			c, err := cleanNumbers(val)
			if err != nil {
				return nil, err
			}
			t[i] = c
		}
		return t, nil
	default:
		return v, nil
	}
}

// formatTree 把合并后的树按"排序叶子 + 来源"打印，是排障用的最终视图。
func formatTree(root map[string]any, trace Trace) string {
	var sb strings.Builder
	var walk func(m map[string]any, prefix string)
	walk = func(m map[string]any, prefix string) {
		for k, v := range m {
			path := k
			if prefix != "" {
				path = prefix + "." + k
			}
			if sub, ok := v.(map[string]any); ok {
				walk(sub, path)
				continue
			}
			fmt.Fprintf(&sb, "   %-34s = %-12v ← %s\n", path, v, trace[path])
		}
	}
	walk(root, "")
	return sb.String()
}
