// Package gomodfile 负责定位并解析 go.mod 的版本相关三行：
// module / go / toolchain。
package gomodfile

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Requirement 是 go.mod 里的版本要求（只关心本工具需要的三行）。
type Requirement struct {
	Module    string // module 行
	Go        string // go 行（如 1.25.0）；空 = 旧模块未声明
	Toolchain string // toolchain 行（如 go1.25.6）；空 = 未声明
}

// FindUp 从 dir 开始向上逐级找 go.mod，返回其绝对路径。
// 找不到返回 *os.PathError。
func FindUp(dir string) (string, error) {
	abs, err := filepath.Abs(dir)
	if err != nil {
		return "", err
	}
	for {
		candidate := filepath.Join(abs, "go.mod")
		if fi, err := os.Stat(candidate); err == nil && !fi.IsDir() {
			return candidate, nil
		}
		parent := filepath.Dir(abs)
		if parent == abs {
			return "", &os.PathError{Op: "find", Path: "go.mod", Err: os.ErrNotExist}
		}
		abs = parent
	}
}

// ParseFile 读取并解析指定 go.mod 文件。
func ParseFile(path string) (*Requirement, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	req, err := Parse(data)
	if err != nil {
		return nil, fmt.Errorf("parse %s: %w", path, err)
	}
	return req, nil
}

// Parse 解析 go.mod 内容（只认 module / go / toolchain 行，其余忽略）。
func Parse(data []byte) (*Requirement, error) {
	req := &Requirement{}
	sc := bufio.NewScanner(strings.NewReader(string(data)))
	lineNo := 0
	for sc.Scan() {
		lineNo++
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "//") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		switch fields[0] {
		case "module":
			req.Module = fields[1]
		case "go":
			req.Go = fields[1]
		case "toolchain":
			req.Toolchain = fields[1]
		}
	}
	if err := sc.Err(); err != nil {
		return nil, fmt.Errorf("scan line %d: %w", lineNo, err)
	}
	return req, nil
}
