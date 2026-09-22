// project/lib-skeleton/src/lib.rs —— fetch-core 占位（可选扩展，不含实现）
// 验证环境：rustc/cargo 1.92.0（edition 2021）。未在本环境验证。
// 本骨架只示意「库型 crate 的公开 API 面怎么留」：下载核心与「进度显示 / TLS 后端」
// 解耦——TLS 后端经 feature 注入，进度经 trait 回调，库本身零 println。
#![forbid(unsafe_code)]

/// 下载配置：TLS 后端由调用方按 feature 选择（见 Cargo.toml 的 tls-rustls / tls-native）
pub struct FetchConfig {
    pub url: String,
    pub dest: std::path::PathBuf,
    pub retries: u32,
}

/// 进度回调 trait：库不实现 UI，只上报事件（进度条/日志由调用方落地）
pub trait Progress {
    fn on_bytes(&mut self, downloaded: u64, total: Option<u64>);
}

/// 占位签名：本骨架不含实现，仅示范「feature 相关的类型如何进公开 API 面」
pub fn fetch(_cfg: FetchConfig, _progress: &mut dyn Progress) -> std::io::Result<()> {
    // 实现属于 ph12/ph13 复习练习；本骨架聚焦依赖/特性设计（project/REPORT.md 扩展方向）
    todo!("fetch-core 实现：HTTP 下载 + 重试 + 进度上报")
}
