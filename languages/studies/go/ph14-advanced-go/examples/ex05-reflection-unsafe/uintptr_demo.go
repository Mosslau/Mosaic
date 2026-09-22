//go:build checkptrdemo

// uintptr 陷阱演示（故意出错示例）——本文件仅在 -tags=checkptrdemo 时参与构建。
// 目的：实测「uintptr 是整数、GC 不跟踪」的危险写法——普通构建能跑出 42（错误没暴露），
// 加 -gcflags=all=-d=checkptr=2 后 readViaUintptr 当场 fatal error:
// checkptr: pointer arithmetic result points to invalid allocation。
// 为何隔离：`uintptr(unsafe.Pointer(p))` 是 go vet 的 unsafeptr 检查明令禁止的用法，
// 本文件是教学性故意违规（L1 教学性覆盖），用 build tag 隔离，保证默认构建/vet 全绿。
package main

import "unsafe"

func init() {
	runUintptrDemo = uintptrDemo // 替换 main.go 里的占位实现
}

// Item 演示对象。
type Item struct{ ID int }

// readViaPointer 正确做法：unsafe.Pointer 参与 GC 跟踪，对象不会被中途回收。
func readViaPointer(p unsafe.Pointer) int { return (*Item)(p).ID }

// readViaUintptr 错误做法：uintptr 是整数，GC 不跟踪它指向的对象——
// 对象可能已被回收/移动，uintptr 里的地址就悬空了（checkptr 能抓住这种转换）。
func readViaUintptr(u uintptr) int { return (*Item)(unsafe.Pointer(u)).ID }

// uintptrDemo 运行两个读取路径。
func uintptrDemo() {
	it := &Item{ID: 42}
	println("  via unsafe.Pointer:", readViaPointer(unsafe.Pointer(it)))
	u := uintptr(unsafe.Pointer(it))
	println("  via uintptr:", readViaUintptr(u))
}
