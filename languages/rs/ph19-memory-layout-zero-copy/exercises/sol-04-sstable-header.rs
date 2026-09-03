// exercises/sol-04-sstable-header.rs —— 练习 4 参考实现：解析 SSTable block header
// 对应 roadmap 第 19 节练习「解析 SSTable block header」与主文档 3.8（含正文内联片段）。
// 教学简化 SST 文件布局：
//   [magic: "SST1" 4B][count: u32 LE][count × BlockHandle(offset: u32 LE, size: u32 LE)]…数据块区
//   BlockHandle 描述一块数据块的 [offset, offset+size)，可直接在文件缓冲上切零拷贝视图。
// 安全要点（正文片段强调的「双闸门」）：offset+size 先查溢出（checked_add），
// 再整体落在文件长度内（file.get），之后才借用。恶意句柄值在两道闸上被拒。
// 验证环境：rustc/cargo 1.92.0（macOS arm64）。编译/运行/测试：
//   rustc --edition 2021 -D warnings sol-04-sstable-header.rs -o /tmp/ph19-sol04 && /tmp/ph19-sol04
//   rustc --edition 2021 -D warnings --test sol-04-sstable-header.rs -o /tmp/ph19-sol04-t && /tmp/ph19-sol04-t
// 验证状态：已验证（rustc 1.92.0，aarch64-apple-darwin）。
use std::fmt;

const MAGIC: u32 = 0x3154_5353; // "SST1"
const HANDLE_LEN: usize = 8; // offset u32 LE + size u32 LE

#[derive(Debug, PartialEq, Eq)]
struct BlockHandle<'a> {
    offset: u32,
    size: u32,
    /// 数据块的零拷贝视图：直接指向文件缓冲 [offset, offset+size)
    block: &'a [u8],
}

/// 在 handle_pos 处读一个 BlockHandle 并切出块视图。
/// 与主文档 3.8 正文片段逐行对应（SstErr::Truncated / SstErr::TooBig 语义一致）。
fn parse_block_handle<'a>(file: &'a [u8], handle_pos: usize) -> Result<BlockHandle<'a>, SstErr> {
    let head = file.get(handle_pos..handle_pos + HANDLE_LEN).ok_or(SstErr::Truncated)?;
    let offset = u32::from_le_bytes(head[0..4].try_into().map_err(|_| SstErr::Truncated)?) as usize;
    let size = u32::from_le_bytes(head[4..8].try_into().map_err(|_| SstErr::Truncated)?) as usize;
    // 双闸门：① offset + size 不能溢出 usize；② 整体必须落在文件内
    let end = offset.checked_add(size).ok_or(SstErr::TooBig)?;
    let block = file.get(offset..end).ok_or(SstErr::Truncated)?;
    Ok(BlockHandle { offset: offset as u32, size: size as u32, block })
}

/// 读文件头 + 索引区，返回 N 个 handle 的（起始 handle_pos）列表，供 parse_block_handle 使用。
fn parse_index(file: &[u8]) -> Result<Vec<usize>, SstErr> {
    let head = file.get(..8).ok_or(SstErr::Truncated)?;
    let magic = u32::from_le_bytes(head[0..4].try_into().map_err(|_| SstErr::Truncated)?);
    if magic != MAGIC {
        return Err(SstErr::BadMagic(magic));
    }
    let count = u32::from_le_bytes(head[4..8].try_into().map_err(|_| SstErr::Truncated)?) as usize;
    // 索引区 [8, 8 + count*8) 必须完整存在，否则句柄数就是谎言
    let _idx = file.get(8..8 + count.checked_mul(HANDLE_LEN).ok_or(SstErr::TooBig)?).ok_or(SstErr::Truncated)?;
    Ok((0..count).map(|i| 8 + i * HANDLE_LEN).collect())
}

#[derive(Debug, PartialEq, Eq)]
enum SstErr {
    BadMagic(u32),
    Truncated,
    TooBig,
}

impl fmt::Display for SstErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SstErr::BadMagic(m) => write!(f, "魔数错误 0x{m:08X}（不是 SST1）"),
            SstErr::Truncated => write!(f, "截断：句柄/索引区/数据块超出文件长度"),
            SstErr::TooBig => write!(f, "长度或偏移溢出/超上限（拒绝）"),
        }
    }
}

/// 教学编码器：按句柄顺序写入数据块并生成文件头 + 索引区。
fn build_sst(blocks: &[&[u8]]) -> Vec<u8> {
    let mut out = Vec::new();
    out.extend_from_slice(&MAGIC.to_le_bytes());
    out.extend_from_slice(&(blocks.len() as u32).to_le_bytes());
    let mut offset = 8 + blocks.len() * HANDLE_LEN; // 数据块区紧随索引区
    for b in blocks {
        out.extend_from_slice(&(offset as u32).to_le_bytes());
        out.extend_from_slice(&(b.len() as u32).to_le_bytes());
        offset += b.len();
    }
    for b in blocks {
        out.extend_from_slice(b);
    }
    out
}

