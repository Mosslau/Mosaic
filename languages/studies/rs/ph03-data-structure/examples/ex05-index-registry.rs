// examples/ex05-index-registry.rs —— 索引注册表（struct + Vec + HashMap 综合）
// 来源：languages/rs/ph03-data-structure/03-data-structure.md 第 6 章「示例 5」
// 验证环境：rustc 1.92.0
// 编译：rustc ex05-index-registry.rs -o /tmp/ex05-index-registry
// 运行：/tmp/ex05-index-registry
// 验证状态：已验证（编译零警告，输出符合预期）

use std::collections::HashMap;

#[derive(Debug, Clone)]
#[allow(dead_code)] // column_count 是元数据，示例中暂未读取
struct Index {
    name: String,
    index_type: String, // "btree" | "hash" | "inverted"
    column_count: u32,
}

struct IndexRegistry {
    indexes: Vec<Index>,
    by_name: HashMap<String, usize>, // name -> Vec 索引
}

impl IndexRegistry {
    fn new() -> Self {
        IndexRegistry {
            indexes: Vec::new(),
            by_name: HashMap::new(),
        }
    }

    fn register(&mut self, index: Index) {
        let pos = self.indexes.len();
        self.by_name.insert(index.name.clone(), pos);
        self.indexes.push(index);
    }

    fn get_by_name(&self, name: &str) -> Option<&Index> {
        self.by_name.get(name).map(|&pos| &self.indexes[pos])
    }

    fn count_by_type(&self) -> HashMap<&str, u32> {
        let mut result = HashMap::new();
        for idx in &self.indexes {
            *result.entry(idx.index_type.as_str()).or_insert(0) += 1;
        }
        result
    }
}

fn main() {
    let mut reg = IndexRegistry::new();
    reg.register(Index { name: String::from("pk_users"), index_type: String::from("btree"), column_count: 1 });
    reg.register(Index { name: String::from("idx_email"), index_type: String::from("hash"), column_count: 1 });
    reg.register(Index { name: String::from("idx_name_age"), index_type: String::from("btree"), column_count: 2 });

    match reg.get_by_name("idx_email") {
        Some(idx) => println!("found: {:?}", idx),
        None => println!("not found"),
    }
    println!("by type: {:?}", reg.count_by_type());
}
