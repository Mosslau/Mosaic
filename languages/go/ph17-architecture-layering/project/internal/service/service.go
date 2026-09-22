// 来源：ph17-architecture-layering project/internal/service
// 一句话说明：业务层。全部管理规则（注册校验/唯一性、心跳上线、版本禁止回退、
// 离线拒收命令）都在这里，不出现 HTTP 词汇；错误统一返回 *errs.Error，
// 存储哨兵（domain.ErrNotFound）在这里被翻译成业务码——handler 只做映射。
// 可测性：now() 可注入（测试固定时钟）；NodeStore 接口在消费方声明（主文档 3.3）。
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
	"sort"
	"strconv"
	"strings"
	"time"

	"tenetlang/go/ph17-architecture-layering/project/internal/domain"
	"tenetlang/go/ph17-architecture-layering/project/internal/errs"
)

// NodeStore 是 Service 对存储的全部需求——接口定义在使用方（本包）。
// 实现方（internal/store 的 Mem/File）不 import 本包，方法签名一致即隐式满足；
// 是否真满足由 cmd/deviceapi 的 var _ 断言在编译期钉死。
type NodeStore interface {
	Get(id string) (domain.Node, error)
	List() ([]domain.Node, error)
	Save(d domain.Node) error
	Delete(id string) error
}

// Service 业务门面：只依赖接口与领域。
type Service struct {
	store NodeStore
	now   func() time.Time // 时钟注入点：测试固定时间，生产默认 time.Now
}

func New(store NodeStore) *Service {
	return &Service{store: store, now: time.Now}
}

// Register 注册节点：id/name 去空白后非空；id 唯一；版本（可选）必须是语义化版本。
// 新节点默认离线，等待首次心跳上线。
func (s *Service) Register(id, name, ver string) (domain.Node, error) {
	id = strings.TrimSpace(id)
	name = strings.TrimSpace(name)
	if id == "" || name == "" {
		return domain.Node{}, errs.Newf(errs.CodeBadRequest, "id 与 name 不能为空")
	}
	if ver != "" {
		if _, ok := parseVersion(ver); !ok {
			return domain.Node{}, errs.Newf(errs.CodeBadRequest, "版本 %q 不是 major.minor.patch 格式", ver)
		}
	}
	if _, err := s.store.Get(id); err == nil {
		return domain.Node{}, errs.Newf(errs.CodeExists, "节点 %s 已存在", id)
	} else if !errors.Is(err, domain.ErrNotFound) {
		return domain.Node{}, errs.Wrap(errs.CodeInternal, "检查节点是否已存在失败", err)
	}
	d := domain.Node{ID: id, Name: name, Status: domain.StatusOffline, Version: ver}
	if err := s.store.Save(d); err != nil {
		return domain.Node{}, errs.Wrap(errs.CodeInternal, "保存节点失败", err)
	}
	return d, nil
}

func (s *Service) Get(id string) (domain.Node, error) {
	d, err := s.store.Get(id)
	if err != nil {
		return domain.Node{}, s.mapStoreErr(err)
	}
	return d, nil
}

// List 按 ID 排序返回（响应顺序稳定）。
func (s *Service) List() ([]domain.Node, error) {
	nodes, err := s.store.List()
	if err != nil {
		return nil, errs.Wrap(errs.CodeInternal, "读取节点列表失败", err)
	}
	sort.Slice(nodes, func(i, j int) bool { return nodes[i].ID < nodes[j].ID })
	return nodes, nil
}

func (s *Service) Delete(id string) error {
	if err := s.store.Delete(id); err != nil {
		return s.mapStoreErr(err)
	}
	return nil
}

