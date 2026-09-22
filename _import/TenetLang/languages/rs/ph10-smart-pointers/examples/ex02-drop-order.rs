// 来源：languages/rs/ph10-smart-pointers/examples/ —— 主文档第 6 章示例 2
// 说明：Drop 析构顺序三条规则：① 变量按声明逆序 drop；② 结构体先跑 impl Drop 体、
//       再按字段声明顺序析构字段；③ std::mem::drop 可提前触发析构。
//       输出顺序已实测（rustc 1.92.0 运行验证）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex02-drop-order.rs -o /tmp/ex02
// 运行：/tmp/ex02
// 验证状态：已验证（编译零警告，输出顺序与注释一致）

struct Guard {
    name: &'static str,
    tag: u32,
}

impl Drop for Guard {
    fn drop(&mut self) {
        println!("drop Guard {} (tag {})", self.name, self.tag);
    }
}

struct Outer {
    f1: Guard,
    f2: Guard,
}

impl Drop for Outer {
    fn drop(&mut self) {
        // impl Drop 体先于字段析构执行
        println!("drop Outer（impl Drop 体先执行，然后字段按声明顺序析构）");
    }
}

fn main() {
    // 规则 ①：变量按声明逆序 drop——A 先声明，最后释放
    let _a = Guard { name: "A", tag: 1 };
    {
        let _b = Guard { name: "B", tag: 2 };
    } // 内层块结束：B 先 drop（声明逆序的第一层体现）

    // 规则 ③：std::mem::drop 提前移交所有权触发析构，C 不再等到 main 结束
    let c = Guard { name: "C", tag: 3 };
    std::mem::drop(c); // 等价于「立即释放」，与 drop(c) 不能是方法调用（会触发二次 drop，编译错）

    // 规则 ②：结构体的 Drop 体先执行，再按字段声明顺序 f1 -> f2 析构
    let o = Outer {
        f1: Guard { name: "f1", tag: 4 },
        f2: Guard { name: "f2", tag: 5 },
    };
    println!("o 的字段: f1={}, f2={}", o.f1.tag, o.f2.tag);

    // main 结束时的实际输出顺序（实测）：
    // drop Outer（impl Drop 体）-> drop Guard f1 -> drop Guard f2 -> drop Guard A
}
