// examples/ex01-move-copy-clone.rs —— move、Copy 与 Clone 对比：三种赋值行为
// 验证环境：rustc 1.92.0
// 编译：rustc ex01-move-copy-clone.rs -o ex01
// 运行：./ex01
// 已验证：本环境编译零警告，运行输出 s2/x,y/a,b 三组结果

fn main() {
    // move：String 不实现 Copy，赋值后旧变量失效
    let s1 = String::from("hello");
    let s2 = s1; // ownership 移动到 s2，s1 失效
    // println!("{}", s1); // 编译错误：value moved
    println!("s2 = {}", s2);

    // Copy：i32 按位复制，原变量仍可用
    let x = 7;
    let y = x;
    println!("x = {} still usable, y = {}", x, y);

    // Clone：显式深拷贝，原变量仍可用
    let a = String::from("data");
    let b = a.clone();
    println!("a = {}, b = {}", a, b);
}
