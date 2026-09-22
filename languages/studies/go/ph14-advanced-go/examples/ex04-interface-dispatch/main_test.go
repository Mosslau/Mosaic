package main

import "testing"

func TestDynamicDispatch(t *testing.T) {
	var s Shape
	s = Circle{R: 2}
	if s.Name() != "circle" {
		t.Errorf("dispatch circle: got %s", s.Name())
	}
	if s.Area() < 12.56 || s.Area() > 12.58 {
		t.Errorf("circle area: got %f", s.Area())
	}
	s = Rect{W: 3, H: 4}
	if s.Name() != "rect" || s.Area() != 12 {
		t.Errorf("dispatch rect: %s %f", s.Name(), s.Area())
	}
}

func TestTypeAssertion(t *testing.T) {
	var s Shape = Rect{W: 3, H: 4}
	r, ok := s.(Rect)
	if !ok || r.Area() != 12 {
		t.Errorf("comma-ok assert: ok=%v %v", ok, r)
	}
	c, ok := s.(Circle)
	if ok {
		t.Errorf("Circle assert should fail, got %v", c)
	}
}

func TestTypeSwitch(t *testing.T) {
	if got := classifySwitch(42); got != "int 42" {
		t.Errorf("got %q", got)
	}
	if got := classifySwitch("hi"); got != `string "hi"` {
		t.Errorf("got %q", got)
	}
	if got := classifySwitch(nil); got != "nil" {
		t.Errorf("got %q", got)
	}
}

// classifySwitch 与 main 中 classify 等价，供测试复用。
func classifySwitch(v any) string {
	switch t := v.(type) {
	case int:
		return "int " + itoa(t)
	case string:
		return "string " + quote(t)
	case Rect:
		return "Rect"
	case nil:
		return "nil"
	default:
		return "other"
	}
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var b [20]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		b[i] = '-'
	}
	return string(b[i:])
}

func quote(s string) string { return `"` + s + `"` }

func TestNilTraps(t *testing.T) {
	var s Shape
	if s != nil {
		t.Error("零值接口应为 nil")
	}
	var p *Rect
	s = p
	if s == nil {
		t.Error("持有 nil 指针的接口 != nil（itab 有类型）")
	}
	r, ok := s.(*Rect)
	if !ok || r != nil {
		t.Errorf("断言 *Rect: ok=%v, r==nil=%v", ok, r == nil)
	}
}
