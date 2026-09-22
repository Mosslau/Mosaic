// 来源：project/ 可替换存储层的 Todo 服务 —— 文件存储实现
// 一句话说明：FileStorage 以单文本文件持久化（每行 key\tvalue），重建时加载，重开进程数据仍在。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：go run . -backend=file -path=/tmp/todo.txt
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"errors"
	"fmt"
	"os"
	"strings"
)

// FileStorage 基于单文本文件的内存镜像存储：文件每行 "key\tvalue"。
// 每次写操作全量落盘——教学简化，数据量大时应增量写（见 README 扩展方向）。
type FileStorage struct {
	path string
	data map[string]string
}

// NewFileStorage 读取 path 指向的存储文件；文件不存在视为空存储
func NewFileStorage(path string) (*FileStorage, error) {
	fs := &FileStorage{path: path, data: make(map[string]string)}
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return fs, nil
	}
	if err != nil {
		return nil, fmt.Errorf("读取存储文件 %s: %w", path, err)
	}
	for _, line := range strings.Split(strings.TrimSpace(string(data)), "\n") {
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, "\t", 2)
		if len(parts) != 2 {
			continue // 跳过损坏行
		}
		fs.data[parts[0]] = parts[1]
	}
	return fs, nil
}

func (fs *FileStorage) Save(key, value string) error {
	fs.data[key] = value
	return fs.flush()
}

func (fs *FileStorage) Load(key string) (string, error) {
	v, ok := fs.data[key]
	if !ok {
		return "", ErrNotFound
	}
	return v, nil
}

// Delete 幂等：key 不存在同样成功
func (fs *FileStorage) Delete(key string) error {
	if _, ok := fs.data[key]; !ok {
		return nil
	}
	delete(fs.data, key)
	return fs.flush()
}

// flush 将全部数据写回文件
func (fs *FileStorage) flush() error {
	var sb strings.Builder
	for k, v := range fs.data {
		sb.WriteString(k)
		sb.WriteByte('\t')
		sb.WriteString(v)
		sb.WriteByte('\n')
	}
	if err := os.WriteFile(fs.path, []byte(sb.String()), 0o644); err != nil {
		return fmt.Errorf("写入存储文件 %s: %w", fs.path, err)
	}
	return nil
}
