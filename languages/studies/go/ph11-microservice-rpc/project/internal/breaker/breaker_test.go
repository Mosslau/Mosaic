package breaker

import (
	"testing"
	"time"
)

func TestOpensAfterThreshold(t *testing.T) {
	b := New(2, time.Hour)
	if b.State() != "closed" {
		t.Fatalf("初始应为 closed, got %s", b.State())
	}
	b.Failure()
	if b.State() != "closed" {
		t.Fatal("1 次失败未达阈值")
	}
	b.Failure()
	if b.State() != "open" {
		t.Fatalf("达阈值应 open, got %s", b.State())
	}
	if b.Allow() {
		t.Fatal("open 冷却期应拒绝放行")
	}
}

func TestHalfOpenSuccessCloses(t *testing.T) {
	b := New(1, 50*time.Millisecond)
	b.Failure()
	time.Sleep(80 * time.Millisecond) // 过冷却
	if !b.Allow() {
		t.Fatal("冷却后应半开放行探针")
	}
	if b.State() != "half-open" {
		t.Fatalf("应 half-open, got %s", b.State())
	}
	b.Success()
	if b.State() != "closed" {
		t.Fatalf("探针成功应 closed, got %s", b.State())
	}
	if !b.Allow() {
		t.Fatal("closed 应放行")
	}
}

func TestHalfOpenFailureReopens(t *testing.T) {
	b := New(1, 50*time.Millisecond)
	b.Failure()
	time.Sleep(80 * time.Millisecond)
	if !b.Allow() {
		t.Fatal("冷却后应放行")
	}
	b.Failure() // 探针失败
	if b.State() != "open" {
		t.Fatalf("探针失败应 open, got %s", b.State())
	}
	if b.Allow() {
		t.Fatal("重新 open 后应拒绝")
	}
}

func TestSuccessResetsCounter(t *testing.T) {
	b := New(3, time.Hour)
	b.Failure()
	b.Failure()
	b.Success()
	b.Failure()
	if b.State() != "closed" {
		t.Fatalf("中途成功应清零, got %s", b.State())
	}
}
