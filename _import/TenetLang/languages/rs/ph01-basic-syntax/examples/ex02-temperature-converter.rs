// examples/ex02-temperature-converter.rs —— 温度转换器：摄氏/华氏互转，用 match 选择方向
// 验证环境：rustc 1.92.0
// 编译：rustc ex02-temperature-converter.rs -o ex02
// 运行：./ex02
// 已验证：本环境编译零警告，输出 0°C=32.0°F、100°C=212.0°F，98.6°F→37.0°C

fn celsius_to_fahrenheit(c: f64) -> f64 {
    c * 9.0 / 5.0 + 32.0
}

fn fahrenheit_to_celsius(f: f64) -> f64 {
    (f - 32.0) * 5.0 / 9.0
}

fn main() {
    let temps_c = [0.0, 20.0, 37.0, 100.0];

    println!("摄氏度 -> 华氏度：");
    for c in temps_c.iter() {
        let f = celsius_to_fahrenheit(*c);
        println!("  {}°C = {:.1}°F", c, f);
    }

    // 使用 match 选择转换方向
    let mode = 'F'; // 'F' 表示华氏转摄氏，'C' 反之
    let value = 98.6;
    let result = match mode {
        'C' => celsius_to_fahrenheit(value),
        'F' => fahrenheit_to_celsius(value),
        _ => {
            println!("未知模式");
            0.0
        }
    };
    println!("Result: {:.1}", result);
}