// Heartbeat 心跳上报：节点必须存在；状态置为在线并刷新 LastSeen（时钟走 s.now）。
// 真实平台里心跳由采集器批量上报，这里演示 HTTP 管理面的单台上报。
func (s *Service) Heartbeat(id string) (domain.Node, error) {
	d, err := s.store.Get(id)
	if err != nil {
		return domain.Node{}, s.mapStoreErr(err)
	}
	d.Status = domain.StatusOnline
	d.LastSeen = s.now().UTC()
	if err := s.store.Save(d); err != nil {
		return domain.Node{}, errs.Wrap(errs.CodeInternal, "保存心跳失败", err)
	}
	return d, nil
}

// UpgradeVersion 版本升级：必须存在；新版本格式合法；不允许回退（<= 当前版本拒绝）。
// 版本相等视为幂等成功（重复下发同一版本无副作用）。
func (s *Service) UpgradeVersion(id, ver string) (domain.Node, error) {
	v, ok := parseVersion(strings.TrimSpace(ver))
	if !ok {
		return domain.Node{}, errs.Newf(errs.CodeBadRequest, "版本 %q 不是 major.minor.patch 格式", ver)
	}
	d, err := s.store.Get(id)
	if err != nil {
		return domain.Node{}, s.mapStoreErr(err)
	}
	if cur := d.Version; cur != "" {
		curV, ok := parseVersion(cur)
		if !ok {
			// 库里数据异常（正常流程不会发生）：按内部错误处理而不是静默放行
			return domain.Node{}, errs.Wrap(errs.CodeInternal, "节点版本数据异常", errors.New("bad stored version "+cur))
		}
		if versionLess(v, curV) {
			return domain.Node{}, errs.Newf(errs.CodeConflict, "版本不允许回退: %s -> %s", cur, ver)
		}
	}
	d.Version = ver
	if err := s.store.Save(d); err != nil {
		return domain.Node{}, errs.Wrap(errs.CodeInternal, "保存版本失败", err)
	}
	return d, nil
}

// SendCommand 下发指令（管理面受理）：指令非空；节点必须在线，否则拒绝。
// 命令的真实投递链（协议转换/ACK/重试）属 ph21 通用数据采集与接入网关方向 Go 阶段，
// 本阶段只做业务层受理判定——离线节点的命令直接在源头拒掉。
func (s *Service) SendCommand(id, command string) error {
	command = strings.TrimSpace(command)
	if command == "" {
		return errs.Newf(errs.CodeBadRequest, "command 不能为空")
	}
	d, err := s.store.Get(id)
	if err != nil {
		return s.mapStoreErr(err)
	}
	if d.Status != domain.StatusOnline {
		return errs.Newf(errs.CodeOffline, "节点 %s 当前状态 %s，命令无法下发", id, d.Status)
	}
	return nil
}

// mapStoreErr 把存储层错误翻译成业务码：not found → NODE_NOT_FOUND，
// 其它一律 INTERNAL 并保留根因（包装而不是吞掉）。
func (s *Service) mapStoreErr(err error) error {
	if errors.Is(err, domain.ErrNotFound) {
		return errs.New(errs.CodeNotFound, "节点不存在")
	}
	return errs.Wrap(errs.CodeInternal, "存储操作失败", err)
}

// version 语义化版本三元组。
type version struct {
	major, minor, patch int
}

// parseVersion 解析 "major.minor.patch"，非负整数，缺段/带字母/负数都判不合法。
func parseVersion(s string) (version, bool) {
	parts := strings.Split(s, ".")
	if len(parts) != 3 {
		return version{}, false
	}
	v := version{}
	nums := []*int{&v.major, &v.minor, &v.patch}
	for i, part := range parts {
		n, err := strconv.Atoi(part)
		if err != nil || n < 0 {
			return version{}, false
		}
		*nums[i] = n
	}
	return v, true
}

// versionLess 字典序比较三元组。
func versionLess(a, b version) bool {
	if a.major != b.major {
		return a.major < b.major
	}
	if a.minor != b.minor {
		return a.minor < b.minor
	}
	return a.patch < b.patch
}
