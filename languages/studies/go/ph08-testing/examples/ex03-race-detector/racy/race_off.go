//go:build !race

// 来源：ph08-testing 主文档示例 3 —— 并发代码 race 检测（racy 版）
// 一句话说明：编译期探测 -race 是否开启（未加 -race 时 raceEnabled 为 false）。
package racy

const raceEnabled = false
