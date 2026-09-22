// 来源：languages/rs/ph07-trait-generics/project/README.md（阶段项目：序列化接口）
// 说明：Encode trait 统一 LogRecord / IndexMeta / VectorRecord 编码，支持 CSV/JSON 两种格式，含单元测试
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc src/main.rs -o /tmp/proj
// 运行：/tmp/proj
// 测试：rustc --test src/main.rs -o /tmp/proj_test && /tmp/proj_test
// 验证状态：已验证（编译零警告，8 个单元测试全部通过）

use std::fmt;

/// 编码格式：由调用方选择，记录类型按格式输出
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Format {
    Csv,
    Json,
}

/// 统一编码契约：所有"可编码落盘"的记录都实现它
trait Encode {
    /// 核心方法：按指定格式编码为单行文本
    fn encode(&self, format: Format) -> String;

    /// 便捷方法：CSV 编码
    fn encode_csv(&self) -> String {
        self.encode(Format::Csv)
    }

    /// 便捷方法：JSON 编码
    fn encode_json(&self) -> String {
        self.encode(Format::Json)
    }

    /// 默认实现：包一层括号，实现者可覆盖
    fn encode_pretty(&self, format: Format) -> String {
        format!("[{}]", self.encode(format))
    }
}

// ---------- 三类记录 ----------

/// 日志记录
#[derive(Debug, Clone)]
struct LogRecord {
    ts: u64,
    level: String,
    message: String,
}

/// 索引元数据
#[derive(Debug, Clone)]
struct IndexMeta {
    name: String,
    index_type: String,
    column_count: u32,
}

/// 向量记录
#[derive(Debug, Clone)]
struct VectorRecord {
    id: u64,
    dims: u32,
    values: Vec<f32>,
}

impl Encode for LogRecord {
    fn encode(&self, format: Format) -> String {
        match format {
            Format::Csv => format!("{},\"{}\",\"{}\"", self.ts, self.level, self.message),
            Format::Json => format!(
                "{{\"ts\":{},\"level\":\"{}\",\"message\":\"{}\"}}",
                self.ts, self.level, self.message
            ),
        }
    }
}

impl Encode for IndexMeta {
    fn encode(&self, format: Format) -> String {
        match format {
            Format::Csv => format!("\"{}\",{},{}", self.name, self.index_type, self.column_count),
            Format::Json => format!(
                "{{\"name\":\"{}\",\"type\":\"{}\",\"columns\":{}}}",
                self.name, self.index_type, self.column_count
            ),
        }
    }
}

impl Encode for VectorRecord {
    fn encode(&self, format: Format) -> String {
        let vals: Vec<String> = self.values.iter().map(|v| format!("{v}")).collect();
        match format {
            Format::Csv => format!("{},{},\"{}\"", self.id, self.dims, vals.join("|")),
            Format::Json => format!(
                "{{\"id\":{},\"dims\":{},\"values\":[{}]}}",
                self.id,
                self.dims,
                vals.join(",")
            ),
        }
    }
}

// ---------- 泛型管线 ----------

/// 批量导出：只依赖 Encode 契约，新增记录类型零改动
fn export_all<T: Encode>(items: &[T], format: Format) -> String {
    items
        .iter()
        .map(|item| item.encode(format))
        .collect::<Vec<_>>()
        .join("\n")
}

/// 批量快照：演示 where 子句组合多约束（可编码 + 可克隆）
fn snapshot<T>(items: &[T]) -> Vec<T>
where
    T: Encode + Clone,
{
    items.to_vec()
}

/// 打印一个可编码值的两种格式（演示 fmt::Display 与 trait 配合）
fn show<T: Encode + fmt::Debug>(item: &T) {
    println!("debug: {:?}", item);
    println!("  csv:  {}", item.encode_csv());
    println!("  json: {}", item.encode_json());
    println!("  pretty(json): {}", item.encode_pretty(Format::Json));
}

fn main() {
    let logs = vec![
        LogRecord { ts: 1700000000, level: String::from("INFO"), message: String::from("boot ok") },
        LogRecord { ts: 1700000001, level: String::from("ERROR"), message: String::from("disk full") },
    ];
    let metas = vec![
        IndexMeta { name: String::from("pk_users"), index_type: String::from("btree"), column_count: 1 },
        IndexMeta { name: String::from("idx_email"), index_type: String::from("hash"), column_count: 1 },
    ];
    let vectors = vec![
        VectorRecord { id: 1, dims: 3, values: vec![0.1, 0.2, 0.3] },
        VectorRecord { id: 2, dims: 2, values: vec![1.0, -1.0] },
    ];

    println!("=== 逐条展示（三种格式） ===");
    show(&logs[0]);

    println!("\n=== 批量导出：CSV ===");
    println!("--- logs ---\n{}", export_all(&logs, Format::Csv));
    println!("--- metas ---\n{}", export_all(&metas, Format::Csv));
    println!("--- vectors ---\n{}", export_all(&vectors, Format::Csv));

    println!("\n=== 批量导出：JSON ===");
    println!("--- logs ---\n{}", export_all(&logs, Format::Json));

    println!("\n=== 快照（克隆后原切片仍可编码） ===");
    let snap = snapshot(&logs);
    println!("snapshot 条数: {}, 首条 csv: {}", snap.len(), snap[0].encode_csv());
}

// ---------- 单元测试 ----------

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_log() -> LogRecord {
        LogRecord { ts: 100, level: String::from("INFO"), message: String::from("hello") }
    }

    fn sample_meta() -> IndexMeta {
        IndexMeta { name: String::from("pk"), index_type: String::from("btree"), column_count: 2 }
    }

    fn sample_vector() -> VectorRecord {
        VectorRecord { id: 7, dims: 2, values: vec![1.5, -2.0] }
    }

    #[test]
    fn log_csv() {
        assert_eq!(sample_log().encode_csv(), "100,\"INFO\",\"hello\"");
    }

    #[test]
    fn log_json() {
        assert_eq!(
            sample_log().encode_json(),
            "{\"ts\":100,\"level\":\"INFO\",\"message\":\"hello\"}"
        );
    }

    #[test]
    fn meta_csv() {
        assert_eq!(sample_meta().encode_csv(), "\"pk\",btree,2");
    }

    #[test]
    fn vector_json() {
        assert_eq!(
            sample_vector().encode_json(),
            "{\"id\":7,\"dims\":2,\"values\":[1.5,-2]}"
        );
    }

    #[test]
    fn pretty_uses_default_impl() {
        assert_eq!(sample_log().encode_pretty(Format::Csv), "[100,\"INFO\",\"hello\"]");
    }

    #[test]
    fn export_all_batches_any_encodable() {
        let logs = vec![sample_log(), sample_log()];
        let out = export_all(&logs, Format::Csv);
        assert_eq!(out.lines().count(), 2);
        assert!(out.starts_with("100,\"INFO\""));
    }

    #[test]
    fn snapshot_clones_encodable_items() {
        let metas = vec![sample_meta(), sample_meta()];
        let snap = snapshot(&metas);
        assert_eq!(snap.len(), 2);
        assert_eq!(snap[0].encode_json(), sample_meta().encode_json());
    }

    #[test]
    fn vector_csv_uses_pipe_separator() {
        assert_eq!(sample_vector().encode_csv(), "7,2,\"1.5|-2\"");
    }
}
