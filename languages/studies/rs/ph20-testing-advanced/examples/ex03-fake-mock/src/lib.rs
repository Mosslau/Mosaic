//! ex03：fake 与 mock —— 用 trait 把「测试替身」挂在被测对象上。
//!
//! 场景（复用 ph19 的 WAL record 解析器）：把解析出的 record **应用**到一个
//! 「存储」边界。被测对象不是解析器本身，而是 [`replay_to`]——它只依赖
//! [`Store`] trait，不依赖任何具体存储。于是：
//!
//! - **fake（可跑的真实现）**：[`MemoryStore`] 在内存里完整实现 `Store`，
//!   生产可当冒烟实现、测试可当「速跑真实现」——fake 测的是**行为正确性**；
//! - **mock（记录交互的测试替身）**：见 `tests/interactions.rs` 的手写 `MockStore`，
//!   记录每次 `apply` 的参数、可脚本化注入失败——mock 测的是**调用协议**
//!   （调了几次、参数对没对、失败后有没有停）。手动 mock 样板代码不少，
//!   用 `mockall` 的 `#[automock]` 可自动生成同款结构（见主文档 3.4，本示例零第三方依赖）。
//!
//! # 依赖注入的心智
//!
//! `replay_to<S: Store>(store: &mut S, log: &[u8])` 接受「接口」而不是「实现」：
//! 这就是构造期依赖注入 + 面向接口编程的最小形态——换 fake、换 mock、换真实引擎
//! 都只换参数，被测逻辑一行不改。
//!
//! # 使用示例（doctest）
//!
//! ```rust
//! use ex03_fake_mock::{replay_to, MemoryStore, Op, WalWriter};
//!
//! let mut w = WalWriter::new();
//! w.append(1, Op::Put, b"a", b"1");
//! w.append(2, Op::Delete, b"b", b"");
//!
//! let mut store = MemoryStore::new();
//! let n = replay_to(&mut store, w.as_bytes()).expect("合法日志");
//! assert_eq!(n, 2);
//! assert_eq!(store.entries()[0].key, b"a");
//! assert_eq!(store.entries()[1].op, Op::Delete);
//! ```

mod record;
mod store;

pub use record::{
    parse_record, records, Op, Record, WalError, WalWriter, HEADER_LEN, MAGIC, MAX_KEY, MAX_VALUE,
};
pub use store::{replay_to, Entry, MemoryStore, ReplayError, Store, StoreError};
