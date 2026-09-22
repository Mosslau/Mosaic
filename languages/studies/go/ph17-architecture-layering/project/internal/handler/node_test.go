// 来源：ph17-architecture-layering project/internal/handler/node_test.go
// 一句话说明：handler 层集成单测——真实 mux（含 {id} 通配）+ service + 内存存储，
// 覆盖端到端规则（注册/查重/404/离线拒命令/心跳后放行/版本回退 409）与统一错误结构。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package handler

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	"tenetlang/go/ph17-architecture-layering/project/internal/domain"
	"tenetlang/go/ph17-architecture-layering/project/internal/errs"
	"tenetlang/go/ph17-architecture-layering/project/internal/service"
	"tenetlang/go/ph17-architecture-layering/project/internal/store"
)

func newTestHandler() (*Handler, *http.ServeMux) {
	logger := slog.New(slog.NewTextHandler(io.Discard, nil)) // 测试期日志丢弃
	svc := service.New(store.NewMem())
	h := New(svc, logger)
	mux := http.NewServeMux()
	h.Register(mux)
	return h, mux
}

// do 发一个 JSON 请求并返回 recorder。
func do(t *testing.T, mux *http.ServeMux, method, path string, body any) *httptest.ResponseRecorder {
	t.Helper()
	var rd io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			t.Fatalf("marshal body: %v", err)
		}
		rd = bytes.NewReader(b)
	}
	req := httptest.NewRequest(method, path, rd)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func decodeErr(t *testing.T, rec *httptest.ResponseRecorder) errBody {
	t.Helper()
	var out errBody
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("decode error body %q: %v", rec.Body.String(), err)
	}
	return out
}

func register(t *testing.T, mux *http.ServeMux, id, name, ver string) *httptest.ResponseRecorder {
	t.Helper()
	return do(t, mux, http.MethodPost, "/api/nodes", createRequest{ID: id, Name: name, Version: ver})
}

func TestHealthz(t *testing.T) {
	_, mux := newTestHandler()
	rec := do(t, mux, http.MethodGet, "/healthz", nil)
	if rec.Code != http.StatusOK {
		t.Fatalf("healthz status = %d, want 200", rec.Code)
	}
}

func TestCreateAndGetNode(t *testing.T) {
	_, mux := newTestHandler()
	rec := register(t, mux, "dev-1", "节点组 A", "1.2.3")
	if rec.Code != http.StatusCreated {
		t.Fatalf("create status = %d, want 201 (body: %s)", rec.Code, rec.Body.String())
	}
	var d domain.Node
	if err := json.Unmarshal(rec.Body.Bytes(), &d); err != nil {
		t.Fatalf("decode node: %v", err)
	}
	if d.ID != "dev-1" || d.Status != domain.StatusOffline {
		t.Fatalf("created node = %+v, want dev-1/offline（新节点默认离线）", d)
	}

	rec2 := do(t, mux, http.MethodGet, "/api/nodes/dev-1", nil)
	if rec2.Code != http.StatusOK {
		t.Fatalf("get status = %d, want 200", rec2.Code)
	}
}

func TestCreateDuplicateReturnsConflict(t *testing.T) {
	_, mux := newTestHandler()
	if rec := register(t, mux, "dev-1", "节点组 A", ""); rec.Code != http.StatusCreated {
		t.Fatalf("first create status = %d, want 201", rec.Code)
	}
	rec := register(t, mux, "dev-1", "重复", "")
	if rec.Code != http.StatusConflict {
		t.Fatalf("duplicate create status = %d, want 409", rec.Code)
	}
	if out := decodeErr(t, rec); out.Code != errs.CodeExists {
		t.Fatalf("code = %q, want NODE_EXISTS", out.Code)
	}
}

func TestGetUnknownNodeReturnsNotFound(t *testing.T) {
	_, mux := newTestHandler()
	rec := do(t, mux, http.MethodGet, "/api/nodes/ghost", nil)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", rec.Code)
	}
	if out := decodeErr(t, rec); out.Code != errs.CodeNotFound {
		t.Fatalf("code = %q, want NODE_NOT_FOUND", out.Code)
	}
}

func TestCommandFlowOfflineThenHeartbeatThenAccepted(t *testing.T) {
	_, mux := newTestHandler()
	if rec := register(t, mux, "dev-1", "节点组 A", ""); rec.Code != http.StatusCreated {
		t.Fatalf("create status = %d, want 201", rec.Code)
	}

	// 离线：拒收命令（409 NODE_OFFLINE）
	rec := do(t, mux, http.MethodPost, "/api/nodes/dev-1/commands", commandRequest{Command: "restart"})
	if rec.Code != http.StatusConflict {
		t.Fatalf("offline command status = %d, want 409", rec.Code)
	}
	if out := decodeErr(t, rec); out.Code != errs.CodeOffline {
		t.Fatalf("code = %q, want NODE_OFFLINE", out.Code)
	}

	// 心跳上线
	rec = do(t, mux, http.MethodPost, "/api/nodes/dev-1/heartbeat", nil)
	if rec.Code != http.StatusOK {
		t.Fatalf("heartbeat status = %d, want 200", rec.Code)
	}

	// 在线：受理（202 accepted）
	rec = do(t, mux, http.MethodPost, "/api/nodes/dev-1/commands", commandRequest{Command: "restart"})
	if rec.Code != http.StatusAccepted {
		t.Fatalf("online command status = %d, want 202", rec.Code)
	}
}

func TestVersionDowngradeReturnsConflict(t *testing.T) {
	_, mux := newTestHandler()
	if rec := register(t, mux, "dev-1", "节点组 A", "2.0.0"); rec.Code != http.StatusCreated {
		t.Fatalf("create status = %d, want 201", rec.Code)
	}
	rec := do(t, mux, http.MethodPost, "/api/nodes/dev-1/version", versionRequest{Version: "1.0.0"})
	if rec.Code != http.StatusConflict {
		t.Fatalf("downgrade status = %d, want 409 (body: %s)", rec.Code, rec.Body.String())
	}
	if out := decodeErr(t, rec); out.Code != errs.CodeConflict {
		t.Fatalf("code = %q, want CONFLICT", out.Code)
	}
}

func TestDeleteNode(t *testing.T) {
	_, mux := newTestHandler()
	if rec := register(t, mux, "dev-1", "节点组 A", ""); rec.Code != http.StatusCreated {
		t.Fatalf("create status = %d, want 201", rec.Code)
	}
	if rec := do(t, mux, http.MethodDelete, "/api/nodes/dev-1", nil); rec.Code != http.StatusNoContent {
		t.Fatalf("delete status = %d, want 204", rec.Code)
	}
	if rec := do(t, mux, http.MethodGet, "/api/nodes/dev-1", nil); rec.Code != http.StatusNotFound {
		t.Fatalf("get after delete status = %d, want 404", rec.Code)
	}
}
