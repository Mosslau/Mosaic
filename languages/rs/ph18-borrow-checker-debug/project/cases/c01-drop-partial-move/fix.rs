// 修复版（与同目录 error.rs 对照）：给 Drop 类型一个「消费式取走内部数据」的 API。
// 用 std::mem::take 把字段内容换成空默认值 —— self 始终保持完整，drop 照常执行（内容已空）。
// 验证：rustc --edition 2021 fix.rs && ./fix（已验证：rustc 1.92.0 / macOS arm64）。
struct Droppable(Vec<u8>);

impl Droppable {
    /// 消费自身，把内部数据转移给调用方。self 仍保持结构完整，Drop 可安全执行。
    fn into_inner(mut self) -> Vec<u8> {
        std::mem::take(&mut self.0) // 留下一个空 Vec，把内容还回去
    }
}

impl Drop for Droppable {
    fn drop(&mut self) {
        println!("Droppable dropped, 残余 len = {}", self.0.len());
    }
}

fn main() {
    let d = Droppable(vec![1, 2, 3]);
    let inner = d.into_inner(); // 消费 d：内容被取走，d 的空壳随后被 drop
    println!("inner len = {}", inner.len()); // 输出会先看到 drop 打印 len = 0
}
