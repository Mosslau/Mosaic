package deferx

import (
	"reflect"
	"runtime"
	"strings"
	"testing"
)

func TestOrderLIFO(t *testing.T) {
	got := Order()
	want := []string{"body", "defer3", "defer2", "defer1"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("order: got %v want %v", got, want)
	}
}

func TestArgEval(t *testing.T) {
	body, captured := ArgEval()
	if body != 100 {
		t.Errorf("body: %d", body)
	}
	if captured != 1 {
		t.Errorf("defer 参数应在语句处求值: %d", captured)
	}
}

func TestClosureCapture(t *testing.T) {
	if got := ClosureCapture(); got != 100 {
		t.Errorf("closure: %d", got)
	}
}

func TestNamedReturn(t *testing.T) {
	if got := NamedReturn(); got != 50 {
		t.Errorf("named: %d", got)
	}
}

func TestRecoverInDefer(t *testing.T) {
	if got := RecoverInDefer(); got != "boom" {
		t.Errorf("recover: %v", got)
	}
}

func TestNestedPanic(t *testing.T) {
	if got := NestedPanic(); got != "inner" {
		t.Errorf("nested: %v", got)
	}
}

func TestPanicNil(t *testing.T) {
	isNil, r := PanicNil()
	if isNil {
		t.Error("Go 1.21+ panic(nil) 的 recover 不应为 nil")
	}
	if _, ok := r.(*runtime.PanicNilError); !ok {
		t.Errorf("应为 *runtime.PanicNilError: %#v", r)
	}
}

func TestSafeCall(t *testing.T) {
	if err := SafeCall(func() { panic("x") }); err == nil {
		t.Error("panic 应转 error")
	} else if !strings.Contains(err.Error(), "x") {
		t.Errorf("error 应带原值: %v", err)
	}
	if err := SafeCall(func() {}); err != nil {
		t.Errorf("无 panic 应 nil: %v", err)
	}
}
