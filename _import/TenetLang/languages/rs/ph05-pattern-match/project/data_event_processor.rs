// project/data_event_processor.rs —— 数据事件处理器：enum 事件建模 + match 穷尽分发 + 分组统计
// 来源：project/README.md（roadmap ph05 推荐项目「数据事件处理器」）
// 说明：五种数据事件（写入/删除/更新/过期/告警）用 enum 建模，process 用 match 生成结构化日志，
//       EventStats 用 match 累计计数；末尾 #[cfg(test)] 单元测试覆盖分发与统计路径
// 验证环境：rustc 1.92.0，零第三方依赖
// 编译：rustc data_event_processor.rs -o /tmp/data_event_processor
// 运行：/tmp/data_event_processor
// 测试：rustc --test data_event_processor.rs -o /tmp/data_event_processor_test && /tmp/data_event_processor_test
// 验证状态：已验证（rustc 1.92.0）

use std::fmt;

/// 告警级别：本身用 enum 表达，替代 "info"/"warning"/"critical" 魔法字符串。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum AlertLevel {
    Info,
    Warning,
    Critical,
}

impl AlertLevel {
    /// 字符串 -> enum：解析失败返回 None，由调用方决定处理方式（不 panic）。
    fn from_str(s: &str) -> Option<AlertLevel> {
        match s {
            "info" => Some(AlertLevel::Info),
            "warning" => Some(AlertLevel::Warning),
            "critical" => Some(AlertLevel::Critical),
            _ => None,
        }
    }
}

impl fmt::Display for AlertLevel {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            AlertLevel::Info => "info",
            AlertLevel::Warning => "warning",
            AlertLevel::Critical => "critical",
        };
        f.write_str(s)
    }
}

/// 数据平台的五种事件类型：每个变体携带类型化数据，非法组合不可表达。
#[derive(Debug, Clone, PartialEq)]
enum DataEvent {
    Write { key: String, value: Vec<u8> },
    Delete { key: String },
    Update { key: String, value: Vec<u8>, old_version: u64 },
    Expire { key: String, at: u64 },
    Alert { level: AlertLevel, message: String },
}

impl DataEvent {
    /// 返回事件的类型标签，供统计分组与测试断言使用。
    fn kind(&self) -> &'static str {
        match self {
            DataEvent::Write { .. } => "write",
            DataEvent::Delete { .. } => "delete",
            DataEvent::Update { .. } => "update",
            DataEvent::Expire { .. } => "expire",
            DataEvent::Alert { .. } => "alert",
        }
    }
}

/// 逐事件处理：match 穷尽覆盖全部五种变体，生成结构化日志行。
///
/// 新增事件类型（如 `DataEvent::Merge`）时，编译器会在这里报 E0004——
/// 这就是"忘记处理"从运行时 bug 变成编译期错误的体现。
fn process(event: &DataEvent) -> String {
    match event {
        DataEvent::Write { key, value } => {
            format!("[write]  写入 key={}, 大小={}B", key, value.len())
        }
        DataEvent::Delete { key } => {
            format!("[delete] 删除 key={}", key)
        }
        DataEvent::Update { key, value, old_version } => {
            format!("[update] 更新 key={}, 大小={}B, 旧版本={}", key, value.len(), old_version)
        }
        DataEvent::Expire { key, at } => {
            format!("[expire] 过期 key={}, 过期时间={}", key, at)
        }
        DataEvent::Alert { level, message } => {
            // 嵌套 enum 的 match：级别决定日志前缀
            let prefix = match level {
                AlertLevel::Info => "提示",
                AlertLevel::Warning => "警告",
                AlertLevel::Critical => "严重",
            };
            format!("[alert]  {} [{}]: {}", prefix, level, message)
        }
    }
}

/// 事件统计：按类型累计计数。
#[derive(Debug, Default, Clone, PartialEq)]
struct EventStats {
    write: u64,
    delete: u64,
    update: u64,
    expire: u64,
    alert: u64,
}

impl EventStats {
    /// 逐事件累计：match 穷尽，新增事件类型时同样强制更新此处。
    fn record(&mut self, event: &DataEvent) {
        match event {
            DataEvent::Write { .. } => self.write += 1,
            DataEvent::Delete { .. } => self.delete += 1,
            DataEvent::Update { .. } => self.update += 1,
            DataEvent::Expire { .. } => self.expire += 1,
            DataEvent::Alert { .. } => self.alert += 1,
        }
    }

    fn total(&self) -> u64 {
        self.write + self.delete + self.update + self.expire + self.alert
    }
}

