// 来源：languages/rs/ph07-trait-generics/07-trait-generics.md 第 6 章示例 1
// 说明：为 LogRecord / IndexMeta / VectorRecord 实现统一的 Encode trait，泛型函数 dump_all 通吃三种类型
// 验证环境：rustc 1.92.0（macOS arm64）
// 编译：rustc ex01-encode-trait.rs -o /tmp/ex01
// 运行：/tmp/ex01
// 验证状态：已验证（编译零警告，输出符合预期）

// 行为契约：所有"可编码"的类型都实现它
trait Encode {
    fn encode(&self) -> String;
    fn encode_pretty(&self) -> String {      // 默认实现：可被覆盖
        format!("[{}]", self.encode())
    }
}

struct LogRecord { ts: u64, level: String, message: String }
struct IndexMeta { name: String, index_type: String, column_count: u32 }
struct VectorRecord { id: u64, dims: u32, values: Vec<f32> }

impl Encode for LogRecord {
    fn encode(&self) -> String { format!("{} {} {}", self.ts, self.level, self.message) }
}

impl Encode for IndexMeta {
    fn encode(&self) -> String { format!("{} {} {}", self.name, self.index_type, self.column_count) }
}

impl Encode for VectorRecord {
    fn encode(&self) -> String {
        let vals: Vec<String> = self.values.iter().map(|v| format!("{v}")).collect();
        format!("{} {} [{}]", self.id, self.dims, vals.join(","))
    }
}

// 泛型函数：只依赖 Encode 提供的 encode()，不关心具体类型
fn dump_all<T: Encode>(items: &[T]) {
    for item in items { println!("{}", item.encode()); }
}

fn main() {
    let logs = vec![
        LogRecord { ts: 1700000000, level: String::from("INFO"), message: String::from("boot ok") },
        LogRecord { ts: 1700000001, level: String::from("ERROR"), message: String::from("disk full") },
    ];
    let metas = vec![
        IndexMeta { name: String::from("pk_users"), index_type: String::from("btree"), column_count: 1 },
    ];
    let vectors = vec![VectorRecord { id: 1, dims: 3, values: vec![0.1, 0.2, 0.3] }];

    dump_all(&logs);
    println!("pretty: {}", logs[0].encode_pretty()); // 默认实现
    dump_all(&metas);
    dump_all(&vectors);
}
