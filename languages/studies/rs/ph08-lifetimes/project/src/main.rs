// 来源：languages/rs/ph08-lifetimes/project/README.md（阶段项目：只读配置视图）
// 说明：从配置文本中借用字段并提供查询接口——section 分组、通用 get、行号定位，零拷贝，含单元测试
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 src/main.rs -o /tmp/proj
// 运行：/tmp/proj
// 测试：rustc --edition 2021 --test src/main.rs -o /tmp/proj_test && /tmp/proj_test
// 验证状态：已验证（编译零警告，8 个单元测试全部通过）

/// 一条配置条目：key 与 value 都借用原文，零拷贝
#[derive(Debug)]
struct Entry<'a> {
    section: &'a str, // 所属 section 名；空串表示全局（不在任何 [section] 下）
    key: &'a str,
    value: &'a str,
    lineno: usize, // 1-based 行号，定位用
}

/// 只读配置视图：所有条目借用同一份原文 `text`，实例不能比原文活得久
///
/// 生命周期结构：
/// - `parse(text: &'a str) -> ConfigView<'a>`：输入借用与视图绑定同一个 'a
/// - `get(...) -> Option<&'a str>`：返回值显式绑定 'a（原文），而不是 &self——
///   这样即使视图本身被 drop，取出的切片在原文存活期内依然有效
struct ConfigView<'a> {
    entries: Vec<Entry<'a>>,
}

impl<'a> ConfigView<'a> {
    /// 解析 key=value 文本；支持 [section] 分组、# 注释与空行
    fn parse(text: &'a str) -> ConfigView<'a> {
        let mut entries = Vec::new();
        let mut section: &'a str = "";
        for (i, raw) in text.lines().enumerate() {
            let line = raw.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            if let Some(name) = line.strip_prefix('[').and_then(|s| s.strip_suffix(']')) {
                section = name.trim();
                continue;
            }
            if let Some((key, value)) = line.split_once('=') {
                entries.push(Entry {
                    section,
                    key: key.trim(),
                    value: value.trim(),
                    lineno: i + 1,
                });
            }
        }
        ConfigView { entries }
    }

    /// 通用查询：支持 "key"（全局）与 "section.key"（分组内）两种形式
    /// 返回 &'a str 而非 &'self str：切片属于原文，不属于视图
    fn get(&self, key: &str) -> Option<&'a str> {
        let (section, bare) = match key.split_once('.') {
            Some((s, k)) => (s, k),
            None => ("", key),
        };
        self.entries
            .iter()
            .find(|e| e.section == section && e.key == bare)
            .map(|e| e.value)
    }

    /// 查询某个 key 定义在原文第几行（1-based）
    fn lineno_of(&self, key: &str) -> Option<usize> {
        let (section, bare) = match key.split_once('.') {
            Some((s, k)) => (s, k),
            None => ("", key),
        };
        self.entries
            .iter()
            .find(|e| e.section == section && e.key == bare)
            .map(|e| e.lineno)
    }

    /// 列出一个 section 内的全部 (key, value)
    fn section(&self, name: &str) -> Vec<(&'a str, &'a str)> {
        self.entries
            .iter()
            .filter(|e| e.section == name)
            .map(|e| (e.key, e.value))
            .collect()
    }

    /// 条目总数（含所有 section）
    fn len(&self) -> usize {
        self.entries.len()
    }
}

fn main() {
    let text = String::from(
        "# cache service config\n\
         host=0.0.0.0\n\
         port=6379\n\
         \n\
         [db]\n\
         host=db-01.internal\n\
         port=5432\n\
         retries=5\n\
         \n\
         [log]\n\
         level=info\n",
    );

    // 视图借用 text，零拷贝；text 存活期间 view 才有效
    let view = ConfigView::parse(&text);

    println!("global host : {}", view.get("host").unwrap_or("(missing)"));
    println!("db.host     : {}", view.get("db.host").unwrap_or("(missing)"));
    println!("db.port     : line {:?}", view.lineno_of("db.port"));
    println!("log.level   : {}", view.get("log.level").unwrap_or("(missing)"));
    println!("missing key : {:?}", view.get("db.timeout"));
    println!("entries     : {}", view.len());

    println!("\n[db] section:");
    for (k, v) in view.section("db") {
        println!("  {k} = {v}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = "host=0.0.0.0\n\
                          port=6379\n\
                          # comment\n\
                          \n\
                          [db]\n\
                          host=db-01.internal\n\
                          port=5432\n\
                          [log]\n\
                          level=info\n";

    #[test]
    fn parses_global_keys() {
        let view = ConfigView::parse(SAMPLE);
        assert_eq!(view.get("host"), Some("0.0.0.0"));
        assert_eq!(view.get("port"), Some("6379"));
    }

    #[test]
    fn parses_section_keys() {
        let view = ConfigView::parse(SAMPLE);
        assert_eq!(view.get("db.host"), Some("db-01.internal"));
        assert_eq!(view.get("log.level"), Some("info"));
    }

    #[test]
    fn section_does_not_leak_to_global() {
        let view = ConfigView::parse(SAMPLE);
        // db.host 不应覆盖全局 host；全局查询不到 section 内的 key
        assert_eq!(view.get("host"), Some("0.0.0.0"));
        assert_eq!(view.get("level"), None);
    }

    #[test]
    fn missing_key_returns_none() {
        let view = ConfigView::parse(SAMPLE);
        assert_eq!(view.get("db.timeout"), None);
        assert_eq!(view.get("nope"), None);
    }

    #[test]
    fn lineno_is_one_based() {
        let view = ConfigView::parse(SAMPLE);
        assert_eq!(view.lineno_of("host"), Some(1));   // 第 1 行
        assert_eq!(view.lineno_of("db.host"), Some(6)); // [db] 在第 5 行
    }

    #[test]
    fn section_listing() {
        let view = ConfigView::parse(SAMPLE);
        assert_eq!(
            view.section("db"),
            vec![("host", "db-01.internal"), ("port", "5432")]
        );
        assert_eq!(view.section("log"), vec![("level", "info")]);
        assert!(view.section("nope").is_empty());
    }

    #[test]
    fn counts_entries_skipping_comments_and_headers() {
        let view = ConfigView::parse(SAMPLE);
        // host, port, db.host, db.port, log.level —— 注释/空行/section 头不计入
        assert_eq!(view.len(), 5);
    }

    #[test]
    fn returned_slice_outlives_the_view() {
        // get 返回 &'a str（绑定原文）而非 &self：视图 drop 后切片仍可用
        let text = String::from("host=db-01.internal\n");
        let host = {
            let view = ConfigView::parse(&text);
            view.get("host").expect("host should exist")
        }; // view 在这里被 drop
        assert_eq!(host, "db-01.internal"); // 切片仍有效：它属于 text
    }
}
