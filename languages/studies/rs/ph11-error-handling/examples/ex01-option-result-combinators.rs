// examples/ex01-option-result-combinators.rs —— Option/Result 组合子（map/and_then/or_else/ok_or_else/?），主文档第 6 章示例 1
// 说明：Option/Result 组合子（map/and_then/or_else/ok_or_else/?）。
//       组合子把「分支处理」压缩成链式调用；? 则让错误传播一行完成。
//       本示例聚焦 ph04 Option/Result 基础之上的组合子用法（ph04 已见过 match、? 与 map/and_then 等组合子；本阶段系统化，并补 or_else/ok_or_else）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex01-option-result-combinators.rs -o /tmp/ex01
// 运行：/tmp/ex01
// 验证状态：已验证（编译零警告；以下输出为实测结果）

fn main() {
    // ===== Result 组合子 =====
    let r: Result<u32, &str> = Ok(42);
    println!("map Ok    = {:?}", r.map(|v| v * 2)); // Ok(84)：只改 Ok 里的值
    let r2: Result<u32, &str> = Err("boom");
    println!("map Err   = {:?}", r2.map(|v| v * 2)); // Err("boom")：错误原样穿过

    // and_then：链式执行「可能失败」的下一步（flatten 后 map）——两段都可能 Err
    let s: Result<&str, &str> = Ok("42");
    println!("and_then  = {:?}", s.and_then(|t| t.parse::<i32>().map_err(|_| "parse fail"))); // Ok(42)

    // or_else：失败时走替代路径（闭包拿到错误值，可记录后再换路）
    let e: Result<u32, &str> = Err("not found");
    println!("or_else   = {:?}", e.or_else(|msg| { println!("  (记录: {msg})"); Ok::<u32, &str>(7) })); // Ok(7)

    // ok_or_else + ?：Option 转 Result——「可能没有」升级为「可能出错」，附带错误消息
    let o: Option<u32> = None;
    println!("ok_or_else = {:?}", o.ok_or_else(|| "missing value")); // Err("missing value")

    // ===== Option 组合子 =====
    let some: Option<i32> = Some(5);
    let none: Option<i32> = None;
    println!("opt map     = {:?}", some.map(|v| v + 1));        // Some(6)
    println!("opt and_then= {:?}", some.and_then(|v| if v > 3 { Some(v * 2) } else { None })); // Some(10)
    println!("opt or_else = {:?}", none.or_else(|| Some(99)));  // Some(99)
    println!("opt unwrap_or = {}", none.unwrap_or(0));          // 0（安全取默认值，不 panic）

    // ===== 组合子 + ? 的真实组合：解析 "key=value" 配置行 =====
    // 返回 Result 而非 Option——失败原因（哪一行、缺什么）比「没有值」更有信息量。
    for line in ["host = 127.0.0.1", "no-equals-here", "debug = true"] {
        match parse_cfg_line(line) {
            Ok((k, v)) => println!("OK   {line:18} -> {k} = {v}"),
            Err(e) => println!("ERR  {line:18} -> {e}"),
        }
    }
}

fn parse_cfg_line(line: &str) -> Result<(String, String), String> {
    let (k, v) = line
        .split_once('=')
        .ok_or_else(|| format!("缺少 '=' 分隔符: {line:?}"))?; // Option -> Result（ok_or_else + ?）
    Ok((k.trim().to_string(), v.trim().to_string()))
}
