// 可复现构建演示 bin：输出一段固定文本与构建无关的运行时数据
fn main() {
    let sum: u64 = (0..10_000).map(|i| (i * i) % 7919).sum();
    println!("ph24-reprobin sum={sum}");
}
