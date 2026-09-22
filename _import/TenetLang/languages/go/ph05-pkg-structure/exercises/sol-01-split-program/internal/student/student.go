// 来源：exercises/README.md 练习 1 —— 拆分单文件程序参考实现
// 一句话说明：从单文件学生管理程序拆出的 internal/student 业务包，显式返回 error。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：cd sol-01-split-program && go run ./cmd/student-mgr demo
// 验证状态：已验证（Go 1.22.2）
package student

import (
	"errors"
	"fmt"
	"strings"
)

// ErrNotFound 哨兵错误：删除不存在的学生时返回，调用方用 errors.Is 判断
var ErrNotFound = errors.New("student: not found")

// Student 学生记录
type Student struct {
	ID   int
	Name string
	Age  int
}

// Manager 学生管理——业务逻辑与 main 分离，可独立复用与测试
type Manager struct {
	students []Student
	nextID   int
}

// NewManager 新建管理器，ID 从 1 开始
func NewManager() *Manager { return &Manager{nextID: 1} }

// Add 新增学生，返回分配的 ID；姓名为空或年龄非法则拒绝（fail fast）
func (m *Manager) Add(name string, age int) (int, error) {
	name = strings.TrimSpace(name)
	if name == "" {
		return 0, fmt.Errorf("student: 姓名不能为空")
	}
	if age < 0 || age > 200 {
		return 0, fmt.Errorf("student: 非法年龄 %d", age)
	}
	id := m.nextID
	m.students = append(m.students, Student{ID: id, Name: name, Age: age})
	m.nextID++
	return id, nil
}

// Delete 按 ID 删除；未找到时包装 ErrNotFound
func (m *Manager) Delete(id int) error {
	for i, s := range m.students {
		if s.ID == id {
			m.students = append(m.students[:i], m.students[i+1:]...)
			return nil
		}
	}
	return fmt.Errorf("student: 删除 #%d: %w", id, ErrNotFound)
}

// List 返回全部学生——副本语义，调用方修改不影响内部
func (m *Manager) List() []Student {
	out := make([]Student, len(m.students))
	copy(out, m.students)
	return out
}
