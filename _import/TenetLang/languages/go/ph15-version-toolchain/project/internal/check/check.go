// Package check 把 go.mod 的版本要求与当前工具链对比，产出三态结论：
// ok（满足）/ warn（go 行满足但 toolchain 行更高，auto 会切换下载）/
// fail（当前工具链低于 go 行硬门槛，构建必失败）。
// 语义与 go 命令实测行为一致（见主文档 3.6 节实测输出）：
//   - go 行是硬门槛：当前低于它时，GOTOOLCHAIN=auto 尝试下载、=local 直接报错；
//   - toolchain 行是"首选"：高于当前时 auto 会下载切换、local 会忽略该行。
package check

import (
	"fmt"

	"tenetlang/go/ph15-version-toolchain/project/internal/gomodfile"
	"tenetlang/go/ph15-version-toolchain/project/internal/vercmp"
)

// Status 是三态结论。
type Status string

const (
	StatusOK   Status = "ok"
	StatusWarn Status = "warn"
	StatusFail Status = "fail"
)

// Report 是单次检查的结构化结果（text/JSON 共用）。
type Report struct {
	ModFile   string `json:"mod_file"`          // go.mod 路径
	Module    string `json:"module"`            // module 行
	GoLine    string `json:"go_line"`           // go 行（空 = 未声明）
	Toolchain string `json:"toolchain"`         // toolchain 行（空 = 未声明）
	Current   string `json:"current"`           // 当前工具链（如 go1.25.6）
	Want      string `json:"want"`              // -want 策略要求（空 = 无）
	Status    Status `json:"status"`            // ok / warn / fail
	Message   string `json:"message"`           // 一句话结论
	Details   string `json:"details,omitempty"` // 补充说明
}

// Run 对单个 go.mod 要求执行检查。want 是额外的策略门槛（可空）。
// current 形如 "go1.25.6"。
func Run(req *gomodfile.Requirement, modFile, current, want string) Report {
	r := Report{
		ModFile: modFile, Module: req.Module, GoLine: req.Go,
		Toolchain: req.Toolchain, Current: current, Want: want,
	}
	cur := current // 保留 go 前缀用于展示
	// 1) 策略门槛（-want）：团队要求的最低工具链
	if want != "" && vercmp.Less(cur, want) {
		r.Status = StatusFail
		r.Message = fmt.Sprintf("当前 %s < 策略要求 %s", cur, want)
		return r
	}
	// 2) go 行硬门槛
	if req.Go != "" && vercmp.Less(cur, req.Go) {
		r.Status = StatusFail
		r.Message = fmt.Sprintf("当前 %s < go 行 %s（硬门槛）", cur, req.Go)
		r.Details = "GOTOOLCHAIN=auto 会尝试下载更新工具链；=local 会直接报错"
		return r
	}
	if req.Go == "" {
		r.Status = StatusOK
		r.Message = "go.mod 未声明 go 行（旧模块），无强制要求"
		return r
	}
	// 3) toolchain 行高于当前 → 告警（auto 会切换，local 会忽略）
	if req.Toolchain != "" && vercmp.Less(cur, req.Toolchain) {
		r.Status = StatusWarn
		r.Message = fmt.Sprintf("go 行满足，但 toolchain 行 %s > 当前 %s", req.Toolchain, cur)
		r.Details = "auto 模式会下载并切换工具链；local 模式忽略 toolchain 行"
		return r
	}
	r.Status = StatusOK
	r.Message = fmt.Sprintf("当前 %s ≥ go.mod 要求（go %s）", cur, req.Go)
	return r
}
