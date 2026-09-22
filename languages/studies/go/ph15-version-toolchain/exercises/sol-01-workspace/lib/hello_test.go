package lib

import (
	"strings"
	"testing"
)

func TestHello(t *testing.T) {
	got := Hello("lib")
	if !strings.HasPrefix(got, "Hello, lib!") {
		t.Fatalf("Hello() = %q, want prefix %q", got, "Hello, lib!")
	}
	if !strings.Contains(got, "v0.0.0-workspace") {
		t.Fatalf("Hello() = %q, 应标注 workspace 本地版本", got)
	}
}
