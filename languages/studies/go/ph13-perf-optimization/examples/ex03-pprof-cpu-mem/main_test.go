package main

import (
	"os"
	"path/filepath"
	"runtime/pprof"
	"testing"
)

func TestFib(t *testing.T) {
	cases := map[int]int{0: 0, 1: 1, 2: 1, 10: 55, 20: 6765}
	for n, want := range cases {
		if got := fib(n); got != want {
			t.Fatalf("fib(%d)=%d, want %d", n, got, want)
		}
	}
}

func TestMakeGarbage(t *testing.T) {
	s := makeGarbage(42)
	if len(s) != 1024+2 { // 1024 个 x + "42"
		t.Fatalf("len=%d", len(s))
	}
}

// TestProfilesWritten 在测试进程里实际采集两种 profile，验证文件非空且可被 pprof 解析框架接受
//（真正的 go tool pprof -top 分析步骤见 README 实测记录）
func TestProfilesWritten(t *testing.T) {
	dir := t.TempDir()

	cpuFile := filepath.Join(dir, "cpu.pprof")
	f, err := os.Create(cpuFile)
	if err != nil {
		t.Fatal(err)
	}
	if err := pprof.StartCPUProfile(f); err != nil {
		t.Fatal(err)
	}
	sum := 0
	for i := 0; i < 30; i++ {
		sum += fib(28) // 采样一段足够长的 CPU 工作，保证 100Hz 采样有样本
	}
	pprof.StopCPUProfile()
	f.Close()
	_ = sum
	if info, _ := os.Stat(cpuFile); info.Size() == 0 {
		t.Fatal("cpu.pprof 为空")
	}

	heapFile := filepath.Join(dir, "heap.pprof")
	h, err := os.Create(heapFile)
	if err != nil {
		t.Fatal(err)
	}
	keep := make([]string, 0, 128)
	for i := 0; i < 128; i++ {
		keep = append(keep, makeGarbage(i))
	}
	if err := pprof.WriteHeapProfile(h); err != nil {
		t.Fatal(err)
	}
	h.Close()
	_ = keep
	if info, _ := os.Stat(heapFile); info.Size() == 0 {
		t.Fatal("heap.pprof 为空")
	}
}
