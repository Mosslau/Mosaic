// 来源：languages/rs/ph10-smart-pointers/exercises/README.md 练习 5
// 说明：用 Weak 打破循环引用——树结构「父持子强引用、子指父弱引用」；
//       实测强/弱计数（root strong=1 weak=2，两个叶子各 strong=2），
//       父先释放后叶子 upgrade() 返回 None，Drop 打印证明所有节点正常释放（无泄漏）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 sol-05-weak-tree.rs -o /tmp/sol05
// 运行：/tmp/sol05
// 验证状态：已验证（编译零警告，计数与 drop 打印顺序与注释一致）

use std::cell::RefCell;
use std::rc::{Rc, Weak};

#[derive(Debug)]
struct Node {
    name: &'static str,
    value: i32,
    parent: RefCell<Weak<Node>>,      // 弱引用：叶子「认识」父，但不增加强计数
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
    let root = Rc::new(Node::new("root", 100));
    let leaf1 = Rc::new(Node::new("leaf1", 1));
    let leaf2 = Rc::new(Node::new("leaf2", 2));

    // 父持子：强引用；子指父：弱引用（不构成环）
    root.children.borrow_mut().push(Rc::clone(&leaf1));
    root.children.borrow_mut().push(Rc::clone(&leaf2));
    *leaf1.parent.borrow_mut() = Rc::downgrade(&root);
    *leaf2.parent.borrow_mut() = Rc::downgrade(&root);

    println!("root strong = {} weak = {}", Rc::strong_count(&root), Rc::weak_count(&root)); // 1 / 2
    println!("leaf1 strong = {}", Rc::strong_count(&leaf1)); // 2（变量 + root.children 各一份强引用）
    println!("leaf2 strong = {}", Rc::strong_count(&leaf2)); // 2

    // 升级弱引用访问父节点：先绑定借用 guard，避免临时借用跨 if-let 存活
    {
        let parent_ref = leaf1.parent.borrow();
        if let Some(parent) = parent_ref.upgrade() {
            println!("leaf1 的父节点 {} value = {}", parent.name, parent.value); // root 100
        }
    } // parent_ref 离开作用域，借用归还——guard 不释放会阻止后续 drop(leaf1)（E0505）

    // 先释放 root：root Drop 触发，children 里的 leaf 引用随之减少，但 leaf 仍被变量持有
    drop(root);
    assert_eq!(Rc::strong_count(&leaf1), 1); // 只剩变量 leaf1

    // 父已释放：弱引用悬空，upgrade() 返回 None——弱引用不阻止目标释放
    match leaf1.parent.borrow().upgrade() {
        Some(_) => println!("父还活着（不该走到这里）"),
        None => println!("父已释放：leaf1.parent.upgrade() 返回 None"),
    }
    match leaf2.parent.borrow().upgrade() {
        Some(_) => println!("父还活着（不该走到这里）"),
        None => println!("父已释放：leaf2.parent.upgrade() 返回 None"),
    }

    // 显式释放两个叶子，Drop 打印证明全部节点都正常释放（无循环泄漏）
    drop(leaf1);
    drop(leaf2);
}
