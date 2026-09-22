// examples/ex01-device-state.rs —— 设备状态建模：三种状态携带不同数据，match 一次性处理，matches! 判断可用性
// 来源：05-pattern-match.md 第 6 章示例 1
// 验证环境：rustc 1.92.0，零第三方依赖
// 编译：rustc ex01-device-state.rs -o /tmp/ex01-device-state
// 运行：/tmp/ex01-device-state
// 验证状态：已验证（rustc 1.92.0）

/// 设备状态：每个变体携带不同数据（ADT 的和类型）。
#[derive(Debug)]
enum DeviceState {
    Online { ip: String, uptime_secs: u64 },
    Offline,
    Fault(u32),
}

impl DeviceState {
    /// 生成人类可读的状态描述；match 自引用 &self，模式自动解出引用。
    fn describe(&self) -> String {
        match self {
            DeviceState::Online { ip, uptime_secs } => {
                format!("在线 — IP: {}, 运行: {}s", ip, uptime_secs)
            }
            DeviceState::Offline => "离线".to_string(),
            DeviceState::Fault(code) => format!("故障 — 错误码: {}", code),
        }
    }

    /// matches! 返回 bool：一行替代三行 match（只判断变体、不关心携带数据）。
    fn is_available(&self) -> bool {
        matches!(self, DeviceState::Online { .. })
    }
}

fn main() {
    let devs = vec![
        DeviceState::Online { ip: "192.168.1.1".into(), uptime_secs: 3600 },
        DeviceState::Fault(500),
        DeviceState::Offline,
    ];
    for d in &devs {
        println!("[{}] {}", if d.is_available() { "可用" } else { "不可用" }, d.describe());
    }
}
