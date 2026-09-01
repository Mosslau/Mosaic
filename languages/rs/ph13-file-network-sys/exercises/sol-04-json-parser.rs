// 来源：languages/rs/ph13-file-network-sys/exercises/README.md 练习 4
// 说明：手写极简 JSON 解析器——只支持扁平对象 {"k": 值}，值为字符串/数字/布尔。
//       Tokenizer + 递归下降，错误带字节位置。纯 std，是 serde_json「替你做的工作」的
//       裸机版（对应 roadmap 练习「解析 JSON 配置」；真实项目用 serde_json，见 examples/crates）。
//       有意简化：不支持嵌套对象/数组/转义字符（教学性覆盖，聚焦解析器骨架）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings sol-04-json-parser.rs -o /tmp/sol04
// 运行：/tmp/sol04
// 验证状态：已验证（编译零警告；解析结果与错误位置为实测）

use std::collections::HashMap;

#[derive(Debug, PartialEq)]
enum Json {
    Str(String),
    Num(f64),
    Bool(bool),
}

struct Parser<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> Parser<'a> {
    fn new(s: &'a str) -> Self {
        Parser { bytes: s.as_bytes(), pos: 0 }
    }

    fn err(&self, msg: &str) -> String {
        format!("解析错误 @ 字节 {}: {}", self.pos, msg)
    }

    fn skip_ws(&mut self) {
        while self.pos < self.bytes.len() && self.bytes[self.pos].is_ascii_whitespace() {
            self.pos += 1;
        }
    }

    fn peek(&self) -> Option<u8> {
        self.bytes.get(self.pos).copied()
    }

    fn expect(&mut self, ch: u8) -> Result<(), String> {
        self.skip_ws();
        match self.peek() {
            Some(b) if b == ch => {
                self.pos += 1;
                Ok(())
            }
            _ => Err(self.err(&format!("期望 {:?}，实际 {:?}", ch as char, self.peek().map(|b| b as char)))),
        }
    }

    fn parse_string(&mut self) -> Result<String, String> {
        // 调用时 skip_ws 已做；当前位置应是 '"'
        self.pos += 1; // 跳过开引号
        let start = self.pos;
        while self.pos < self.bytes.len() && self.bytes[self.pos] != b'"' {
            self.pos += 1;
        }
        if self.pos >= self.bytes.len() {
            return Err(self.err("字符串未闭合"));
        }
        let s = String::from_utf8(self.bytes[start..self.pos].to_vec())
            .map_err(|_| self.err("非法 UTF-8"))?;
        self.pos += 1; // 跳过闭引号
        Ok(s)
    }

    fn parse_number(&mut self) -> Result<Json, String> {
        let start = self.pos;
        while let Some(b) = self.peek() {
            if b.is_ascii_digit() || b == b'.' || b == b'-' {
                self.pos += 1;
            } else {
                break;
            }
        }
        let text = std::str::from_utf8(&self.bytes[start..self.pos]).unwrap();
        text.parse::<f64>()
            .map(Json::Num)
            .map_err(|_| self.err(&format!("无效数字 {text:?}")))
    }

    fn parse_literal(&mut self, word: &str, val: Json) -> Result<Json, String> {
        if self.bytes[self.pos..].starts_with(word.as_bytes()) {
            self.pos += word.len();
            Ok(val)
        } else {
            Err(self.err(&format!("无效字面量（期望 {word}）")))
        }
    }

    fn parse_value(&mut self) -> Result<Json, String> {
        self.skip_ws();
        match self.peek() {
            Some(b'"') => Ok(Json::Str(self.parse_string()?)),
            Some(b) if b.is_ascii_digit() || b == b'-' => self.parse_number(),
            Some(b't') => self.parse_literal("true", Json::Bool(true)),
            Some(b'f') => self.parse_literal("false", Json::Bool(false)),
            other => Err(self.err(&format!("无法解析的值开头 {:?}", other.map(|b| b as char)))),
        }
    }

    /// 解析扁平对象：{"k1": v1, "k2": v2}
    fn parse_object(&mut self) -> Result<HashMap<String, Json>, String> {
        let mut map = HashMap::new();
        self.expect(b'{')?;
        self.skip_ws();
        if self.peek() == Some(b'}') {
            self.pos += 1; // 空对象 {}
            return Ok(map);
        }
        loop {
            self.skip_ws();
            if self.peek() != Some(b'"') {
                return Err(self.err("键必须是字符串"));
            }
            let key = self.parse_string()?;
            self.expect(b':')?;
            let val = self.parse_value()?;
            map.insert(key, val);
            self.skip_ws();
            match self.peek() {
                Some(b',') => self.pos += 1,
                Some(b'}') => {
                    self.pos += 1;
                    return Ok(map);
                }
                other => {
                    return Err(self.err(&format!("期望 , 或 }}，实际 {:?}", other.map(|b| b as char))))
                }
            }
        }
    }
}

fn parse(input: &str) -> Result<HashMap<String, Json>, String> {
    let mut p = Parser::new(input);
    let map = p.parse_object()?;
    p.skip_ws();
    if p.pos != p.bytes.len() {
        return Err(p.err("对象后有多余内容"));
    }
    Ok(map)
}

fn main() {
    // ===== 1. 正常解析 =====
    let m = parse(r#"{ "name": "rust", "port": 8080, "debug": true, "ratio": 0.5 }"#)
        .expect("应解析成功");
    assert_eq!(m["name"], Json::Str("rust".to_string()));
    assert_eq!(m["port"], Json::Num(8080.0));
    assert_eq!(m["debug"], Json::Bool(true));
    assert_eq!(m["ratio"], Json::Num(0.5));
    println!("1. 解析成功: {} 个键", m.len());

    // ===== 2. 空对象 =====
    assert_eq!(parse("{}").unwrap().len(), 0);
    println!("2. 空对象解析通过");

    // ===== 3. 错误定位 =====
    let e = parse(r#"{ "a": oops }"#).unwrap_err();
    println!("3. {e}"); // 字节位置指向 oops
    let e2 = parse(r#"{ "a": 1 }x"#).unwrap_err(); // 对象后还有垃圾
    println!("3.（尾部垃圾）{e2}");
}

// 注：JSON 字符串转义、嵌套结构、Unicode 属完整实现内容——真实场景请用 serde_json
// （examples/crates/ex07，已验证 serde_json 1.0.151）。
