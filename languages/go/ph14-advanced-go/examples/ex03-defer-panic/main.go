// 来源：ph14-advanced-go 示例 3 —— defer 执行顺序与 panic/recover 语义实测
// 一句话说明：defer 不是"最后执行"这么简单——八个可实测的语义：
// ① defer 后进先出（LIFO）；② defer 的参数在 defer 语句处求值（不是函数返回时）；
// ③ defer 匿名闭包引用的变量看最终值（与②相反）；④ return 后、返回前执行 defer，
// defer 能修改命名返回值；⑤ recover 只有在 defer 函数内直接调用才有效；
// ⑥ 嵌套 panic 时内层覆盖外层；⑦ Go 1.21+ 起 panic(nil) 也能被 recover 且返回
// 非 nil 的 *runtime.PanicNilError；⑧ panic 只终止当前 goroutine。
// 全部行为 go1.25.6 实测（输出见 README）。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（仅标准库）
// 运行：
//
//	go test -v ./...
//	go vet ./...
//	go run .
//
// 验证状态：已验证（go1.25.6）
package main

import "fmt"

// deferOrder 演示 LIFO：同一函数内多个 defer 按声明逆序执行。
// 必须用命名返回值：defer 里 append 改的是"返回值变量"本身；若用普通 return，
// 返回的 slice 头在 defer 执行前就拷贝走了（len 固定为 1），defer 的 append 白做。
func deferOrder() (out []string) {
	defer func() { out = append(out, "defer1") }()
	defer func() { out = append(out, "defer2") }()
	defer func() { out = append(out, "defer3") }()
	out = append(out, "body")
	return
}

// deferArgEval 演示参数求值时机：defer 的参数在 defer 语句处就求值，
// 与函数体后续对 n 的修改无关——返回的 deferredN 固定是 1。
func deferArgEval() (bodyN, deferredN int) {
	n := 1
	defer func(v int) { deferredN = v }(n) // 参数在 defer 语句处求值 → 1
	n = 100
	bodyN = n
	return
}

// deferClosure 对照：defer 匿名闭包引用变量，看到的是函数返回时的最终值（100）。
func deferClosure() (captured int) {
	n := 1
	defer func() { captured = n }() // 闭包引用：看最终值 → 100
	n = 100
	return
}

// namedReturn 演示 defer 修改命名返回值：返回值先算好（5），defer 在返回前乘 10 → 50。
func namedReturn() (x int) {
	x = 1
	defer func() { x = x * 10 }()
	return 5
}

// recoverOnlyInDefer：recover 正确用法——在 defer 函数里调用，捕获 panic。
func recoverOnlyInDefer() (r any) {
	defer func() {
		r = recover()
	}()
	panic("boom")
}

// recoverOutside：recover 不在 defer 里调用 = 无效，panic 继续传播（调用方才能捕获）。
func recoverOutside() {
	if r := recover(); r != nil { // 无效：此刻没有 panic 状态可收
		panic(fmt.Sprintf("unreachable: %v", r))
	}
	panic("boom2")
}

// nestedPanic：后执行的 defer panic 覆盖先执行的：recover 拿到 "inner"。
func nestedPanic() (r any) {
	defer func() { r = recover() }()
	defer func() { panic("inner") }() // 后执行，覆盖 outer
	panic("outer")
}

// panicNil：Go 1.21+ 起 panic(nil) 携带 *runtime.PanicNilError，
// recover() 不再返回 nil——「recover 返回 nil = 没发生 panic」的旧经验失效。
func panicNil() (isNil bool, r any) {
	defer func() {
		r = recover()
		isNil = r == nil
	}()
	panic(nil)
}

func main() {
	fmt.Println("== 1. defer LIFO ==")
	fmt.Println("  执行顺序:", deferOrder())

	fmt.Println("== 2. defer 参数求值时机（语句处求值）==")
	bodyN, deferredN := deferArgEval()
	fmt.Printf("  body 中 n=%d，defer 捕获的 n=%d（参数在 defer 语句处已求值）\n", bodyN, deferredN)

	fmt.Println("== 3. defer 闭包引用变量（看最终值）==")
	fmt.Println("  闭包捕获的 n:", deferClosure())

	fmt.Println("== 4. defer 修改命名返回值 ==")
	fmt.Println("  namedReturn:", namedReturn())

	fmt.Println("== 5. recover 只在 defer 中生效 ==")
	fmt.Println("  recoverOnlyInDefer 捕获:", recoverOnlyInDefer())

	fmt.Println("== 6. recover 不在 defer 中 = 无效，panic 继续传播 ==")
	func() {
		defer func() {
			fmt.Println("  调用方 defer 捕获到:", recover())
		}()
		recoverOutside()
	}()

	fmt.Println("== 7. 嵌套 panic：内层覆盖外层 ==")
	fmt.Println("  nestedPanic 捕获:", nestedPanic())

	fmt.Println("== 8. panic(nil)：Go 1.21+ 返回 *runtime.PanicNilError ==")
	isNil, r := panicNil()
	fmt.Printf("  recover()==nil? %v, 值: %#v\n", isNil, r)

	fmt.Println("== 9. panic 只终止当前 goroutine ==")
	done := make(chan struct{})
	go func() {
		defer func() { recover() }() // 子 goroutine 自己的 defer 捕获
		panic("in-goroutine")
	}()
	go func() { done <- struct{}{} }() // 另一个子 goroutine 不受影响
	<-done
	fmt.Println("  主 goroutine 与无关 goroutine 正常继续")
}
