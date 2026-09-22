// 来源：ph14-advanced-go 示例 5 —— reflect：反射版配置加载器 + unsafe：内存布局与 uintptr 陷阱
// 一句话说明：本示例把 roadmap 练习「写反射版配置加载器」落地为完整代码——用 reflect
// 遍历 struct 字段、按 tag 决定 key、按字段 Kind 做类型转换，从 JSON 或环境变量填充配置；
// 再加 unsafe 实验：Sizeof/Alignof/Offsetof 看结构体内存布局（含 padding），以及
// uintptr 陷阱（uintptr 是整数、GC 不跟踪——-gcflags=all=-d=checkptr=2 能当场抓住）。
// uintptr 演示代码本身是"故意出错"（被 go vet 拦截），隔离在 uintptr_demo.go 的
// -tags=checkptrdemo 构建门后；`go run -tags=checkptrdemo -gcflags=all=-d=checkptr=2 .`
// 预期 fatal error: checkptr: pointer arithmetic...，勿在测试里调用。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...                     # 加载器与 unsafe 断言（不含 checkptr demo）
//	go vet ./...
//	go run .                             # 演示：JSON/ENV 加载 + 内存布局表
//	go run -tags=checkptrdemo .          # uintptr 陷阱：普通构建两个路径都打印 42（错误没暴露）
//	go run -tags=checkptrdemo -gcflags=all=-d=checkptr=2 .   # checkptr 当场拦截（预期 fatal）
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"reflect"
	"strconv"
	"strings"
	"unsafe"
)

// ---- 反射版配置加载器 ----

// Config 目标结构：cfg tag 决定 key；cfg:"-" 表示跳过（如 Tags 只走 JSON 全量解析）。
type Config struct {
	Port      int      `cfg:"port"`
	Host      string   `cfg:"host"`
	Debug     bool     `cfg:"debug"`
	TimeoutMS float64  `cfg:"timeout_ms"`
	Tags      []string `cfg:"-"`
}

// LoadFromJSON 反射填充：把 map[string]any 按 cfg tag 写进 struct 字段。
// json.Unmarshal 自己也是反射实现的——这里手动走一遍反射，看它"怎么走"。
func LoadFromJSON(cfg *Config, data string) error {
	var raw map[string]any
	if err := json.Unmarshal([]byte(data), &raw); err != nil {
		return err
	}
	return fillFromMap(reflect.ValueOf(cfg).Elem(), raw)
}

// LoadFromEnv 反射填充：从环境变量读取（前缀 + tag 大写），覆盖 JSON 未提供的字段。
func LoadFromEnv(cfg *Config, prefix string) error {
	env := map[string]string{}
	for _, kv := range os.Environ() {
		if i := strings.IndexByte(kv, '='); i > 0 && strings.HasPrefix(kv, prefix) {
			// 统一转小写：APP_PORT → port，与 cfg tag 的 key 对齐
			env[strings.ToLower(strings.TrimPrefix(kv[:i], prefix))] = kv[i+1:]
		}
	}
	return fillFromMap(reflect.ValueOf(cfg).Elem(), toAny(env))
}

// fillFromMap 核心：遍历字段、读 tag、按 Kind 类型转换、SetXxx 写入。
// 教学点：reflect.Value.CanSet（只对可寻址的导出字段为 true）、
// Kind 分派（String/Int/Bool/Float64）、Overflow 检查、错误带字段名。
func fillFromMap(rv reflect.Value, raw map[string]any) error {
	rt := rv.Type()
	for i := 0; i < rv.NumField(); i++ {
		fv := rv.Field(i)
		ft := rt.Field(i)
		key := ft.Tag.Get("cfg")
		if key == "" || key == "-" || !fv.CanSet() {
			continue
		}
		v, ok := raw[key]
		if !ok {
			continue
		}
		if err := setByKind(fv, v); err != nil {
			return fmt.Errorf("字段 %s (cfg:%q): %w", ft.Name, key, err)
		}
	}
	return nil
}

// setByKind 按目标字段的 Kind 做转换：JSON 数字进 map 是 float64，
// 环境变量全是 string——两条来源都汇到这一个函数。
func setByKind(fv reflect.Value, v any) error {
	switch fv.Kind() {
	case reflect.String:
		s, ok := v.(string)
		if !ok {
			return fmt.Errorf("需要 string，得到 %T", v)
		}
		fv.SetString(s)
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		var n int64
		switch x := v.(type) {
		case float64:
			// JSON 数字一律是 float64：先查值域再转换（直接 int64(x) 在溢出时是
			// 实现相关的静默行为，OverflowInt 事后查不出来）
			if x > float64(math.MaxInt64) || x < float64(math.MinInt64) {
				return fmt.Errorf("%v 超出 int64 范围", x)
			}
			n = int64(x)
		case string:
			parsed, err := strconv.ParseInt(x, 10, 64)
			if err != nil {
				return err
			}
			n = parsed
		default:
			return fmt.Errorf("需要整数，得到 %T", v)
		}
		if fv.OverflowInt(n) {
			return fmt.Errorf("%d 超出 %s 范围", n, fv.Type())
		}
		fv.SetInt(n)
	case reflect.Bool:
		var b bool
		switch x := v.(type) {
		case bool:
			b = x
		case string:
			parsed, err := strconv.ParseBool(x)
			if err != nil {
				return err
			}
			b = parsed
		default:
			return fmt.Errorf("需要 bool，得到 %T", v)
		}
		fv.SetBool(b)
	case reflect.Float32, reflect.Float64:
		var f float64
		switch x := v.(type) {
		case float64:
			f = x
		case string:
			parsed, err := strconv.ParseFloat(x, 64)
			if err != nil {
				return err
			}
			f = parsed
		default:
			return fmt.Errorf("需要浮点数，得到 %T", v)
		}
		fv.SetFloat(f)
	default:
		return fmt.Errorf("不支持的 Kind %s（%s）", fv.Kind(), fv.Type())
	}
	return nil
}

