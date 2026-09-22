"""sol-03 冒烟测试：import Rust 扩展 sol03_fastwords，对照纯 Python 验证。

验证环境：Python 3.13.12（与编译 pyo3 时相同的解释器）。
运行命令（在 sol-03-pyo3-extension/ 下，先完成 cargo build）：
  export PATH="$HOME/.cargo/bin:$PATH"
  export CARGO_TARGET_DIR=/tmp/ph23-sol03-target
  export RUSTFLAGS="-C link-arg=-Wl,-undefined,dynamic_lookup"
  cargo build --release
  PY=/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3
  cp /tmp/ph23-sol03-target/release/libsol03_fastwords.dylib ./sol03_fastwords.so
  $PY -B smoke_test.py
  rm -f sol03_fastwords.so
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sol03_fastwords as fw


def main() -> int:
    fail = 0

    # count_words 与 text.split() 对照
    text = "  rust  ffi pyo3  跨语言  边界  "
    assert fw.count_words(text) == len(text.split()), "count_words vs split"

    # 空/全空白：返回 0，不 panic、不抛异常
    for empty in ("", "   \n\t ", "    "):
        assert fw.count_words(empty) == 0, f"empty case {empty!r}"

    # top_k_words：频次降序、平局字典序
    sample = "b a a c b a d d e"  # a×3, b×2, d×2, c×1, e×1
    got = fw.top_k_words(sample, 3)
    expect = [("a", 3), ("b", 2), ("d", 2)]
    assert got == expect, f"top3 mismatch: {got}"
    got_all = fw.top_k_words(sample, 10)
    assert got_all == [("a", 3), ("b", 2), ("d", 2), ("c", 1), ("e", 1)], got_all

    # k=0 → 空列表；类型为 list[tuple[str,int]]
    assert fw.top_k_words(sample, 0) == []
    assert isinstance(fw.top_k_words(sample, 1)[0], tuple)

    print("ALL OK")
    return fail


if __name__ == "__main__":
    sys.exit(main())
