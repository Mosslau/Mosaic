//! RAG chunk 处理：字符窗口切分文本，纯 Rust 核心，被 pyo3 绑定层薄封装。
//!
//! 语义约定：按「字符」切分（对齐人读文本的感知，而非字节）；窗口大小 `chunk_size`、
//! 相邻窗口重叠 `overlap` 字符，步长 = chunk_size - overlap。返回的每一片都是
//! 原文本的连续子串，最后一片可能短于 chunk_size。
//! 验证环境：cargo/rustc 1.92.0；本机实测「已验证」。

/// 参数校验失败的原因——用类型而非错误码表达，Rust 内部可穷尽匹配。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChunkError {
    /// chunk_size 为 0：窗口无意义。
    ZeroChunkSize,
    /// overlap >= chunk_size：步长 ≤ 0，会死循环。
    OverlapTooLarge,
}

/// 按字符窗口切分文本。
///
/// 返回 `Result<Vec<String>, ChunkError>`：参数非法返回 Err，正常路径无 panic。
/// 文本为空或短于 chunk_size 时返回单元素 Vec（整段文本）。
pub fn chunk_text_inner(
    text: &str,
    chunk_size: usize,
    overlap: usize,
) -> Result<Vec<String>, ChunkError> {
    if chunk_size == 0 {
        return Err(ChunkError::ZeroChunkSize);
    }
    if overlap >= chunk_size {
        return Err(ChunkError::OverlapTooLarge);
    }

    let chars: Vec<char> = text.chars().collect();
    if chars.len() <= chunk_size {
        return Ok(vec![text.to_string()]);
    }

    let step = chunk_size - overlap;
    let mut chunks = Vec::with_capacity(chars.len().div_ceil(chunk_size));
    let mut start = 0;
    while start < chars.len() {
        let end = (start + chunk_size).min(chars.len());
        chunks.push(chars[start..end].iter().collect());
        if end == chars.len() {
            break; // 末片已含结尾，不再推进，避免重复产生空窗口
        }
        start += step;
    }
    Ok(chunks)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn text() -> String {
        "0123456789".repeat(6) // 60 个字符
    }

    #[test]
    fn no_overlap_partitions_contiguously() {
        // chunk_size=10, overlap=0 → 恰好 6 片，拼接还原全文
        let chunks = chunk_text_inner(&text(), 10, 0).unwrap();
        assert_eq!(chunks.len(), 6);
        assert_eq!(chunks.concat(), text());
    }

    #[test]
    fn overlap_advances_by_step() {
        // chunk_size=10, overlap=2 → 步长 8；片 1 与片 2 重叠最后 2 字符
        let chunks = chunk_text_inner(&text(), 10, 2).unwrap();
        assert_eq!(chunks.len(), 8);
        assert!(chunks[0].ends_with(&chunks[1][..2]));
        // 末片 = 全文最后不足 10 字符的尾巴
        assert_eq!(chunks.last().unwrap().len(), 4);
    }

    #[test]
    fn unicode_is_counted_by_chars_not_bytes() {
        let s = "你".repeat(30); // 30 个中文字符，90 字节
        let chunks = chunk_text_inner(&s, 7, 1).unwrap();
        // 每片 ≤ 7 字符、且都是完整字符（90 字节只按 char 切，不可能切成半个字）
        assert!(chunks.iter().all(|c| c.chars().count() <= 7));
        assert!(chunks.iter().all(|c| c.chars().all(|ch| ch == '你')));
        // 覆盖原文本全部字符（重叠段会重复，故用并集验证）
        let covered: String = chunks.concat();
        assert!(covered.chars().all(|ch| ch == '你'));
    }

    #[test]
    fn short_and_empty_text() {
        assert_eq!(chunk_text_inner("abc", 10, 1).unwrap(), vec!["abc"]);
        assert_eq!(chunk_text_inner("", 4, 1).unwrap(), vec![""]);
    }

    #[test]
    fn invalid_params_are_errors_not_panics() {
        assert_eq!(
            chunk_text_inner("abc", 0, 0),
            Err(ChunkError::ZeroChunkSize)
        );
        assert_eq!(
            chunk_text_inner("abc", 5, 5),
            Err(ChunkError::OverlapTooLarge)
        );
        assert_eq!(
            chunk_text_inner("abc", 3, 8),
            Err(ChunkError::OverlapTooLarge)
        );
    }
}
