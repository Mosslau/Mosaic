// project/main.rs —— 索引注册表（IndexRegistry）
// 来源：languages/rs/ph03-data-structure/03-data-structure.md 第 6 章「示例 5」+ 第 7 章「阶段项目」
// 验证环境：rustc 1.92.0
// 编译：rustc main.rs -o /tmp/index-registry
// 运行：/tmp/index-registry
// 测试：rustc --test main.rs -o /tmp/index-registry-test && /tmp/index-registry-test
// 验证状态：已验证（编译零警告，测试全部通过）

use std::collections::HashMap;

// 一个索引的元数据：名称、类型、涉及列数
#[derive(Debug, Clone, PartialEq)]
struct Index {
    name: String,
    index_type: String, // "btree" | "hash" | "inverted"
    column_count: u32,
}

// 索引注册表：Vec 保存有序记录，HashMap 建立「name -> 位置」的索引
struct IndexRegistry {
    indexes: Vec<Index>,
    by_name: HashMap<String, usize>,
}

impl IndexRegistry {
    fn new() -> Self {
        IndexRegistry {
            indexes: Vec::new(),
            by_name: HashMap::new(),
        }
    }

    // 新增索引；重名时拒绝并返回 false
    fn register(&mut self, index: Index) -> bool {
        if self.by_name.contains_key(&index.name) {
            return false;
        }
        let pos = self.indexes.len();
        self.by_name.insert(index.name.clone(), pos);
        self.indexes.push(index);
        true
    }

    // 按名称查询：不存在返回 None
    fn get_by_name(&self, name: &str) -> Option<&Index> {
        self.by_name.get(name).map(|&pos| &self.indexes[pos])
    }

    // 按类型统计数量（entry API）
    fn count_by_type(&self) -> HashMap<&str, usize> {
        let mut result = HashMap::new();
        for idx in &self.indexes {
            *result.entry(idx.index_type.as_str()).or_insert(0) += 1;
        }
        result
    }

    // 按类型列出所有索引（扩展能力）
    fn list_by_type(&self, index_type: &str) -> Vec<&Index> {
        self.indexes.iter().filter(|i| i.index_type == index_type).collect()
    }
}

fn main() {
    let mut reg = IndexRegistry::new();

    reg.register(Index { name: String::from("pk_users"), index_type: String::from("btree"), column_count: 1 });
    reg.register(Index { name: String::from("idx_email"), index_type: String::from("hash"), column_count: 1 });
    reg.register(Index { name: String::from("idx_name_age"), index_type: String::from("btree"), column_count: 2 });

    // 重名注册应被拒绝
    let dup = Index { name: String::from("idx_email"), index_type: String::from("hash"), column_count: 1 };
    println!("register duplicate idx_email: {}", reg.register(dup));

    match reg.get_by_name("idx_email") {
        Some(idx) => println!("found: {:?}", idx),
        None => println!("idx_email not found"),
    }
    println!("get_by_name(\"missing\"): {:?}", reg.get_by_name("missing"));

    println!("count by type: {:?}", reg.count_by_type());

    // 按类型列出，并打印每条索引的列数（显式读 column_count）
    for idx in reg.list_by_type("btree") {
        println!("  btree index: {} ({} columns)", idx.name, idx.column_count);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // 构造一个含 3 条索引的注册表，作为测试夹具
    fn sample_registry() -> IndexRegistry {
        let mut reg = IndexRegistry::new();
        reg.register(Index { name: String::from("pk_users"), index_type: String::from("btree"), column_count: 1 });
        reg.register(Index { name: String::from("idx_email"), index_type: String::from("hash"), column_count: 1 });
        reg.register(Index { name: String::from("idx_name_age"), index_type: String::from("btree"), column_count: 2 });
        reg
    }

    #[test]
    fn register_and_lookup() {
        let reg = sample_registry();
        match reg.get_by_name("idx_name_age") {
            Some(idx) => {
                assert_eq!(idx.index_type, "btree");
                assert_eq!(idx.column_count, 2);
            }
            None => panic!("idx_name_age should be registered"),
        }
    }

    #[test]
    fn reject_duplicate_name() {
        let mut reg = sample_registry();
        let dup = Index { name: String::from("idx_email"), index_type: String::from("btree"), column_count: 3 };
        assert!(!reg.register(dup));
        assert_eq!(reg.indexes.len(), 3); // 未新增记录
    }

    #[test]
    fn lookup_missing_returns_none() {
        let reg = sample_registry();
        assert!(reg.get_by_name("missing").is_none());
    }

    #[test]
    fn count_by_type_works() {
        let reg = sample_registry();
        let counts = reg.count_by_type();
        assert_eq!(counts.get("btree"), Some(&2));
        assert_eq!(counts.get("hash"), Some(&1));
    }

    #[test]
    fn list_by_type_works() {
        let reg = sample_registry();
        let btree = reg.list_by_type("btree");
        assert_eq!(btree.len(), 2);
        assert!(btree.iter().all(|i| i.index_type == "btree"));
    }
}
