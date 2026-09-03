// 本文件故意编译失败：期望错误码 E0502。示范「整体方法借用的粒度太粗」：
// name_str(&self) 与 hit(&mut self) 都以整个 self 为单位借用 —— 即便前者只读一个字段。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0502]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
struct Stats {
    name: String,
    hits: u64,
}

impl Stats {
    fn hit(&mut self) {
        self.hits += 1;
    }
    fn name_str(&self) -> &str {
        &self.name
    }
}

fn main() {
    let mut s = Stats { name: "demo".into(), hits: 0 };
    let label = s.name_str(); // 持有对 s 的不可变借用（经 &self 方法，借整个 s）
    s.hit(); // E0502：还需要 &mut self，与上面的不可变借用冲突
    println!("{label} {}", s.hits);
}
