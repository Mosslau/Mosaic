// 本文件故意编译失败：期望错误码 E0596（cannot borrow `counter` as mutable, as it is not declared as mutable）。
// 场景：变量绑定默认不可变 —— 想要 &mut 前必须先声明 mut。这是借用错误里最「轻」的一类，
//       它不涉及别名冲突，只涉及可变性缺失，读懂报错里的修复提示即可。
// 验证：rustc --edition 2021 error.rs —— 应报 error[E0596]；对照同目录 fix.rs（已验证：rustc 1.92.0）。
fn main() {
    let counter = 0; // 未声明 mut
    let r = &mut counter; // E0596：不可变绑定不能产出可变借用
    *r += 1;
    println!("{r}");
}