fn main() {
    // —— 1. 建 SST：两个数据块，读索引并逐个切零拷贝块视图 ——
    println!("== 解析 SST 索引并读取块 ==");
    let block_a: Vec<u8> = (1u8..=4).collect(); // [1,2,3,4]
    let block_b: Vec<u8> = (9u8..=12).collect(); // [9,10,11,12]
    let file = build_sst(&[&block_a, &block_b]);
    println!("SST 共 {} 字节（头 8B + 索引 16B + 数据块 8B）", file.len());

    let handles = parse_index(&file).expect("合法 SST");
    for (i, pos) in handles.iter().enumerate() {
        let h = parse_block_handle(&file, *pos).expect("句柄可读");
        let view_off = h.block.as_ptr() as usize - file.as_ptr() as usize;
        println!("块 {i}: offset={} size={} 内容={:?}（视图偏移 {view_off} → 零拷贝直指文件缓冲）", h.offset, h.size, h.block);
    }

    // —— 2. 双闸门验证：伪造越界/溢出句柄 ——
    println!();
    println!("== 恶意句柄被双闸门拦下 ==");
    let mut evil = file.clone();
    let idx_pos = 8 + 0 * HANDLE_LEN;
    // 把块 0 的 offset 改成 0xFFFF_FFFF，size 也巨大 → offset+size 溢出 usize？在 32B 文件里先被 checked_add/边界拦
    evil[idx_pos..idx_pos + 4].copy_from_slice(&0xFFFF_FFF0u32.to_le_bytes());
    evil[idx_pos + 4..idx_pos + 8].copy_from_slice(&0x0000_0010u32.to_le_bytes());
    match parse_block_handle(&evil, idx_pos) {
        Ok(_) => println!("意外通过"),
        Err(e) => println!("越界句柄 → {e}"),
    }
    let mut evil2 = file.clone();
    // offset=24 保持、size=0x7FFF_FFFF：64 位 usize 上相加不溢出（checked_add 通过），
    // 但 24+0x7FFF_FFFF 远超文件长度 → 由 file.get 的边界检查兜住 → Truncated。
    // （checked_add 的真正价值在 32 位目标与「防任意大数字」；两道闸互补，缺一不可。）
    evil2[idx_pos + 4..idx_pos + 8].copy_from_slice(&0x7FFF_FFFFu32.to_le_bytes());
    match parse_block_handle(&evil2, idx_pos) {
        Ok(_) => println!("意外通过"),
        Err(e) => println!("巨大 size 句柄 → {e}"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn index_lists_all_blocks() {
        let file = build_sst(&[b"a", b"bc", b"def"]);
        let handles = parse_index(&file).expect("合法");
        assert_eq!(handles.len(), 3);
    }

    #[test]
    fn block_views_are_borrowed_slices() {
        let file = build_sst(&[&[1, 2, 3, 4], &[9, 10, 11, 12]]);
        let handles = parse_index(&file).expect("合法");
        for (i, pos) in handles.iter().enumerate() {
            let h = parse_block_handle(&file, *pos).expect("可读");
            // 视图应指向文件内部，而非复制：首块视图偏移就是文件里数据块区的起点
            let off = h.block.as_ptr() as usize - file.as_ptr() as usize;
            assert_eq!(off, h.offset as usize);
            if i == 0 {
                assert_eq!(h.block, &[1, 2, 3, 4]);
            } else {
                assert_eq!(h.block, &[9, 10, 11, 12]);
            }
        }
    }

    #[test]
    fn bad_magic_is_err() {
        let mut file = build_sst(&[b"x"]);
        file[0] ^= 0xFF;
        assert!(matches!(parse_index(&file), Err(SstErr::BadMagic(_))));
    }

    #[test]
    fn out_of_bounds_handle_is_truncated_or_toobig() {
        let file = build_sst(&[&[1, 2, 3, 4]]);
        // handle_pos 超出文件 → Truncated
        assert_eq!(parse_block_handle(&file, file.len()).err(), Some(SstErr::Truncated));
        // offset 落在文件内但 offset+size 越界 → Truncated（不是 panic）
        let mut evil = file.clone();
        let pos = 8;
        evil[pos + 4..pos + 8].copy_from_slice(&0x7FFF_FFF0u32.to_le_bytes());
        assert!(parse_block_handle(&evil, pos).is_err());
    }

    #[test]
    fn overflow_gates_never_panic() {
        let file = build_sst(&[b"ab"]);
        let mut evil = file.clone();
        let pos = 8;
        evil[pos..pos + 4].copy_from_slice(&u32::MAX.to_le_bytes());
        evil[pos + 4..pos + 8].copy_from_slice(&u32::MAX.to_le_bytes());
        // u32::MAX + u32::MAX 在 usize 上可能溢出也可能不溢出，两条闸都要兜住，绝不 panic
        let r = std::panic::catch_unwind(|| parse_block_handle(&evil, pos));
        assert!(r.is_ok(), "解析不得 panic");
        assert!(r.unwrap().is_err());
    }
}