// toAny 把 map[string]string 转成 map[string]any，复用同一套 setByKind。
func toAny(m map[string]string) map[string]any {
	out := make(map[string]any, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}

// ---- unsafe：内存布局实验 ----

// Point 故意让字段错开对齐：X(int32,4B) → 空 4B → Y(int64,8B) → Z(int32,4B) → 空 4B，
// 结构体大小 24，而不是 4+8+4=16——padding 是 Go 结构体布局的隐形开销。
type Point struct {
	X int32
	Y int64
	Z int32
}

// Mixed 字段顺序对 Sizeof 的影响：A(bool,1B)→空 7B→B(int64,8B)→C(float32,4B)→空 4B→D(string,16B)
// = 40B；若把 A 和 C 排在一起（4B 对齐合并），可省到 32B——字段重排是真实的优化手段。
type Mixed struct {
	A bool
	B int64
	C float32
	D string
}

// runUintptrDemo 默认实现只打印运行方式；-tags=checkptrdemo 构建时由
// uintptr_demo.go 的 init 替换为真实演示（函数值注入，两种构建都能编译通过）。
var runUintptrDemo = func() {
	fmt.Println("  演示代码是故意违规（uintptr 存指针），被 go vet 的 unsafeptr 检查拦截，")
	fmt.Println("  用 build tag 隔离。运行方式：")
	fmt.Println("    go run -tags=checkptrdemo .            # 普通构建：两个路径都打印 42（错误没暴露）")
	fmt.Println("    go run -tags=checkptrdemo -gcflags=all=-d=checkptr=2 .   # checkptr 拦截：预期 fatal error")
}

// layoutTable 打印结构体内存布局：Sizeof / Alignof / 各字段 Offsetof。
func layoutTable() {
	fmt.Printf("  Point: Sizeof=%d Alignof=%d | X@%d Y@%d Z@%d（Y 因对齐后移，中间空 4B）\n",
		unsafe.Sizeof(Point{}), unsafe.Alignof(Point{}),
		unsafe.Offsetof(Point{}.X), unsafe.Offsetof(Point{}.Y), unsafe.Offsetof(Point{}.Z))
	fmt.Printf("  Mixed: Sizeof=%d Alignof=%d | A@%d B@%d C@%d D@%d\n",
		unsafe.Sizeof(Mixed{}), unsafe.Alignof(Mixed{}),
		unsafe.Offsetof(Mixed{}.A), unsafe.Offsetof(Mixed{}.B),
		unsafe.Offsetof(Mixed{}.C), unsafe.Offsetof(Mixed{}.D))
	fmt.Printf("  引用类型描述符大小: string=%d slice=%d map=%d chan=%d func=%d（全是双字/单字头）\n",
		unsafe.Sizeof(""), unsafe.Sizeof([]int{}), unsafe.Sizeof(map[int]int{}),
		unsafe.Sizeof(make(chan int)), unsafe.Sizeof(func() {}))
}

func main() {
	fmt.Println("== 1. 反射配置加载器：JSON 来源 ==")
	var c1 Config
	err := LoadFromJSON(&c1, `{"port":8080,"host":"0.0.0.0","debug":true,"timeout_ms":1.5,"tags":["a"]}`)
	fmt.Printf("  err=%v cfg=%+v（Tags 走 cfg:\"-\" 跳过）\n", err, c1)

	fmt.Println("== 2. 反射配置加载器：环境变量来源 ==")
	os.Setenv("APP_PORT", "9090")
	os.Setenv("APP_HOST", "127.0.0.1")
	os.Setenv("APP_DEBUG", "false")
	var c2 Config
	err = LoadFromEnv(&c2, "APP_")
	fmt.Printf("  err=%v cfg=%+v（string→int/bool/float 的转换都走 setByKind）\n", err, c2)

	fmt.Println("== 3. 类型不匹配：错误路径 ==")
	var c3 Config
	err = LoadFromJSON(&c3, `{"port":"not-a-number"}`)
	fmt.Printf("  err=%v\n", err)

	fmt.Println("== 4. unsafe 内存布局 ==")
	layoutTable()

	fmt.Println("== 5. uintptr 陷阱 ==")
	runUintptrDemo()
}
