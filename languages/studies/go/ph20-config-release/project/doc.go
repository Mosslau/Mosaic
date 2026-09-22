// Package project 是 ph20-config-release 阶段综合项目「多环境配置模块」的
// 根包。它本身不承载逻辑，只挂 doc 与端到端验收测试；业务代码在 cmd/ 与
// internal/ 下，依赖方向单向向内：
//
//	cmd/release-server ──▶ internal/{config,version,feature,release}
//	e2e_test.go         ──▶ internal/ 同下
//
// 项目目标（roadmap §20 推荐项目）：让服务在 dev/test/prod 用不同配置、
// 快速定位运行版本、可安全回滚——把配置分层、版本注入、灰度开关、
// 发布预检四件事做成可离线验证的最小工程。
package project
