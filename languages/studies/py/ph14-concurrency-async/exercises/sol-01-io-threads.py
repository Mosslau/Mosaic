#!/usr/bin/env python3
# exercises/sol-01-io-threads.py —— 练习 1 参考实现：并发下载文件（threading IO 密集）
# 验证环境：Python 3.13.9（macOS arm64，标准库，零第三方依赖）
# 运行：python3 sol-01-io-threads.py（离线可跑，已验证）
# 验证状态：已验证 —— 本机实测：串行下载 ≈ 1.07s，线程池(4) 并发 ≈ 0.27s（约 4 倍）
#           （数字随机器与负载波动 ±10~20%）
# 验证块数字实测：串行 1.070s / 线程池(4) 0.274s（≈ 3.9 倍）；20 个文件、总字节 215,040
import time
from concurrent.futures import ThreadPoolExecutor

N_FILES = 20
DL_TIME = 0.05  # 模拟每个文件的下载耗时（网络等待，线程等待时释放 GIL）


def download_file(i: int) -> dict:
    """模拟下载第 i 个文件：等待 DL_TIME 后返回文件元信息。"""
    time.sleep(DL_TIME)
    return {"id": i, "size": 1024 * (i + 1)}


def main() -> None:
    print(f"== 并发下载模拟：{N_FILES} 个文件 × {DL_TIME}s ==")

    t0 = time.perf_counter()
    serial = [download_file(i) for i in range(N_FILES)]
    t_serial = time.perf_counter() - t0
    print(f"串行下载: {t_serial:.3f}s 拿到 {len(serial)} 个文件")

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as ex:  # 4 个 worker 同时下载
        pooled = list(ex.map(download_file, range(N_FILES)))
    t_pool = time.perf_counter() - t0
    print(f"线程池(4) 并发下载: {t_pool:.3f}s（≈ {t_serial / t_pool:.1f} 倍加速）")

    # 正确性校验：并发结果必须与串行完全一致（一个都不能丢、不能错）
    assert serial == pooled, "并发结果与串行不一致！"
    total = sum(f["size"] for f in pooled)
    print(f"结果校验: 文件数 {len(pooled)}，总字节 {total:,}，串行/并发一致 ✓")


if __name__ == "__main__":
    main()
