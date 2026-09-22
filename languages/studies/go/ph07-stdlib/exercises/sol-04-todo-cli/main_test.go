// 来源：exercises/README.md 练习 4 参考实现 —— Todo 存储的表驱动单元测试
// 一句话说明：t.TempDir() 隔离存储文件，覆盖 load/save 往返、markDone 正常与两类越界。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go test -v
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"path/filepath"
	"testing"
)

func TestStoreRoundTrip(t *testing.T) {
	store := NewStore(filepath.Join(t.TempDir(), "todo.json"))

	// 空存储 load 返回空列表而非报错
	todos, err := store.load()
	if err != nil {
		t.Fatalf("空文件 load 报错: %v", err)
	}
	if len(todos) != 0 {
		t.Fatalf("空文件 load 应返回空列表, 实际 %v", todos)
	}

	// save 后 load 能原样读回
	want := []Todo{{Text: "写周报"}, {Text: "学英语", Done: true}}
	if err := store.save(want); err != nil {
		t.Fatalf("save: %v", err)
	}
	got, err := store.load()
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if len(got) != len(want) {
		t.Fatalf("load 条数 = %d, 期望 %d", len(got), len(want))
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("第 %d 条 = %+v, 期望 %+v", i, got[i], want[i])
		}
	}
}

func TestMarkDone(t *testing.T) {
	newStore := func(t *testing.T) *Store {
		t.Helper()
		store := NewStore(filepath.Join(t.TempDir(), "todo.json"))
		if err := store.save([]Todo{{Text: "a"}, {Text: "b"}}); err != nil {
			t.Fatalf("准备数据: %v", err)
		}
		return store
	}

	t.Run("正常标记", func(t *testing.T) {
		store := newStore(t)
		if err := store.markDone(2); err != nil {
			t.Fatalf("markDone(2): %v", err)
		}
		todos, _ := store.load()
		if todos[0].Done || !todos[1].Done {
			t.Errorf("标记结果 = %+v, 期望仅第 2 条完成", todos)
		}
	})

	cases := []struct {
		name string
		n    int
	}{
		{"编号过小", 0},
		{"编号为负", -1},
		{"编号越界", 3},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			store := newStore(t)
			if err := store.markDone(tc.n); err == nil {
				t.Errorf("markDone(%d) 应报错, 实际成功", tc.n)
			}
		})
	}
}
