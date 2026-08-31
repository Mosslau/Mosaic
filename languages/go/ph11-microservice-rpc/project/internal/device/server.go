// Package device 设备管理服务：RPC 契约（JSON-RPC wire 格式）、服务端实现与
// 网关侧"弹性客户端"（服务发现 + 负载均衡 + 熔断 + 超时重试的组合，见 client.go）。
package device

import (
	"encoding/json"
	"errors"
	"net"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

// 服务名与 RPC 方法名（注册中心登记与客户端调用的唯一标识）
const (
	ServiceName  = "device.Service"
	MethodReport = "DeviceService.ReportStatus"
	MethodGet    = "DeviceService.GetStatus"
	MethodList   = "DeviceService.ListStatuses"
)

// Status 设备状态（RPC 载荷）
type Status struct {
	DeviceID string
	Speed    float64
	Ts       int64
}

// 参数/返回值
type ReportArgs struct{ Status Status }
type ReportReply struct {
	Ok       bool
	DeviceID string
}
type GetArgs struct{ DeviceID string }
type GetReply struct{ Status *Status }
type ListReply struct{ Statuses []*Status }

// ---- JSON-RPC wire 报文（与 net/rpc/jsonrpc 兼容：params 为数组、响应回显 id）----

type request struct {
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
	ID     *uint64         `json:"id"`
}

type response struct {
	ID     uint64 `json:"id"`
	Result any    `json:"result"`
	Error  any    `json:"error"`
}

// ---- 服务端 ----

// tokenBucket 令牌桶限流（简化版：refill 间隔把桶补满；生产用 golang.org/x/time/rate）
type tokenBucket struct {
	capacity int64
	tokens   atomic.Int64
}

func newTokenBucket(capacity int64, refill time.Duration) *tokenBucket {
	b := &tokenBucket{capacity: capacity}
	b.tokens.Store(capacity)
	go func() {
		ticker := time.NewTicker(refill)
		defer ticker.Stop() // 避免 time.Tick 的 ticker 无法停止（goroutine 泄漏）
		for range ticker.C {
			b.tokens.Store(b.capacity)
		}
	}()
	return b
}

func (b *tokenBucket) allow() bool {
	for {
		t := b.tokens.Load()
		if t <= 0 {
			return false
		}
		if b.tokens.CompareAndSwap(t, t-1) {
			return true
		}
	}
}

// Server 设备管理服务：限流上报 + 最新状态存储 + 查询
type Server struct {
	mu     sync.Mutex
	latest map[string]*Status
	bucket *tokenBucket
	// 观测计数（测试验证负载均衡分摊用）
	reportCount atomic.Int64
}

func NewServer(rate int64, refill time.Duration) *Server {
	return &Server{
		latest: make(map[string]*Status),
		bucket: newTokenBucket(rate, refill),
	}
}

// ServeConn 服务一条客户端连接（JSON-RPC 手工循环，同示例 5）
func (s *Server) ServeConn(conn net.Conn) {
	defer conn.Close()
	dec := json.NewDecoder(conn)
	enc := json.NewEncoder(conn)
	for {
		var req request
		if err := dec.Decode(&req); err != nil {
			return
		}
		var errMsg any
		switch req.Method {
		case MethodReport:
			var params [1]ReportArgs // JSON-RPC params 是数组（net/rpc/jsonrpc 也是数组包单参数）
			if err := json.Unmarshal(req.Params, &params); err != nil {
				return
			}
			args := params[0]
			if !s.bucket.allow() {
				errMsg = "rate limited" // 超限：429 语义（gRPC 对应 ResourceExhausted）
				break
			}
			s.mu.Lock()
			s.latest[args.Status.DeviceID] = &args.Status
			s.mu.Unlock()
			s.reportCount.Add(1)
			if req.ID == nil {
				continue
			}
			_ = enc.Encode(response{ID: *req.ID, Result: ReportReply{Ok: true, DeviceID: args.Status.DeviceID}, Error: nil})
			continue
		case MethodGet:
			var params [1]GetArgs
			if err := json.Unmarshal(req.Params, &params); err != nil {
				return
			}
			args := params[0]
			s.mu.Lock()
			st, ok := s.latest[args.DeviceID]
			s.mu.Unlock()
			if !ok {
				errMsg = "device not found"
				break
			}
			if req.ID == nil {
				continue
			}
			_ = enc.Encode(response{ID: *req.ID, Result: GetReply{Status: st}, Error: nil})
			continue
		case MethodList:
			s.mu.Lock()
			all := make([]*Status, 0, len(s.latest))
			for _, st := range s.latest {
				all = append(all, st)
			}
			s.mu.Unlock()
			sort.Slice(all, func(i, j int) bool { return all[i].DeviceID < all[j].DeviceID })
			if req.ID == nil {
				continue
			}
			_ = enc.Encode(response{ID: *req.ID, Result: ListReply{Statuses: all}, Error: nil})
			continue
		default:
			errMsg = "unknown method: " + req.Method
		}
		if req.ID != nil {
			_ = enc.Encode(response{ID: *req.ID, Result: nil, Error: errMsg})
		}
	}
}

// ReportCount 已处理的上报数（测试观测）
func (s *Server) ReportCount() int64 { return s.reportCount.Load() }

// ErrNotFound 查询不存在的设备
var ErrNotFound = errors.New("device not found")
