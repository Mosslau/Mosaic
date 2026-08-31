//go:build race

// 来源：ph08-testing 主文档示例 3 —— 并发代码 race 检测（racy 版）
// 一句话说明：编译期探测 -race 是否开启（race 构建标签由 -race 自动注入）。
package racy

const raceEnabled = true
