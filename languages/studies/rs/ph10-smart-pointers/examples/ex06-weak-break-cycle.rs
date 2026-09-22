// 来源：languages/rs/ph10-smart-pointers/examples/ —— 主文档第 6 章示例 6
// 说明：Weak 打破循环引用。前半段：树结构「父持子强引用、子指父弱引用」，实测强/弱计数
//       并验证父先释放后 upgrade() 返回 None、Drop 正常触发（无泄漏）；后半段：构造
//       两个 Rc 互指的环，演示引用计数永不归零的内存泄漏（Drop 不触发）。
// 注意：后半段是「故意演示内存泄漏」——泄漏发生在进程内，进程退出时由操作系统回收，
//       本示例无实际危害；它存在的意义是让你亲眼看到循环引用不会自动释放。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 ex06-weak-break-cycle.rs -o /tmp/ex06
// 运行：/tmp/ex06
// 验证状态：已验证（编译零警告，计数与 drop 打印顺序与注释一致）

use std::cell::RefCell;
use std::rc::{Rc, Weak};

#[derive(Debug)]
struct Node {
    name: &'static str,
    value: i32,
    parent: RefCell<Weak<Node>>,      // 弱引用：不增加强引用计数——「子认识父」
    children: RefCell<Vec<Rc<Node>>>, // 强引用：父拥有子
}

impl Node {
    fn new(name: &'static str, value: i32) -> Self {
        Node {
            name,
            value,
            parent: RefCell::new(Weak::new()),
            children: RefCell::new(Vec::new()),
        }
    }
}

impl Drop for Node {
    fn drop(&mut self) {
        println!("drop Node {}", self.name);
    }
}

fn main() {
    // ===== 前半段：Weak 打破循环，释放正常 =====
    let root = Rc::new(Node::new("root", 10));
    let leaf = Rc::new(Node::new("leaf", 3));

    root.children.borrow_mut().push(Rc::clone(&leaf)); // 父持子：强引用
    *leaf.parent.borrow_mut() = Rc::downgrade(&root);  // 子指父：弱引用，不构成环

    println!("root strong = {} weak = {}", Rc::strong_count(&root), Rc::weak_count(&root)); // 1 / 1
    println!("leaf strong = {} weak = {}", Rc::strong_count(&leaf), Rc::weak_count(&leaf)); // 2 / 0

    // 升级弱引用访问父节点：先绑定借用 guard，避免临时借用跨 if-let 存活
    let parent_ref = leaf.parent.borrow();
    if let Some(parent) = parent_ref.upgrade() {
        println!("leaf 的父节点 {} value = {}", parent.name, parent.value); // root 10
    }

    // 先释放 root：root 的 Drop 触发（强计数 1 -> 0），children 里的 leaf 引用随之减少
    drop(root);

    // leaf 还活着，但它对父的弱引用已悬空
    match leaf.parent.borrow().upgrade() {
        Some(_) => println!("父还活着"),
        None => println!("父已释放：upgrade() 返回 None（弱引用不阻止目标释放）"),
    }
    println!("leaf strong = {}", Rc::strong_count(&leaf)); // 1（只剩变量 leaf）
    // main 结束时 leaf 释放，打印 drop Node leaf——两条边都有正确释放，无泄漏

    // ===== 后半段：不用 Weak 的循环引用泄漏（故意演示，进程退出时由 OS 回收） =====
    println!("\n--- 循环引用泄漏演示（故意，进程退出时由 OS 回收） ---");
    let a = Rc::new(Node::new("a", 1));
    let b = Rc::new(Node::new("b", 2));
    println!("成环前: a strong={} b strong={}", Rc::strong_count(&a), Rc::strong_count(&b)); // 1 / 1
    *a.children.borrow_mut() = vec![Rc::clone(&b)]; // a -> b
    *b.children.borrow_mut() = vec![Rc::clone(&a)]; // b -> a，形成环
    println!("成环后: a strong={} b strong={}", Rc::strong_count(&a), Rc::strong_count(&b)); // 2 / 2

    drop(a);
    drop(b);
    // 两个句柄都已 drop，但「drop Node a/b」没有打印：环上的强计数互相支撑、永不归零，
    // 堆数据成为孤儿泄漏——Rust 不报编译错（这是逻辑泄漏，不是 UB），只能靠 Weak 或设计避免。
    println!("两个句柄已 drop，但 Node 的 drop 没有触发 —— 循环引用泄漏（计数停留 1/1）");
}
