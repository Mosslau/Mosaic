# lib-skeleton —— fetch-cli 拆成可复用库时的特性设计骨架（可选扩展）

配套 project/REPORT.md 的「扩展方向」：若 fetch-cli 的核心下载逻辑被拆成库（`fetch-core`）供别的工具复用，这份 Cargo.toml 演示库型 crate 的**依赖纪律**——默认特性最小化、可选依赖即 feature、互斥配置用 `dep:` 独占（主文档 3.9 的工程惯例）。

验证环境：rustc/cargo 1.92.0（edition 2021，rust-version 1.85）；依赖 crates.io 拉取（可配 rsproxy）。**未在本环境验证**。

```text
lib-skeleton/
├── Cargo.toml   # 特性设计说明见下
└── src/
    └── lib.rs   # 一句占位：下载核心的公开 API 面（本骨架不含实现）
```
