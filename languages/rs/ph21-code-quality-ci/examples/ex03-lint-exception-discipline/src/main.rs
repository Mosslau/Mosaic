// ex03-lint-exception-discipline —— lint 例外纪律演示（主 crate，全绿基线）。
//
// 例外纪律三步走（主文档 3.4）：能修则修 → 修不了才 allow → allow 必须解释
// 「为什么这次例外是值得的」。本文件刻意演示三类「站得住」的例外：
//
//   ① #[allow(clippy::too_many_arguments)] —— 固定列数解码入口的 API 形状例外
//   ② #[expect(clippy::manual_map)] —— 预期触发契约（期望落空会反向报错）
//   ③ 测试里 #[allow(clippy::out_of_bounds_indexing)] —— 故意演示 panic 契约
//
// 验证命令（本 crate 目录内）：
//   cargo fmt --check
//   cargo clippy --all-targets -- -D warnings   # 实测全绿
//   cargo test                                   # 实测通过

/// 解码后的一行（与 8 个入参一一对应）。
pub struct Row {
    pub id: u32,
    pub name: String,
    pub city: String,
}

/// 例外 ①：把一行固定 8 列 CSV 的字段逐个传进解码函数。
///
/// 为什么这次例外是值得的：这是**固定列数**的外部格式解码入口——8 个参数与文件 8 列
/// 一一对应，逐个传参让「列序 ↔ 参数序」直接可见；若拆成结构体会让调用方多一次构造，
/// 反而在「列错位」时更难核对。改行结构是 API 重构，不是本函数的 lint 问题，
/// 因此用最小作用域的 allow 登记，并留注释说明治理前提（换格式时才改）。
#[allow(clippy::too_many_arguments)]
pub fn parse_csv_row(
    id: u32,
    name: &str,
    city: &str,
    score: u32,
    active: bool,
    tags: &[&str],
    created: u64,
    note: &str,
) -> Row {
    let _ = (name, city, score, active, tags, created, note); // 演示函数，忽略多余入参
    Row {
        id,
        name: String::from(name),
        city: String::from(city),
    }
}

/// 例外 ②：把分数转成可显示字符串。
///
/// 故意手写 `match`（而不是 `o.map`）是为了让读者看到两臂都不为空值时的形状；
/// `#[expect]` 表示「我预期 manual_map 在这里会触发且我认可」——若将来这段被重构为
/// `.map(...)`，期望落空会产生 `unfulfilled_lint_expectations` 警告提醒删除本行
/// （实测行为见 expect-demo 子 crate，那里演示期望落空的输出）。
#[expect(clippy::manual_map)]
pub fn display_score(o: Option<u32>) -> Option<String> {
    match o {
        Some(score) => Some(format!("{score}/100")),
        None => None,
    }
}

fn main() {
    let row = parse_csv_row(
        7,
        "alice",
        "tokyo",
        99,
        true,
        &["fast", "stable"],
        1_700_000_000,
        "hello",
    );
    println!("id={} name={} city={}", row.id, row.name, row.city);
    println!("score={:?}", display_score(Some(95)));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn display_score_maps_some() {
        assert_eq!(display_score(Some(95)), Some(String::from("95/100")));
        assert_eq!(display_score(None), None);
    }

    #[test]
    #[should_panic(expected = "range start index 99 out of range")]
    #[allow(clippy::out_of_bounds_indexing)] // 例外 ③：故意越界演示裸下标的 panic 契约
    fn naked_index_panics_on_short_buf() {
        // 与 ph20 ex01 同一模式的契约测试：解析层一律用 get() 的原因在此固化成可回归断言；
        // 例外理由 = 教学性覆盖（故意越界，属于本阶段承认的例外类型）
        let buf = b"short";
        let _ = &buf[99..];
    }
}
