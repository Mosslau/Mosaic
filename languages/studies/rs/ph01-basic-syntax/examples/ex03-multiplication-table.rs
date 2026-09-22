// examples/ex03-multiplication-table.rs —— 九九乘法表：嵌套 for 循环 + 格式化输出
// 验证环境：rustc 1.92.0
// 编译：rustc ex03-multiplication-table.rs -o ex03
// 运行：./ex03
// 已验证：本环境编译零警告，输出 9 行，首行 1×1=1，末行以 9×9=81 结尾

fn main() {
    for i in 1..=9 {
        for j in 1..=i {
            // {:<2} 乘积左对齐占两位，保证列对齐
            print!("{}×{}={:<2}  ", j, i, i * j);
        }
        println!();
    }
}
