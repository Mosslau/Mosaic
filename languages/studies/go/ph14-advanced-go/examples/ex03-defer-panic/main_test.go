package main

import (
	"reflect"
	"runtime"
	"testing"
)

func TestDeferOrderLIFO(t *testing.T) {
	got := deferOrder()
	want := []string{"body", "defer3", "defer2", "defer1"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("defer LIFO: got %v, want %v", got, want)
	}
}

func TestDeferArgEval(t *testing.T) {
	bodyN, deferredN := deferArgEval()
	if bodyN != 100 {
		t.Errorf("bodyN: got %d, want 100", bodyN)
	}
	if deferredN != 1 {
		t.Errorf("deferredN（参数在 defer 语句处求值）: got %d, want 1", deferredN)
	}
}

func TestDeferClosure(t *testing.T) {
	if got := deferClosure(); got != 100 {
		t.Errorf("闭包引用看最终值: got %d, want 100", got)
	}
}

func TestNamedReturn(t *testing.T) {
	if got := namedReturn(); got != 50 {
		t.Errorf("defer 修改命名返回值: got %d, want 50", got)
	}
}

func TestRecoverOnlyInDefer(t *testing.T) {
	if got := recoverOnlyInDefer(); got != "boom" {
		t.Errorf("recover 捕获: got %v, want boom", got)
	}
}

// TestRecoverOutside：recover 不在 defer 里调用 = 无效，panic 冒泡给调用方。
func TestRecoverOutside(t *testing.T) {
	got := func() (r any) {
		defer func() { r = recover() }()
		recoverOutside() // 内部 recover 无效，panic 传播到这里被外层 defer 捕获
		return nil
	}()
	if got != "boom2" {
		t.Errorf("recover 不在 defer 中应无效: got %v, want boom2", got)
	}
}

func TestNestedPanic(t *testing.T) {
	if got := nestedPanic(); got != "inner" {
		t.Errorf("嵌套 panic 内层覆盖外层: got %v, want inner", got)
	}
}

func TestPanicNil(t *testing.T) {
	isNil, r := panicNil()
	if isNil {
		t.Error("panic(nil) 在 Go 1.21+ 起 recover 不应返回 nil")
	}
	if _, ok := r.(*runtime.PanicNilError); !ok {
		t.Errorf("panic(nil) 应恢复为 *runtime.PanicNilError，got %#v", r)
	}
}

// TestPanicOnlyKillsGoroutine：panic 只终止当前 goroutine，其他 goroutine 正常。
func TestPanicOnlyKillsGoroutine(t *testing.T) {
	done := make(chan struct{})
	go func() {
		defer func() { recover() }()
		panic("boom")
	}()
	go func() { done <- struct{}{} }()
	<-done // 若 panic 波及整个进程，这里会超时/崩溃——实测正常返回
}
