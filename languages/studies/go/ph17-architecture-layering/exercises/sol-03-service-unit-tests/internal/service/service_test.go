// 来源：ph17-architecture-layering exercises/sol-03-service-unit-tests/internal/service/service_test.go
// 一句话说明：service 层单测参考实现。要点：
// ① 用 stub 替身（外部包 service_test）实现 Store，不碰真实存储与 HTTP；
// ② 表驱动：一个 TestAdd 覆盖"非空/去空白/唯一"多条规则；
// ③ 断言用 errors.Is 判断语义（哨兵），不用字符串比较。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package service_test

import (
	"errors"
	"testing"

	"tenetlang/go/ph17-architecture-layering/exercises/sol-03-service-unit-tests/internal/service"
	"tenetlang/go/ph17-architecture-layering/exercises/sol-03-service-unit-tests/internal/todo"
)

// stubStore 测试替身：map 存数据，可按用例注入 Get/Save 失败。
type stubStore struct {
	m       map[string]todo.Todo
	getErr  error
	saveErr error
	saves   int
}

func (s *stubStore) Get(id string) (todo.Todo, error) {
	if s.getErr != nil {
		return todo.Todo{}, s.getErr
	}
	t, ok := s.m[id]
	if !ok {
		return todo.Todo{}, todo.ErrNotFound
	}
	return t, nil
}

func (s *stubStore) Save(t todo.Todo) error {
	if s.saveErr != nil {
		return s.saveErr
	}
	s.saves++
	s.m[t.ID] = t
	return nil
}

func (s *stubStore) Delete(id string) error {
	delete(s.m, id)
	return nil
}

func (s *stubStore) List() ([]todo.Todo, error) {
	out := make([]todo.Todo, 0, len(s.m))
	for _, t := range s.m {
		out = append(out, t)
	}
	return out, nil
}

// 替身也受编译期约束：Store 接口签名一变，测试立刻编译失败。
var _ service.Store = (*stubStore)(nil)

func newStub(seed ...todo.Todo) *stubStore {
	s := &stubStore{m: make(map[string]todo.Todo)}
	for _, t := range seed {
		s.m[t.ID] = t
	}
	return s
}

func TestAddValidatesInput(t *testing.T) {
	st := newStub()
	svc := service.New(st)

	cases := []struct {
		name  string
		id    string
		title string
	}{
		{name: "空 id", id: "  ", title: "x"},
		{name: "空 title", id: "a", title: ""},
		{name: "全空白 title", id: "a", title: "   "},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := svc.Add(tc.id, tc.title)
			if !errors.Is(err, service.ErrBadRequest) {
				t.Fatalf("err = %v, want ErrBadRequest", err)
			}
			if len(st.m) != 0 {
				t.Fatalf("非法输入不应落库，got %d items", len(st.m))
			}
		})
	}
}

func TestAddRejectsDuplicateID(t *testing.T) {
	st := newStub(todo.Todo{ID: "a", Title: "旧"})
	svc := service.New(st)
	_, err := svc.Add("a", "新标题")
	if !errors.Is(err, service.ErrExists) {
		t.Fatalf("err = %v, want ErrExists", err)
	}
	// 重复添加不能覆盖原记录
	if got := st.m["a"].Title; got != "旧" {
		t.Fatalf("title = %q, want 旧（不允许覆盖）", got)
	}
}

func TestAddTrimsAndSaves(t *testing.T) {
	st := newStub()
	svc := service.New(st)
	got, err := svc.Add("  a  ", "  学习分层  ")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.ID != "a" || got.Title != "学习分层" {
		t.Fatalf("got %+v, want trimmed a/学习分层", got)
	}
	if st.saves != 1 {
		t.Fatalf("saves = %d, want 1", st.saves)
	}
}

func TestToggleNotFound(t *testing.T) {
	svc := service.New(newStub())
	_, err := svc.Toggle("nope")
	if !errors.Is(err, todo.ErrNotFound) {
		t.Fatalf("err = %v, want todo.ErrNotFound", err)
	}
}

func TestToggleFlipsDone(t *testing.T) {
	st := newStub(todo.Todo{ID: "a", Title: "x"})
	svc := service.New(st)
	got, err := svc.Toggle("a")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !got.Done || !st.m["a"].Done {
		t.Fatal("toggle 后 Done 应为 true（返回值与落库都应翻转为完成）")
	}
}

func TestAddPropagatesStoreFailure(t *testing.T) {
	boom := errors.New("db down")
	st := newStub()
	st.getErr = boom
	svc := service.New(st)
	_, err := svc.Add("a", "x")
	if !errors.Is(err, boom) {
		t.Fatalf("err = %v, want wrapped %v（存储层故障必须原样透出，不能吞）", err, boom)
	}
}
