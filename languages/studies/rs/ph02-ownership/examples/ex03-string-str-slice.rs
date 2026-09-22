// examples/ex03-string-str-slice.rs —— String、&str 与 slice 的转换与使用
// 验证环境：rustc 1.92.0
// 编译：rustc ex03-string-str-slice.rs -o ex03
// 运行：./ex03
// 已验证：本环境编译零警告，运行输出 word/sum/slice 三组结果

/// 取出第 idx 个单词，返回 &str 切片（不拥有数据）
fn pick_word(text: &str, idx: usize) -> Option<&str> {
    text.split_whitespace().nth(idx)
}

/// 对 nums[start..end] 求和，越界返回 0
fn sum_range(nums: &[i32], start: usize, end: usize) -> i32 {
    if start > end || end > nums.len() {
        return 0;
    }
    nums[start..end].iter().sum()
}

fn main() {
    let sentence = String::from("rust ownership is powerful");

    // &String 自动解引用为 &str；pick_word 返回的 &str 借用 sentence
    let word = pick_word(&sentence, 1).unwrap_or("?");
    println!("second word: {}", word);

    // 数组与 Vec 都可转成 &[i32] 切片
    let numbers = [10, 20, 30, 40, 50];
    println!("sum[1..4] = {}", sum_range(&numbers, 1, 4));

    // String 可以按字节范围切出 &str（必须落在 UTF-8 字符边界上）
    let slice: &str = &sentence[5..14];
    println!("slice: {}", slice);

    // 显式转换：&str -> String 需要分配，String -> &str 零开销
    let lit: &str = "literal";
    let owned: String = lit.to_string();
    let view: &str = owned.as_str();
    println!("{} {}", owned, view);
}
