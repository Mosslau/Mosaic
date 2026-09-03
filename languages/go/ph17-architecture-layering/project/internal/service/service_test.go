// 来源：ph17-architecture-layering project/internal/service/service_test.go
// 一句话说明：service 层单测（白盒：同包可注入时钟 s.now）。规则覆盖：
// 注册校验/唯一性/默认离线、心跳上线并刷新时间、固件禁止回退、离线拒收命令、
// not-found 映射、存储故障透出。全部用 stub 替身，不起服务器、不碰真实文件。
// 验证环境：go1.25.6（darwin/arm64），依赖：零第三方（标准库）
// 构建：go build ./...    测试：go test ./...    静态检查：go vet ./...
// 注：go 命令需带仓库统一重定位环境（GOCACHE=/tmp/gocache GOMODCACHE=/tmp/gomodcache
//
//	GOPROXY=https://goproxy.cn,direct GOSUMDB=off），GOCACHE/GOMODCACHE 可指临时目录
//
// 验证状态：已验证（go1.25.6 本机实测：go vet / go build / go test 全绿，gofmt 合规）
package service

import (
	"errors"
	"testing"
	"time"

	"tenetlang/go/ph17-architecture-layering/project/internal/domain"
	"tenetlang/go/ph17-architecture-layering/project/internal/errs"
)

// stubStore 测试替身：map 存数据，可按用例注入故障。
type stubStore struct {
	m       map[string]domain.Device
	getErr  error
	saveErr error
}

func (s *stubStore) Get(id string) (domain.Device, error) {
	if s.getErr != nil {
		return domain.Device{}, s.getErr
	}
	d, ok := s.m[id]
	if !ok {
		return domain.Device{}, domain.ErrNotFound
	}
	return d, nil
}

func (s *stubStore) List() ([]domain.Device, error) {
	out := make([]domain.Device, 0, len(s.m))
	for _, d := range s.m {
		out = append(out, d)
	}
	return out, nil
}

func (s *stubStore) Save(d domain.Device) error {
	if s.saveErr != nil {
		return s.saveErr
	}
	s.m[d.ID] = d
	return nil
}

func (s *stubStore) Delete(id string) error {
	if _, ok := s.m[id]; !ok {
		return domain.ErrNotFound
	}
	delete(s.m, id)
	return nil
}

var _ DeviceStore = (*stubStore)(nil)

func newStub(seed ...domain.Device) *stubStore {
	s := &stubStore{m: make(map[string]domain.Device)}
	for _, d := range seed {
		s.m[d.ID] = d
	}
	return s
}

// fixedClock 构造注入固定时钟的 Service。
func fixedClock(st DeviceStore, at time.Time) *Service {
	s := New(st)
	s.now = func() time.Time { return at }
	return s
}

func codeOf(t *testing.T, err error) errs.Code {
	t.Helper()
	var de *errs.Error
	if !errors.As(err, &de) {
		t.Fatalf("want *errs.Error, got %T: %v", err, err)
	}
	return de.Code
}

func TestRegisterValidatesInput(t *testing.T) {
	svc := New(newStub())
	for name, args := range map[string][2]string{
		"空 id":   {"", "车队 A"},
		"空 name": {"dev-1", "  "},
	} {
		t.Run(name, func(t *testing.T) {
			_, err := svc.Register(args[0], args[1], "")
			if code := codeOf(t, err); code != errs.CodeBadRequest {
				t.Fatalf("code = %q, want BAD_REQUEST", code)
			}
		})
	}
}

func TestRegisterRejectsBadFirmwareFormat(t *testing.T) {
	svc := New(newStub())
	_, err := svc.Register("dev-1", "车队 A", "v2.0")
	if code := codeOf(t, err); code != errs.CodeBadRequest {
		t.Fatalf("code = %q, want BAD_REQUEST（固件必须 major.minor.patch）", code)
	}
}

