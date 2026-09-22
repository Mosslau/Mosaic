// exercises/sol-02-temperature-converter.rs —— 温度转换器：函数表达式返回 + match 选方向
// 验证环境：rustc 1.92.0
// 编译：rustc sol-02-temperature-converter.rs -o sol02
// 运行：./sol02
// 已验证：本环境编译零警告，0°C=32.0°F、100°C=212.0°F、98.6°F=37.0°C

fn celsius_to_fahrenheit(c: f64) -> f64 {
    // 最后一行无分号：表达式即返回值
    c * 9.0 / 5.0 + 32.0
}

fn fahrenheit_to_celsius(f: f64) -> f64 {
    (f - 32.0) * 5.0 / 9.0
}

fn main() {
    for c in [0.0, 100.0] {
        println!("{}°C = {:.1}°F", c, celsius_to_fahrenheit(c));
    }

    let value = 98.6;
    let mode = 'F';
    let result = match mode {
        'C' => celsius_to_fahrenheit(value),
        'F' => fahrenheit_to_celsius(value),
        _ => {
            println!("未知模式");
            0.0
        }
    };
    println!("{}°F = {:.1}°C", value, result);
}
