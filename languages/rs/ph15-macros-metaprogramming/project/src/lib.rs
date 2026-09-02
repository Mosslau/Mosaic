//! event-hub：ph15 宏与元编程阶段综合项目（库）。
//!
//! 对应 roadmap 推荐项目「事件结构体宏：为多类事件生成统一打印、校验或序列化辅助代码」。
//! 本项目落地的组合是「统一打印 + 统一序列化」：
//!
//! - [`define_events!`]（声明宏）：一次定义多类事件结构体，并为每个结构体生成
//!   `impl Event`（`kind()` 种类标签 + `render()` 统一打印）——宏负责「样板」；
//! - serde derive（`#[derive(Serialize, Deserialize)]` 写在宏展开体里）：
//!   [`HubEvent`] 内部标签枚举，`kind` 字段自动生成——derive 负责「序列化样板」；
//! - thiserror derive：事件 JSON 解析错误建模为 [`HubError`]——derive 负责「错误样板」。
//!
//! 三种元编程（macro_rules! 声明宏 / serde derive / thiserror derive）在同一个 crate
//! 里协作：宏生成「类型 + impl」，derive 在编译器处理宏展开结果后生成「trait impl」。

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// 统一事件 trait：`define_events!` 为每类事件生成的 impl
pub trait Event {
    /// 事件种类标签（如 `"order_placed"`，与 JSON 内部标签 `kind` 一致）
    fn kind(&self) -> &'static str;
    /// 统一打印格式：`[kind] field=value ...`
    fn render(&self) -> String;
}

/// 批量定义事件结构体 + 生成 `impl Event`（kind / render）。
///
/// 用法：
///
/// ```ignore
/// event_hub::define_events! {
///     Login => "login" { user: String, ok: bool },
///     OrderPlaced => "order_placed" { order_id: u64, amount: u32 },
/// }
/// ```
///
/// 每个结构体自动带上 `#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]`
/// 与 `pub` 字段——derive 属性写在宏的展开体里，由编译器在宏展开后处理
/// （见主文档 3.5「derive 宏与宏展开的先后」）。
///
/// 卫生性注意：`impl $crate::Event` 里的 `$crate` 保证宏在**别的 crate** 里使用时
/// trait 路径也解析到本 crate（`#[macro_export]` 导出的宏才能跨 crate 用）。
#[macro_export]
macro_rules! define_events {
    ( $( $name:ident => $kind:literal { $( $field:ident : $fty:ty ),* $(,)? } ),* $(,)? ) => {
        $(
            #[derive(Debug, Clone, PartialEq, ::serde::Serialize, ::serde::Deserialize)]
            pub struct $name {
                $( pub $field: $fty ),*
            }

            impl $crate::Event for $name {
                fn kind(&self) -> &'static str {
                    $kind
                }

                fn render(&self) -> String {
                    // 重复展开：每个字段追加一段 " name=value"（Debug 输出给字符串/数字都加引号或原文）
                    let mut out = format!("[{}]", self.kind());
                    $(
                        out.push_str(&format!(" {}={:?}", stringify!($field), self.$field));
                    )*
                    out
                }
            }
        )*
    };
}

// 项目预置的三类事件：结构体由宏生成，字段 pub，derive 由宏体里的属性提供
define_events! {
    Login => "login" {
        user: String,
        ok: bool,
    },
    OrderPlaced => "order_placed" {
        order_id: u64,
        amount: u32,
    },
    PaymentFailed => "payment_failed" {
        order_id: u64,
        reason: String,
    },
}

/// 统一事件枚举：**内部标签**（`#[serde(tag = "kind")]`）序列化——JSON 里自带
/// `"kind": "login"` 判别字段（由 serde 为每个 variant 自动生成），与 [`Event::kind`]
/// 返回的种类字符串一一对应。
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum HubEvent {
    Login(Login),
    OrderPlaced(OrderPlaced),
    PaymentFailed(PaymentFailed),
}

impl HubEvent {
    /// 把枚举变体分发到对应事件结构体，复用宏生成的统一打印
    pub fn render(&self) -> String {
        match self {
            HubEvent::Login(e) => e.render(),
            HubEvent::OrderPlaced(e) => e.render(),
            HubEvent::PaymentFailed(e) => e.render(),
        }
    }
}

/// 事件总线错误：thiserror derive 生成 Display / Error / source（`#[from]` 生成 From）
#[derive(Debug, Error)]
pub enum HubError {
    #[error("事件 JSON 解析失败: {0}")]
    Json(#[from] serde_json::Error),
    #[error("未知事件种类: {0}")]
    UnknownKind(String),
}