func TestRegisterDuplicateRejected(t *testing.T) {
	st := newStub(domain.Device{ID: "dev-1", Name: "已有"})
	svc := New(st)
	_, err := svc.Register("dev-1", "新车", "1.0.0")
	if code := codeOf(t, err); code != errs.CodeExists {
		t.Fatalf("code = %q, want DEVICE_EXISTS", code)
	}
	if st.m["dev-1"].Name != "已有" {
		t.Fatal("重复注册不得覆盖原记录")
	}
}

func TestRegisterDefaultsOffline(t *testing.T) {
	st := newStub()
	svc := New(st)
	d, err := svc.Register("dev-1", "车队 A", "1.2.3")
	if err != nil {
		t.Fatalf("register: %v", err)
	}
	if d.Status != domain.StatusOffline {
		t.Fatalf("新设备状态 = %q, want offline（等首次心跳上线）", d.Status)
	}
	if _, ok := st.m["dev-1"]; !ok {
		t.Fatal("注册后应已落库")
	}
}

func TestGetUnknownDeviceMapsNotFound(t *testing.T) {
	svc := New(newStub())
	_, err := svc.Get("ghost")
	if code := codeOf(t, err); code != errs.CodeNotFound {
		t.Fatalf("code = %q, want DEVICE_NOT_FOUND", code)
	}
}

func TestHeartbeatSetsOnlineAndTime(t *testing.T) {
	st := newStub(domain.Device{ID: "dev-1", Name: "车队 A", Status: domain.StatusOffline})
	at := time.Date(2026, 9, 10, 8, 30, 0, 0, time.UTC)
	svc := fixedClock(st, at)

	d, err := svc.Heartbeat("dev-1")
	if err != nil {
		t.Fatalf("heartbeat: %v", err)
	}
	if d.Status != domain.StatusOnline {
		t.Fatalf("status = %q, want online", d.Status)
	}
	if !d.LastSeen.Equal(at) {
		t.Fatalf("lastSeen = %v, want %v（时钟应来自注入的 now）", d.LastSeen, at)
	}
}

func TestUpgradeFirmwareRejectsDowngrade(t *testing.T) {
	st := newStub(domain.Device{ID: "dev-1", Firmware: "2.0.0"})
	svc := New(st)
	_, err := svc.UpgradeFirmware("dev-1", "1.9.9")
	if code := codeOf(t, err); code != errs.CodeConflict {
		t.Fatalf("code = %q, want CONFLICT（禁止回退）", code)
	}
	if st.m["dev-1"].Firmware != "2.0.0" {
		t.Fatal("回退被拒后固件不得被改写")
	}
}

func TestUpgradeFirmwareIdempotentSameVersion(t *testing.T) {
	st := newStub(domain.Device{ID: "dev-1", Firmware: "2.0.0"})
	svc := New(st)
	if _, err := svc.UpgradeFirmware("dev-1", "2.0.0"); err != nil {
		t.Fatalf("同版本重复下发应幂等成功: %v", err)
	}
}

func TestSendCommandRejectsWhenOffline(t *testing.T) {
	st := newStub(domain.Device{ID: "dev-1", Status: domain.StatusOffline})
	svc := New(st)
	err := svc.SendCommand("dev-1", "restart")
	if code := codeOf(t, err); code != errs.CodeOffline {
		t.Fatalf("code = %q, want DEVICE_OFFLINE", code)
	}
}

func TestSendCommandAcceptedWhenOnline(t *testing.T) {
	st := newStub(domain.Device{ID: "dev-1", Status: domain.StatusOnline})
	svc := New(st)
	if err := svc.SendCommand("dev-1", "restart"); err != nil {
		t.Fatalf("在线设备应受理命令: %v", err)
	}
}

func TestStoreFailurePropagates(t *testing.T) {
	boom := errors.New("db down")
	st := newStub()
	st.getErr = boom
	svc := New(st)
	_, err := svc.Register("dev-1", "车队 A", "")
	if !errors.Is(err, boom) {
		t.Fatalf("err = %v, want wrapped %v（存储故障不得被吞）", err, boom)
	}
	if code := codeOf(t, err); code != errs.CodeInternal {
		t.Fatalf("code = %q, want INTERNAL", code)
	}
}
