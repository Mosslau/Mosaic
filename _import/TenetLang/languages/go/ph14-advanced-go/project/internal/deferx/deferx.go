// Package deferx 实验：defer 与 panic/recover 的运行时语义——LIFO 顺序、参数
// 求值时机、闭包引用、命名返回值、recover 生效范围、嵌套 panic 覆盖、panic(nil)
// （Go 1.21+ 返回 *runtime.PanicNilError）。每个语义做成可断言的纯函数，
// 供 rtlab 报告与测试复用。结论：defer 是 LIFO 栈、参数即求值、defer 可改命名
// 返回值；recover 只在 defer 内有效；内层 panic 覆盖外层。
package deferx

import "fmt"

// Order 返回 defer 实际执行顺序（命名返回值：defer 的 append 写回返回值本身）。
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

// PanicNil 返回 panic(nil) 后 recover 的 nil 判定与值（Go 1.21+ 非 nil）。
func PanicNil() (isNil bool, r any) {
	defer func() {
		r = recover()
		isNil = r == nil
	}()
	panic(nil)
}

// SafeCall 把可能 panic 的调用包成 error 返回（panic 转 error 的生产模式）。
func SafeCall(f func()) (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("panic recovered: %v", r)
		}
	}()
	f()
	return nil
}

// Report 生成语义实验报告。
func Report() string {
	body, captured := ArgEval()
	isNil, r := PanicNil()
	return fmt.Sprintf(
		"order       : %v\n"+
			"arg-eval    : body=%d captured=%d（参数在 defer 语句处求值）\n"+
			"closure     : %d（闭包引用看最终值）\n"+
			"named-return: %d（return 5 后 defer ×10）\n"+
			"recover     : %v（只在 defer 内生效）\n"+
			"nested      : %v（内层 panic 覆盖外层）\n"+
			"panic(nil)  : nil? %v, %T（Go 1.21+ 起非 nil）\n"+
			"safe-call   : %v",
		Order(),
		body, captured,
		ClosureCapture(),
		NamedReturn(),
		RecoverInDefer(),
		NestedPanic(),
		isNil, r,
		SafeCall(func() { panic("x") }),
	)
}