fn main() {
    let events = vec![
        DataEvent::Write { key: "user:1".into(), value: vec![1, 2, 3] },
        DataEvent::Update { key: "user:1".into(), value: vec![4, 5, 6], old_version: 1 },
        DataEvent::Write { key: "session:42".into(), value: vec![0xAB] },
        DataEvent::Delete { key: "temp:99".into() },
        DataEvent::Expire { key: "session:42".into(), at: 1_723_159_200 },
        DataEvent::Alert { level: AlertLevel::Warning, message: "写入延迟超过 100ms".into() },
        DataEvent::Alert { level: AlertLevel::Critical, message: "磁盘空间不足 10%".into() },
        DataEvent::Alert { level: AlertLevel::Info, message: "备份完成".into() },
    ];

    println!("== 事件处理日志 ==");
    let mut stats = EventStats::default();
    for event in &events {
        stats.record(event);
        println!("{}", process(event));
    }

    // kind() 给出事件的类型标签，按事件流顺序串成序列
    let kinds: Vec<&str> = events.iter().map(DataEvent::kind).collect();
    println!("\n== 事件统计 ==");
    println!("事件类型序列: {}", kinds.join(", "));
    println!(
        "总事件数: {}  (write={} delete={} update={} expire={} alert={})",
        stats.total(),
        stats.write,
        stats.delete,
        stats.update,
        stats.expire,
        stats.alert,
    );

    // 边界转换演示：来自外部配置的字符串级别 -> enum，解析失败回落 Info（不 panic）
    let level = AlertLevel::from_str("warning").unwrap_or(AlertLevel::Info);
    println!("解析 'warning' -> {:?}", level);
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 构造 Write 事件的便捷函数。
    fn write(key: &str, value: &[u8]) -> DataEvent {
        DataEvent::Write { key: key.to_string(), value: value.to_vec() }
    }

    #[test]
    fn process_covers_all_five_variants() {
        let events = vec![
            write("user:1", &[1, 2, 3]),
            DataEvent::Delete { key: "temp:99".into() },
            DataEvent::Update { key: "user:1".into(), value: vec![4, 5], old_version: 1 },
            DataEvent::Expire { key: "s:42".into(), at: 1_723_159_200 },
            DataEvent::Alert { level: AlertLevel::Critical, message: "oom".into() },
        ];
        let lines: Vec<String> = events.iter().map(process).collect();
        assert_eq!(lines.len(), 5);
        // 每种事件生成不同前缀的结构化日志
        assert!(lines[0].starts_with("[write]"));
        assert!(lines[1].starts_with("[delete]"));
        assert!(lines[2].starts_with("[update]"));
        assert!(lines[3].starts_with("[expire]"));
        assert!(lines[4].starts_with("[alert]"));
    }

    #[test]
    fn process_reads_payload_fields() {
        let write_line = process(&write("user:1", &[1, 2, 3]));
        assert_eq!(write_line, "[write]  写入 key=user:1, 大小=3B");

        let update_line = process(&DataEvent::Update {
            key: "user:1".into(),
            value: vec![9, 9],
            old_version: 2,
        });
        assert_eq!(update_line, "[update] 更新 key=user:1, 大小=2B, 旧版本=2");
    }

    #[test]
    fn alert_level_prefix_distinguishes_critical() {
        let info = process(&DataEvent::Alert {
            level: AlertLevel::Info,
            message: "例行巡检".into(),
        });
        let critical = process(&DataEvent::Alert {
            level: AlertLevel::Critical,
            message: "磁盘空间不足".into(),
        });
        assert!(info.starts_with("[alert]  提示 [info]"));
        assert!(critical.starts_with("[alert]  严重 [critical]"));
    }

    #[test]
    fn stats_record_counts_per_kind() {
        let events = vec![
            write("a", &[1]),
            write("b", &[2]),
            DataEvent::Delete { key: "c".into() },
            DataEvent::Alert { level: AlertLevel::Warning, message: "w".into() },
        ];
        let mut stats = EventStats::default();
        for e in &events {
            stats.record(e);
        }
        assert_eq!(stats.write, 2);
        assert_eq!(stats.delete, 1);
        assert_eq!(stats.alert, 1);
        assert_eq!(stats.update, 0);
        assert_eq!(stats.expire, 0);
        assert_eq!(stats.total(), 4);
    }

    #[test]
    fn kind_labels_match_stats_fields() {
        assert_eq!(write("a", &[1]).kind(), "write");
        assert_eq!(DataEvent::Delete { key: "a".into() }.kind(), "delete");
        assert_eq!(DataEvent::Expire { key: "a".into(), at: 0 }.kind(), "expire");
        assert_eq!(
            DataEvent::Alert { level: AlertLevel::Info, message: "m".into() }.kind(),
            "alert"
        );
    }

    #[test]
    fn alert_level_parses_and_displays() {
        assert_eq!(AlertLevel::from_str("critical"), Some(AlertLevel::Critical));
        assert_eq!(AlertLevel::from_str("warning"), Some(AlertLevel::Warning));
        assert_eq!(AlertLevel::from_str("verbose"), None);
        assert_eq!(AlertLevel::Warning.to_string(), "warning");
    }
}
