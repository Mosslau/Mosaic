// examples/ex02-raw-pointers.rs —— 裸指针：创建 / 判空 / 解引用 / 转换 / 运算 / 读写
// 验证环境：rustc 1.92.0（macOS arm64），零第三方依赖
// 编译：rustc --edition 2021 -D warnings ex02-raw-pointers.rs -o /tmp/ex02
// 运行：/tmp/ex02
// 验证状态：已验证（编译零警告；7 段输出为实测）

use std::ptr;

fn main() {
    // 1. 创建裸指针（安全操作）+ 解引用（unsafe 操作）
    let mut x = 42i32;
    let p: *mut i32 = &mut x; // &mut T as *mut T：可写裸指针
    let r: *const i32 = &x; // &T as *const T：只读裸指针
    assert!(!p.is_null() && !r.is_null());
    unsafe {
        *p += 1;
        assert_eq!(*r, 43);
    }
    println!("1. 创建/解引用 OK: x = {x}");

    // 2. 空指针与 is_null
    let n: *const i32 = ptr::null();
    let nm: *mut i32 = ptr::null_mut();
    assert!(n.is_null() && nm.is_null());
    println!("2. null 指针 OK");

    // 3. as 类型转换：*const T → *const U（位不变，解释方式变）
    let u8ptr: *const u8 = r as *const u8;
    let b = unsafe { *u8ptr };
    println!("3. 类型转换: x 首字节 = {b:#04X}");

    // 4. addr_of! / addr_of_mut!：不经过引用的取址（避免创建临时引用）
    let a = ptr::addr_of!(x);
    let am = ptr::addr_of_mut!(x);
    unsafe {
        *am = 100;
    }
    assert_eq!(unsafe { *a }, 100);
    println!("4. addr_of!/addr_of_mut! OK");

    // 5. 指针运算：add / offset / offset_from（步长按元素大小，不是字节）
    let arr = [10i32, 20, 30, 40];
    let base = arr.as_ptr();
    let p1 = unsafe { base.add(1) }; // +1 个 i32（4 字节）
    let p3 = unsafe { base.offset(3) };
    assert_eq!(unsafe { *p1 }, 20);
    assert_eq!(unsafe { *p3 }, 40);
    let diff = unsafe { p3.offset_from(base) };
    assert_eq!(diff, 3);
    println!("5. add/offset/offset_from OK: diff = {diff}");

    // 6. read / write：显式读写指针指向的值
    let mut buf = [0u8; 4];
    let bp = buf.as_mut_ptr();
    unsafe {
        bp.write(7);
        bp.add(1).write(8);
        assert_eq!(buf[0], 7);
        assert_eq!(buf[1], 8);
        let v = bp.read();
        assert_eq!(v, 7);
    }
    println!("6. read/write OK");

    // 7. 指针比较：同一分配内的指针可比大小（跨分配比较是未定义行为）
    let p2 = unsafe { base.add(2) };
    assert!(p2 > p1 && p1 < p3);
    assert!(base <= p3);
    println!("7. 指针比较 OK");

    // 认知小结：
    // - 创建裸指针是安全的，解引用/运算读写的合法性由开发者保证（不变量由开发者维护）
    // - 裸指针没有所有权语义：不自动释放、不参与借用检查、不保证指向有效数据
    // - 越界 offset / 解引用悬垂指针 / 跨分配比较都是 UB（演示见 ex03）
}
