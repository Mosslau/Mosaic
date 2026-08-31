# exercises/sol-04-redis-cache.py —— 练习 4 参考实现：Redis 缓存查询结果（缓存旁路 + TTL + 失效）
# 验证环境：Python 3.13.9，redis-py 8.0.1 + redis-server 8.x（本机已装）
# 运行：python3 sol-04-redis-cache.py（离线可跑，已验证；server 起在临时目录+随机端口，结束时干净关闭）
# 验证状态：已验证 —— 实测输出（本机 Python 3.13.9 + redis-server 8.x 实际运行）：
#   首次读取 -> miss（305 ms）: {'name': 'device-D001', 'online': True, 'version': 'v1.0'}
#   二次读取 -> hit（0.1 ms）: 同上
#   更新 D001 -> {'online': False, 'version': 'v1.1'}，缓存已删除；失效后读取 -> miss（305 ms）
#   等待 TTL=2s 过期……；过期后读取 -> miss（305 ms）
#   汇总: miss 约 305 ms vs hit 约 0.1 ms（缓存快约 3000 倍量级）
#   脚本结束打印「redis-server 已关闭，临时目录已回收」
import json
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import redis

TTL = 2  # 缓存有效期（秒）

# 内存「数据库」：真实项目里是 sqlite/postgres 表
DB: dict[str, dict] = {
    "D001": {"name": "device-D001", "online": True, "version": "v1.0"},
    "D002": {"name": "device-D002", "online": False, "version": "v2.0"},
}


def query_device(device_id: str) -> dict:
    """模拟慢查询（0.3s）。"""
    time.sleep(0.3)
    return dict(DB[device_id])


def get_device_cached(r: redis.Redis, device_id: str) -> tuple[dict, str]:
    """缓存旁路：先查缓存，未命中查库回填并设 TTL。"""
    key = f"device:{device_id}"
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached), "hit"
    data = query_device(device_id)
    r.set(key, json.dumps(data), ex=TTL)
    return data, "miss"


def update_device(r: redis.Redis, device_id: str, **fields) -> None:
    """写库后主动删缓存（失效策略）：下次读取必然 miss 重新查库，防脏读。"""
    DB[device_id].update(fields)
    r.delete(f"device:{device_id}")  # 主动失效
    print(f"更新 {device_id} -> {fields}，缓存已删除")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_ready(client: redis.Redis, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if client.ping():
                return
        except redis.ConnectionError:
            time.sleep(0.05)
    raise RuntimeError("redis-server 启动超时")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ph11-sol04-"))
    port = free_port()
    proc = subprocess.Popen(
        ["redis-server", "--port", str(port), "--save", "", "--appendonly", "no",
         "--dir", str(tmp), "--daemonize", "no"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        r = redis.Redis(host="127.0.0.1", port=port, decode_responses=True)
        wait_ready(r)

        # 1. 命中与未命中：首次 miss（查库 0.3s），第二次 hit（毫秒级）
        t0 = time.perf_counter()
        data, tag = get_device_cached(r, "D001")
        t_miss = time.perf_counter() - t0
        print(f"首次读取 -> {tag}（{t_miss * 1000:.0f} ms）: {data}")

        t0 = time.perf_counter()
        data, tag = get_device_cached(r, "D001")
        t_hit = time.perf_counter() - t0
        print(f"二次读取 -> {tag}（{t_hit * 1000:.1f} ms）: {data}")

        # 2. 写库主动失效：更新后缓存被删，下次必然 miss（防脏读）
        update_device(r, "D001", online=False, version="v1.1")
        t0 = time.perf_counter()
        data, tag = get_device_cached(r, "D001")
        print(f"失效后读取 -> {tag}（{(time.perf_counter() - t0) * 1000:.0f} ms）: {data}")

        # 3. TTL 过期：等缓存自然过期后再次 miss
        print(f"等待 TTL={TTL}s 过期……")
        time.sleep(TTL + 0.3)
        t0 = time.perf_counter()
        data, tag = get_device_cached(r, "D001")
        print(f"过期后读取 -> {tag}（{(time.perf_counter() - t0) * 1000:.0f} ms）: {data}")

        print(f"汇总: miss 约 {t_miss * 1000:.0f} ms vs hit 约 {t_hit * 1000:.1f} ms"
              f"（缓存快约 {t_miss / t_hit:.0f} 倍）")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        shutil.rmtree(tmp, ignore_errors=True)
        print("redis-server 已关闭，临时目录已回收")


if __name__ == "__main__":
    main()
