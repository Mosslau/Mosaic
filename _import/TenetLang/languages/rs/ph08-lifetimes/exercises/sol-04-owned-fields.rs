// 来源：languages/rs/ph08-lifetimes/exercises/README.md 练习 4
// 说明：把不必要的引用字段改成拥有字段——&'a str → String，生命周期参数整体消失
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-04-owned-fields.rs -o /tmp/sol04
// 运行：/tmp/sol04
// 验证状态：已验证（编译零警告，输出符合预期）

// 改造前（对照，保留为注释）：引用字段，<'a> 共出现在 4 类位置——
//   ① 结构体定义 struct Server<'a>
//   ② impl 块 impl<'a> Server<'a>
//   ③ 作为参数/返回类型的每个使用处（如 fn f(s: Server<'a>)）
//   ④ 持有它的外层结构体/Vec 的类型标注
// struct Server<'a> { host: &'a str, endpoint: &'a str }
// impl<'a> Server<'a> {
//     fn host(&self) -> &str { self.host }
// }

// 改造后：拥有字段，生命周期参数整体消失（代价：构造时多一次堆分配与拷贝）
#[derive(Debug)]
struct Server {
    host: String,
    endpoint: String,
}

impl Server {
    fn new(host: &str, endpoint: &str) -> Self {
        Server {
            host: host.to_string(),     // 拷贝一份，从此自给自足
            endpoint: endpoint.to_string(),
        }
    }
    fn host(&self) -> &str { &self.host }
    fn endpoint(&self) -> &str { &self.endpoint }
}

// 拥有字段的收益：Server 可以自由 move 进函数、存进 Vec，不受任何借用约束
fn count_endpoints(servers: Vec<Server>) -> usize {
    servers.len()
}

fn main() {
    let servers = vec![
        Server::new("db-01", "postgres://db-01:5432"),
        Server::new("cache-01", "redis://cache-01:6379"),
    ];
    for s in &servers {
        println!("{} -> {}", s.host(), s.endpoint());
    }
    let n = count_endpoints(servers); // 所有权整体移出
    println!("total: {n}");
}
