// 本文件故意编译失败：期望错误码 E0509（cannot move out of type `Droppable`, which implements the `Drop` trait）。
// 本文件头部另有机器可读标记行：// expect-error: E0509（verify.sh 据此断言）。
// 场景：类型实现了 Drop —— drop 代码需要看到「完整」的值；字段被单独 move 走会让结构残缺。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0509]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
// expect-error: E0509
struct Droppable(Vec<u8>);

impl Drop for Droppable {
    fn drop(&mut self) {
        println!("Droppable dropped, 残余 len = {}", self.0.len());
    }
}

fn main() {
    let d = Droppable(vec![1, 2, 3]);
    let inner = d.0; // E0509：从 Drop 类型里 move 出字段，drop 会读到残缺结构
    println!("inner len = {}", inner.len());
}
