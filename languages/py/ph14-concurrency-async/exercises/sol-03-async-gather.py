#!/usr/bin/env python3
# exercises/sol-03-async-gather.py —— 练习 3 参考实现：异步并发请求 API + 事件循环阻塞反例
# 验证环境：Python 3.13.9（macOS arm64，标准库，零第三方依赖）
# 运行：python3 sol-03-async-gather.py（离线可跑，已验证）
# 验证状态：已验证 —— 本机实测：串行 await ≈ 1.02s，gather 并发 ≈ 0.05s（约 20 倍）；
#           time.sleep 反例 ≈ 1.08s（并发被抹平）（数字随机器与负载波动 ±10~20%）
# 验证块数字实测：串行 1.019s / gather 0.051s（≈ 20 倍）/ 反例 1.069s；return_exceptions 9/10
import asyncio
import time

N_REQ = 20
API_DELAY = 0.05  # 模拟每个 API 的响应耗时


async def fetch_api(i: int) -> dict:
    """模拟异步请求第 i 个 API：await 让出事件循环，返回 JSON 结构。"""
    await asyncio.sleep(API_DELAY)
    return {"id": i, "data": f"payload-{i}"}


async def fetch_api_blocked(i: int) -> dict:
    """错误示范：协程里用 time.sleep —— 阻塞整个事件循环，并发失效。"""
    time.sleep(API_DELAY)
    return {"id": i, "data": f"payload-{i}"}


async def main() -> None:
    print(f"== 异步请求 API 模拟：{N_REQ} 个请求 × {API_DELAY}s ==")

    t0 = time.perf_counter()
    serial = [await fetch_api(i) for i in range(N_REQ)]
    t_serial = time.perf_counter() - t0
    print(f"串行 await: {t_serial:.3f}s 拿到 {len(serial)} 个响应")

    t0 = time.perf_counter()
    conc = await asyncio.gather(*(fetch_api(i) for i in range(N_REQ)))
    t_conc = time.perf_counter() - t0
    print(f"gather 并发: {t_conc:.3f}s（≈ {t_serial / t_conc:.0f} 倍加速）")

    t0 = time.perf_counter()
    blocked = await asyncio.gather(*(fetch_api_blocked(i) for i in range(N_REQ)))
    t_blocked = time.perf_counter() - t0
    print(f"time.sleep 反例: {t_blocked:.3f}s（阻塞调用把并发抹平，退回串行）")

    # 异常处理：单个请求失败不应拖垮整批
    async def maybe_fail(i: int) -> dict:
        if i == 5:
            raise TimeoutError(f"id={i} 超时")
        return {"id": i}

    rs = await asyncio.gather(
        *(maybe_fail(i) for i in range(10)), return_exceptions=True
    )
    ok_cnt = sum(1 for r in rs if isinstance(r, dict))
    err_types = [type(r).__name__ for r in rs if not isinstance(r, dict)]
    print(f"return_exceptions=True: {ok_cnt}/10 成功，异常对象: {err_types}")

    # 正确性校验：并发结果与串行一致；反例数量一致
    assert serial == conc, "并发结果与串行不一致！"
    assert len(blocked) == N_REQ
    assert ok_cnt == 9
    print("结果校验: 并发/串行结果一致、异常按预期返回 ✓")


if __name__ == "__main__":
    asyncio.run(main())
