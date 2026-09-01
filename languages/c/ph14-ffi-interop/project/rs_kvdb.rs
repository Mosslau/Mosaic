//! rs_kvdb.rs —— Rust 调用 kvdb C ABI 库（roadmap 推荐项目「Rust 调用 C WAL 库」）
//!
//! 编译（macOS）：
//!   cc -Wall -Wextra -std=c11 -dynamiclib kvdb.c -o /tmp/ph14-proj/libkvdb.dylib
//!   rustc --edition 2021 -D warnings rs_kvdb.rs -L /tmp/ph14-proj -l kvdb \
//!         -o /tmp/ph14-proj/rs_kvdb
//! 运行：/tmp/ph14-proj/rs_kvdb [/tmp/ph14-proj/rs-test.db]
//!
//! 验证环境：rustc 1.92.0 + Apple clang 21.0.0（macOS arm64）
//! 验证状态：已验证（零警告; 全部断言通过, 退出码 0; 实测输出见文件尾）
//!
//! 要点：
//!   - opaque 句柄 = 裸指针，只在 C 函数之间传递，不拆解内部布局
//!   - get 的"调用方分配缓冲区"约定：Rust 侧用 [u8; N] 数组当缓冲区
//!   - 错误码：err_out 出参 + kvdb_strerror 读消息; create 失败判 NULL
//!   - WAL 持久化：sync → destroy → 重开后数据仍在（回放恢复）

use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_int, c_uchar, c_uint, c_void};

const KVDB_OK: c_int = 0;
const KVDB_ERR_BADARG: c_int = -1;
const KVDB_ERR_NOTFOUND: c_int = -5;

#[link(name = "kvdb")]
extern "C" {
    fn kvdb_create(path: *const c_char, err_out: *mut c_int) -> *mut c_void;
    fn kvdb_put(db: *mut c_void, key: *const c_char, val: *const c_void,
                vlen: c_uint) -> c_int;
    fn kvdb_get(db: *mut c_void, key: *const c_char, out: *mut c_void,
                cap: c_uint, vlen_out: *mut c_uint) -> c_int;
    fn kvdb_sync(db: *mut c_void) -> c_int;
    fn kvdb_destroy(db: *mut c_void) -> c_int;
    fn kvdb_strerror(err: c_int) -> *const c_char;
}

fn err_str(err: c_int) -> String {
    let p = unsafe { kvdb_strerror(err) };
    if p.is_null() {
        String::from("<null>")
    } else {
        unsafe { CStr::from_ptr(p) }.to_string_lossy().into_owned()
    }
}

fn main() {
    let wal = std::env::args().nth(1).unwrap_or_else(
        || "/tmp/ph14-proj/rs-test.db".to_string());
    let _ = std::fs::remove_file(&wal);          // 从干净状态开始
    let path = CString::new(wal).expect("路径不含 NUL");

    let mut err: c_int = KVDB_OK;
    let db = unsafe { kvdb_create(path.as_ptr(), &mut err) };
    assert!(!db.is_null(), "kvdb_create 失败: {}", err_str(err));
    println!("rs: kvdb_create ok（新建 WAL）");

    // put 文本值（CString 传字符串）
    let k_greet = CString::new("greeting").expect("无 NUL");
    let v_greet = CString::new("hello world").expect("无 NUL");
    assert_eq!(unsafe {
        kvdb_put(db, k_greet.as_ptr(), v_greet.as_ptr() as *const c_void, 11)
    }, KVDB_OK);

    // put 二进制值（含 \0）
    let k_blob = CString::new("blob").expect("无 NUL");
    let blob: [c_uchar; 4] = [0x01, 0x00, 0xFF, 0x02];
    assert_eq!(unsafe {
        kvdb_put(db, k_blob.as_ptr(), blob.as_ptr() as *const c_void, 4)
    }, KVDB_OK);

    // get 文本（调用方分配缓冲区）
    let mut buf = [0u8; 64];
    let mut vlen: c_uint = 0;
    assert_eq!(unsafe {
        kvdb_get(db, k_greet.as_ptr(), buf.as_mut_ptr() as *mut c_void,
                 buf.len() as c_uint, &mut vlen)
    }, KVDB_OK);
    let text = std::str::from_utf8(&buf[..vlen as usize]).expect("UTF-8");
    assert_eq!(text, "hello world");
    println!("rs: get greeting -> {:?} (len={})", text, vlen);

    // get 二进制
    let mut out = [0u8; 4];
    let mut vlen2: c_uint = 0;
    assert_eq!(unsafe {
        kvdb_get(db, k_blob.as_ptr(), out.as_mut_ptr() as *mut c_void, 4,
                 &mut vlen2)
    }, KVDB_OK);
    assert_eq!(&out[..vlen2 as usize], &blob);
    println!("rs: get blob -> 二进制往返一致（含 \\0 字节）");

    // NOTFOUND: 错误码 + 错误消息
    let k_miss = CString::new("missing").expect("无 NUL");
    let rc = unsafe {
        kvdb_get(db, k_miss.as_ptr(), buf.as_mut_ptr() as *mut c_void,
                 buf.len() as c_uint, &mut vlen)
    };
    assert_eq!(rc, KVDB_ERR_NOTFOUND);
    println!("rs: get missing -> rc={} msg={}", rc, err_str(rc));

    // BADARG: 空 key → -1 + 错误消息
    let k_empty = CString::new("").expect("空串不含 NUL");
    let rc_bad = unsafe {
        kvdb_put(db, k_empty.as_ptr(), buf.as_mut_ptr() as *const c_void, 1)
    };
    assert_eq!(rc_bad, KVDB_ERR_BADARG);
    println!("rs: put(空 key) -> rc={} msg={}", rc_bad, err_str(rc_bad));

    // sync → destroy → 重开: WAL 回放验证持久化
    assert_eq!(unsafe { kvdb_sync(db) }, KVDB_OK);
    assert_eq!(unsafe { kvdb_destroy(db) }, KVDB_OK);
    let db2 = unsafe { kvdb_create(path.as_ptr(), &mut err) };
    assert!(!db2.is_null(), "重开失败: {}", err_str(err));
    let mut vlen3: c_uint = 0;
    assert_eq!(unsafe {
        kvdb_get(db2, k_greet.as_ptr(), buf.as_mut_ptr() as *mut c_void,
                 buf.len() as c_uint, &mut vlen3)
    }, KVDB_OK);
    let text3 = std::str::from_utf8(&buf[..vlen3 as usize]).expect("UTF-8");
    assert_eq!(text3, "hello world");
    println!("rs: 重开库后 get(greeting) 仍命中 —— WAL 回放持久化验证通过");
    assert_eq!(unsafe { kvdb_destroy(db2) }, KVDB_OK);
    println!("rs-kvdb: 全部断言通过");
}

// 实测输出（本机一次运行）：
// rs: kvdb_create ok（新建 WAL）
// rs: get greeting -> "hello world" (len=11)
// rs: get blob -> 二进制往返一致（含 \0 字节）
// rs: get missing -> rc=-5 msg=key not found
// rs: put(空 key) -> rc=-1 msg=invalid argument
// rs: 重开库后 get(greeting) 仍命中 —— WAL 回放持久化验证通过
// rs-kvdb: 全部断言通过
