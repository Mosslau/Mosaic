// 来源：ph14-advanced-go 练习 3 参考实现 —— defer / panic-recover 语义实验
// 一句话说明：roadmap 学习内容「defer、panic/recover 原理」的动手版——把六个语义
// 做成可断言的实验函数：LIFO、参数求值时机、闭包引用、命名返回值、recover 只在 defer
// 中生效、嵌套 panic 覆盖、panic(nil)（Go 1.21+ 返回 *runtime.PanicNilError）。
// 测试逐条断言，运行版打印实验报告。全部 go1.25.6 实测。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go vet ./...
//	go run .
//
// 验证状态：已验证（go1.25.6）
// 验证块（go test ./... 实测，2026-09-01）：
//
//	PASS  ok  tenetlang/go/ph14-advanced-go/exercises/sol-03-defer-panic  0.006s
//	go vet ./... 零输出；go test -race ./... 通过
//	go run . 输出节选：
//	  order: [body defer3 defer2 defer1]        ← LIFO
//	  arg: body=100 captured=1                   ← 参数在 defer 语句处求值
//	  closure: 100                               ← 闭包引用看最终值
//	  named: 50                                  ← return 5 后 defer 乘 10
//	  recover-only-in-defer: boom
//	  nested: inner                              ← 内层 panic 覆盖外层
//	  panic(nil): nil? false, type *runtime.PanicNilError
package main

import (
	"fmt"
	"runtime"
)

// Order 返回 defer 实际执行顺序（用命名返回值：defer 的 append 要写回返回值本身）。
func Order() (out []string) {
	defer func() { out = append(out, "defer1") }()
	defer func() { out = append(out, "defer2") }()
	defer func() { out = append(out, "defer3") }()
	out = append(out, "body")
	return
}

// ArgEval 返回 body 中的 n 与 defer 捕获的 n（参数在 defer 语句处求值 → 1）。
func ArgEval() (body, captured int) {
	n := 1
	defer func(v int) { captured = v }(n)
	n = 100
	body = n
	return
}

// ClosureCapture 返回 defer 闭包引用的 n（闭包看最终值 → 100）。
func ClosureCapture() (captured int) {
	n := 1
	defer func() { captured = n }()
	n = 100
	return
}

// NamedReturn 返回被 defer 修改后的命名返回值（5 × 10 = 50）。
func NamedReturn() (x int) {
	x = 1
	defer func() { x *= 10 }()
	return 5
}

// RecoverInDefer 返回 recover 捕获到的 panic 值。
func RecoverInDefer() (r any) {
	defer func() { r = recover() }()
	panic("boom")
}

// NestedPanic 返回 recover 捕获到的值：内层 panic 覆盖外层 → "inner"。
func NestedPanic() (r any) {
	defer func() { r = recover() }()
	defer func() { panic("inner") }()
	panic("outer")
}

// PanicNil 返回 panic(nil) 后 recover 的 nil 判定与值。
func PanicNil() (isNil bool, r any) {
	defer func() {
		r = recover()
		isNil = r == nil
	}()
	panic(nil)
}

// RecoverOutside 故意在非 defer 位置调用 recover：无效，panic 冒泡（调用方捕获）。
func RecoverOutside() {
	if r := recover(); r != nil {
		panic(fmt.Sprintf("unreachable: %v", r))
	}
	panic("boom2")
}

// SafeCall 把可能 panic 的调用包成 error 返回——生产代码把 panic 转 error 的标准模式。
func SafeCall(f func()) (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("panic recovered: %v", r)
		}
	}()
	f()
	return nil
}

func main() {
	fmt.Println("order:", Order())
	body, captured := ArgEval()
	fmt.Printf("arg: body=%d captured=%d\n", body, captured)
	fmt.Println("closure:", ClosureCapture())
	fmt.Println("named:", NamedReturn())
	fmt.Println("recover-only-in-defer:", RecoverInDefer())
	fmt.Println("nested:", NestedPanic())
	isNil, r := PanicNil()
	fmt.Printf("panic(nil): nil? %v, type %T\n", isNil, r)

	// recover 不在 defer 中 → panic 冒泡；SafeCall 模式把它转成 error
	fmt.Println("safe-call:", SafeCall(func() { RecoverOutside() }))
	fmt.Println("safe-call-ok:", SafeCall(func() {}))
	_ = runtime.GOOS // 保留 runtime 导入（版本说明见文件头）
}
