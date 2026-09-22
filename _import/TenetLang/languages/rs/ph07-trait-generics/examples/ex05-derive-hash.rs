// 来源：languages/rs/ph07-trait-generics/07-trait-generics.md 第 6 章示例 5
// 说明：derive 版 DocId（逐字段 PartialEq/Hash）对比自定义版 ShardKey（只按 shard 判定相等与哈希）
// 验证环境：rustc 1.92.0（macOS arm64）
// 编译：rustc ex05-derive-hash.rs -o /tmp/ex05
// 运行：/tmp/ex05
// 验证状态：已验证（编译零警告，输出符合预期）

use std::collections::HashMap;
use std::hash::{Hash, Hasher};

// derive 版：DocId 作为完整 key（所有字段参与比较与哈希）
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct DocId { shard: u32, seq: u64 }

// 自定义版：ShardKey 只按 shard 判定相等与哈希——同一分片的所有键视为同一个 key
#[derive(Debug, Clone)]
struct ShardKey {
    shard: u32,
    #[allow(dead_code)] // 演示用：label 故意不参与比较/哈希
    label: String,
}

impl PartialEq for ShardKey {
    fn eq(&self, other: &Self) -> bool { self.shard == other.shard }
}

impl Eq for ShardKey {}

impl Hash for ShardKey {
    fn hash<H: Hasher>(&self, state: &mut H) { self.shard.hash(state); }
}

fn main() {
    let mut docs: HashMap<DocId, String> = HashMap::new();
    docs.insert(DocId { shard: 1, seq: 42 }, String::from("doc-a"));
    println!("lookup: {:?}", docs.get(&DocId { shard: 1, seq: 42 }));

    // 按分片聚合：label 不同但 shard 相同 → 视为同一个 key，累加
    let mut by_shard: HashMap<ShardKey, u64> = HashMap::new();
    *by_shard.entry(ShardKey { shard: 2, label: String::from("a") }).or_insert(0) += 10;
    *by_shard.entry(ShardKey { shard: 2, label: String::from("b") }).or_insert(0) += 20;
    let total = by_shard.get(&ShardKey { shard: 2, label: String::from("x") }).expect("shard 2 已聚合");
    println!("shard 2 total: {}", total); // 30
}
