//! cfg-app —— sol-03 的示例 crate：把一组配置项解析成开关计数。
//!
//! 功能演示足够简单的「可测 + 零警告」代码，让本地检查脚本（scripts/check.sh）有内容可查。

/// 统计配置文本里布尔开关键值为 true/false 的数量。
pub fn count_bools(text: &str) -> (usize, usize) {
    let mut on = 0usize;
    let mut off = 0usize;
    for line in text.lines() {
        let Some((_, v)) = line.split_once('=') else {
            continue;
        };
        match v.trim() {
            "true" => on += 1,
            "false" => off += 1,
            _ => {}
        }
    }
    (on, off)
}

fn main() {
    let cfg = "cache=true\nverbose=false\nretries=3";
    let (on, off) = count_bools(cfg);
    println!("on={on} off={off}");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts_true_and_false() {
        assert_eq!(count_bools("a=true\nb=false\nc=true"), (2, 1));
    }

    #[test]
    fn ignores_non_bool_and_malformed_lines() {
        assert_eq!(count_bools("a=maybe\nno-equals\nb=false"), (0, 1));
        assert_eq!(count_bools(""), (0, 0));
    }
}
