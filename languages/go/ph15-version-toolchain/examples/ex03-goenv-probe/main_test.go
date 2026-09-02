package main

import (
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestDescribeCoversKeyPaths(t *testing.T) {
	// 四条核心路径必须有语义注解（本阶段 3.2 节的必会区分）
	for _, k := range []string{"GOROOT", "GOPATH", "GOMODCACHE", "GOCACHE", "GOTOOLCHAIN"} {
		if describe(k) == "" {
			t.Fatalf("describe(%q) 返回空：关键键缺少语义注解", k)
		}
	}
	if !strings.Contains(describe("GOMODCACHE"), "模块缓存") {
		t.Fatalf("GOMODCACHE 注解应含'模块缓存': %q", describe("GOMODCACHE"))
	}
	if !strings.Contains(describe("GOCACHE"), "构建缓存") {
		t.Fatalf("GOCACHE 注解应含'构建缓存': %q", describe("GOCACHE"))
	}
	if !strings.Contains(describe("GOROOT"), "安装目录") {
		t.Fatalf("GOROOT 注解应含'安装目录': %q", describe("GOROOT"))
	}
}

func TestProbeIntegration(t *testing.T) {
	if _, err := exec.LookPath("go"); err != nil {
		t.Skip("本机没有 go 命令，跳过集成测试")
	}
	env, err := probe()
	if err != nil {
		t.Fatalf("probe() 失败: %v", err)
	}
	for _, k := range keys {
		if _, ok := env[k]; !ok {
			t.Fatalf("probe 结果缺少键 %q", k)
		}
	}
	if env["GOROOT"] == "" || !filepath.IsAbs(env["GOROOT"]) {
		t.Fatalf("GOROOT 应为绝对路径, got %q", env["GOROOT"])
	}
	if env["GOVERSION"] == "" || !strings.HasPrefix(env["GOVERSION"], "go") {
		t.Fatalf("GOVERSION 应以 go 开头, got %q", env["GOVERSION"])
	}
	if env["GOTOOLCHAIN"] == "" {
		t.Fatal("GOTOOLCHAIN 为空（默认应为 auto）")
	}
}
