// 来源：ph17-architecture-layering exercises/sol-02-store-interface/internal/store/file_test.go
// 一句话说明：文件存储的往返测试——写进文件、重开文件、数据仍在；
// 删除也持久化；删不存在返回领域哨兵。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package store

import (
	"errors"
	"path/filepath"
	"testing"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-02-store-interface/internal/todo"
)

func TestFileStoreRoundTrip(t *testing.T) {
	path := filepath.Join(t.TempDir(), "todos.json")

	f, err := NewFile(path)
	if err != nil {
		t.Fatalf("NewFile: %v", err)
	}
	if err := f.Save(todo.Todo{ID: "a", Title: "写主文档"}); err != nil {
		t.Fatalf("Save a: %v", err)
	}
	if err := f.Save(todo.Todo{ID: "b", Title: "写练习"}); err != nil {
		t.Fatalf("Save b: %v", err)
	}

	// 重新打开同一文件：数据还在（持久化语义）
	f2, err := NewFile(path)
	if err != nil {
		t.Fatalf("reopen: %v", err)
	}
	items, err := f2.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(items) != 2 {
		t.Fatalf("after reopen len = %d, want 2", len(items))
	}

	// 删除同样持久化
	if err := f2.Delete("a"); err != nil {
		t.Fatalf("Delete a: %v", err)
	}
	f3, err := NewFile(path)
	if err != nil {
		t.Fatalf("reopen again: %v", err)
	}
	items, err = f3.List()
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(items) != 1 || items[0].ID != "b" {
		t.Fatalf("after delete len = %d, want only b", len(items))
	}

	// 删不存在 → 领域哨兵
	if err := f3.Delete("zzz"); !errors.Is(err, todo.ErrNotFound) {
		t.Fatalf("Delete missing err = %v, want ErrNotFound", err)
	}
}
