// 来源：ph17-architecture-layering examples/ex03-error-code-wrap/api_test.go
// 一句话说明：用测试钉死三件事——① 包装链不丢根因（errors.Is 穿透到存储哨兵）；
// ② 类型化错误可用 errors.As 取回 Code；③ HTTP 层映射输出稳定的 {code,message} 结构。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestRenameNotFoundKeepsRootCause(t *testing.T) {
	ts := newTodos()
	err := ts.rename("missing", "新标题")
	if err == nil {
		t.Fatal("want error")
	}
	var de *Error
	if !errors.As(err, &de) {
		t.Fatalf("want *Error, got %T", err)
	}
	if de.Code != CodeNotFound {
		t.Fatalf("code = %q, want %q", de.Code, CodeNotFound)
	}
	// 包装 ≠ 替换：根因哨兵仍然可被 errors.Is 命中
	if !errors.Is(err, errNoRows) {
		t.Fatal("errors.Is(err, errNoRows) = false, want true")
	}
}

func TestRenameInvalidArgumentNoCause(t *testing.T) {
	ts := newTodos()
	ts.items["a"] = "旧标题"
	err := ts.rename("a", "   ") // 全是空白 → 业务码 INVALID_ARGUMENT
	if err == nil {
		t.Fatal("want error")
	}
	var de *Error
	if !errors.As(err, &de) {
		t.Fatalf("want *Error, got %T", err)
	}
	if de.Code != CodeInvalid {
		t.Fatalf("code = %q, want %q", de.Code, CodeInvalid)
	}
	if errors.Is(err, errNoRows) {
		t.Fatal("无根因的错误不该命中存储层哨兵")
	}
}

// TestRenameHTTPMapping 用真实 mux（含 {id} 通配）走一遍 HTTP 层，
// 验证 PathValue 注入与 404 错误结构输出。
func TestRenameHTTPMapping(t *testing.T) {
	a := &api{todos: newTodos()}
	mux := http.NewServeMux()
	mux.HandleFunc("POST /todos/{id}/rename", a.renameHandler)

	body, _ := json.Marshal(renameRequest{Title: "x"})
	req := httptest.NewRequest(http.MethodPost, "/todos/ghost/rename", bytes.NewReader(body))
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", rec.Code)
	}
	var out errResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("decode body: %v", err)
	}
	if out.Code != CodeNotFound {
		t.Fatalf("body code = %q, want %q", out.Code, CodeNotFound)
	}
	if out.Message == "" {
		t.Fatal("message 不应为空（调用方靠它展示）")
	}
}
