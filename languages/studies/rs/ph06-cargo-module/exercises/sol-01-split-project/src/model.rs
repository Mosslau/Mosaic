// exercises/sol-01-split-project/src/model.rs —— 练习 1 参考实现：数据模型层
// 拆分自 exercises/ex01-single-source.rs 的 CityTemp
// 验证环境：rustc 1.92.0 + cargo 1.92.0，纯标准库
// 编译：cargo build（在 sol-01-split-project/ 目录内执行）
// 验证状态：已验证（rustc 1.92.0）

#[derive(Debug, Clone, PartialEq)]
pub struct CityTemp {
    pub ts: u64,      // 时间戳（Unix 秒）
    pub city: String, // 城市
    pub temp: f64,    // 温度
}
