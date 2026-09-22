// exercises/sol-02-str-slice-convert.rs —— 练习 2 参考解：String / &str / slice 转换
// 验证环境：rustc 1.92.0
// 编译：rustc sol-02-str-slice-convert.rs -o sol02
// 运行：./sol02
// 已验证：本环境编译零警告，输出 first word / owned / view / tail 四组结果

/// 返回第一个空格前的切片（无空格则返回整个串），零分配
fn first_word(s: &str) -> &str {
    match s.find(' ') {
        Some(i) => &s[..i],
        None => s,
    }
}

/// &str -> String：分配堆内存，返回拥有值
fn swap_to_owned(s: &str) -> String {
    s.to_string()
}

/// &String -> &str：零开销视图
fn as_view(s: &String) -> &str {
    s.as_str()
}

/// 去掉首元素的子切片，空切片则返回空切片
fn tail(nums: &[i32]) -> &[i32] {
    if nums.is_empty() {
        nums
    } else {
        &nums[1..]
    }
}

fn main() {
    let sentence = String::from("hello world rust");

    // first_word 返回的 &str 借用 sentence，期间 sentence 不可被 move
    println!("first word: {}", first_word(&sentence));

    let owned: String = swap_to_owned("borrowed");
    let view: &str = as_view(&owned);
    println!("owned: {}, view: {}", owned, view);

    let nums = [1, 2, 3];
    println!("tail: {:?}", tail(&nums));
    println!("tail of empty: {:?}", tail(&[]));
}
