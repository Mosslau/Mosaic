// exercises/sol-02-device-status.rs —— 练习 2 参考实现：设备状态字符串状态码改 enum
// 来源：exercises/README.md 练习 2（roadmap 承诺「把字符串状态码改成 enum」）
// 验证环境：rustc 1.92.0
// 编译：rustc sol-02-device-status.rs -o /tmp/sol-02-device-status
// 运行：/tmp/sol-02-device-status
// 验证状态：已验证（rustc 1.92.0）

/// 设备状态：Fault 携带错误码，非法状态不可表达。
#[derive(Debug, Clone, Copy, PartialEq)]
enum DeviceStatus {
    Online,
    Offline,
    Fault(u32),
}

impl DeviceStatus {
    /// 字符串 -> enum：边界转换，未知字符串返回带原因的 Err。
    ///
    /// "fault:<数字>" 用模式守卫拆出错误码，`strip_prefix` 取到数字段后 parse；
    /// parse 失败（如 "fault:abc"）也返回带原因的 Err，不 panic。
    fn from_str(s: &str) -> Result<DeviceStatus, String> {
        match s {
            "online" => Ok(DeviceStatus::Online),
            "offline" => Ok(DeviceStatus::Offline),
            other if other.starts_with("fault:") => {
                let code = other.strip_prefix("fault:").unwrap_or("0");
                code.parse::<u32>()
                    .map(DeviceStatus::Fault)
                    .map_err(|_| format!("invalid fault code: '{}'", code))
            }
            other => Err(format!("unknown status: '{}'", other)),
        }
    }

    /// enum -> 字符串：唯一出口，杜绝拼写错误。
    fn as_str(&self) -> String {
        match self {
            DeviceStatus::Online => "online".to_string(),
            DeviceStatus::Offline => "offline".to_string(),
            DeviceStatus::Fault(code) => format!("fault:{}", code),
        }
    }
}

fn main() {
    // 合法转换
    assert_eq!(DeviceStatus::from_str("online"), Ok(DeviceStatus::Online));
    assert_eq!(DeviceStatus::from_str("fault:500"), Ok(DeviceStatus::Fault(500)));

    // 非法输入返回带原因的 Err
    assert!(DeviceStatus::from_str("disconnected").is_err());
    assert!(DeviceStatus::from_str("fault:abc").is_err());

    // 反向转换与往返一致
    assert_eq!(DeviceStatus::Fault(500).as_str(), "fault:500");
    assert_eq!(
        DeviceStatus::from_str(&DeviceStatus::Online.as_str()),
        Ok(DeviceStatus::Online)
    );

    // 业务分发：match 穷尽覆盖，新增变体编译器会在这里报错
    let status = DeviceStatus::Fault(500);
    let action = match status {
        DeviceStatus::Online => "允许访问".to_string(),
        DeviceStatus::Offline => "等待上线".to_string(),
        DeviceStatus::Fault(code) => format!("报障，错误码：{}", code),
    };
    println!("状态 {} 的动作：{}", status.as_str(), action);
    println!("全部断言通过");
}
