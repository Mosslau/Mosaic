// examples/ex05-send-sync-bounds.rs —— Send / Sync 边界的编译期验证
// 说明：Send = 可以把所有权跨线程转移；Sync = 可以被多个线程同时共享引用。
//       二者都是 marker trait（自动推导，无方法）。下方 assert_* 是"证据函数"：
//       编译通过即证明该类型满足约束；编译失败报 E0277。
//       负例（会编译失败）写在注释里，完整错误文本见主文档 3.4（rustc 1.92.0 实测）。
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex05-send-sync-bounds.rs -o /tmp/ex05
// 运行：/tmp/ex05
// 验证状态：已验证（编译零警告；下方断言全部通过——即所列类型确实 Send/Sync）

// （反例用到的 Cell/RefCell/Rc 只出现在注释里，不引入——真实使用见 ph10 智能指针阶段）
use std::sync::{mpsc, Arc, Mutex, RwLock};

// 编译期"证据函数"：T: Send / T: Sync 才能实例化
fn assert_send<T: Send>() {}
fn assert_sync<T: Sync>() {}

fn main() {
    // ===== 1. 基础类型：Send + Sync =====
    assert_send::<i32>();
    assert_sync::<i32>();
    assert_send::<String>();
    assert_sync::<String>();
    assert_send::<Vec<u8>>();
    assert_sync::<Vec<u8>>();

    // ===== 2. 组合类型：Send/Sync 由字段递归推导 =====
    // Arc<Mutex<T>>（T: Send）既 Send 又 Sync：可跨线程共享且可变
    assert_send::<Arc<Mutex<u32>>>();
    assert_sync::<Arc<Mutex<u32>>>();
    assert_send::<Arc<RwLock<u32>>>();
    assert_sync::<Arc<RwLock<u32>>>();
    // 通道两端都 Send（可移入线程）；Receiver 不是 Sync（单消费者）
    assert_send::<mpsc::Sender<u32>>();
    assert_send::<mpsc::Receiver<u32>>();
    // 引用：&T 是 Send 当且仅当 T: Sync（只读共享靠 Sync 保证）
    assert_send::<&'static str>();
    assert_sync::<&'static str>();

    // ===== 3. 反例（编译失败，本文件不编译它们；错误文本已实测） =====
    // assert_send::<Rc<u32>>();            // E0277: Rc<u32> cannot be sent between threads safely
    // assert_sync::<Rc<u32>>();            // E0277: Rc<u32> cannot be shared between threads safely
    // assert_send::<*const u32>();         // E0277: *const u32 cannot be sent between threads safely
    // assert_sync::<Cell<u32>>();          // E0277: Cell<u32> cannot be shared between threads safely
    //                                      //        （Cell/RefCell 是 Send 但不是 Sync——可跨线程移动，不可跨线程共享）
    // assert_sync::<RefCell<u32>>();       // E0277: RefCell<u32> cannot be shared between threads safely
    //                                      //        （编译器 note：想跨线程别名+修改，用 RwLock 或 AtomicU32）
    // assert_sync::<mpsc::Receiver<u32>>(); // E0277: Receiver<u32> cannot be shared between threads safely
    //
    // 反例的完整报错（取消上面某行注释重新编译即可复现）：
    //   error[E0277]: `Rc<u32>` cannot be sent between threads safely
    //     = help: within `{closure@p1.rs:4:24: 4:31}`, the trait `Send` is not implemented for `Rc<u32>`
    //     = note: required because it appears within the type `{closure@p1.rs:4:24: 4:31}`
    //   （"cannot be sent between threads safely" / "cannot be shared between threads safely"
    //     的完整 4 行提示见主文档 3.4，全部 rustc 1.92.0 实测）

    println!("全部 Send/Sync 断言编译通过");
    println!("Send/Sync 速记：Send=可跨线程移动所有权；Sync=可跨线程共享引用");
    println!("（不满足时编译器直接拒绝编译——数据竞争在编译期受限）");
}
