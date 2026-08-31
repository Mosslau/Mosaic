# examples/ex06-redis-cache.py —— Redis 缓存：真实 redis-server 的缓存旁路（cache-aside）
# 验证环境：Python 3.13.9，redis-py 8.0.1 + redis-server 8.x（本机 /opt/homebrew/bin/redis-server）
# 运行：python3 ex06-redis-cache.py（离线可跑，已验证；server 起在临时目录+随机端口，结束时干净关闭）
# 说明：对应主文档 3.7/4.5。示例内启动一个临时 redis-server 子进程（端口随机、无持久化），
#       演示 string 读写 + TTL 过期 + 缓存旁路模式的命中/未命中耗时；脚本结束 terminate 并回收临时目录。
import json
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import redis

TTL = 1  # 缓存有效期（秒）


def free_port() -> int:
    """向系统要一个空闲端口（绑定后立刻释放，供 redis-server 使用）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_ready(client: redis.Redis, timeout: float = 5.0) -> None:
    """轮询 PING 直到 server 就绪。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if client.ping():
                return
        except redis.ConnectionError:
            time.sleep(0.05)
    raise RuntimeError("redis-server 启动超时")


def slow_query(device_id: str) -> dict:
    """模拟慢查询（真实项目里是查 SQLite/PostgreSQL）。"""
    time.sleep(0.3)
    return {"device_id": device_id, "name": f"device-{device_id}"}


def get_device(r: redis.Redis, device_id: str) -> tuple[dict, str]:
    """缓存旁路：先查缓存，未命中查库回填并设 TTL。"""
    key = f"device:{device_id}"
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached), "hit"
    data = slow_query(device_id)
    r.set(key, json.dumps(data), ex=TTL)  # 写缓存 + 过期时间（redis-py 8 推荐 set 而非 setex）
    return data, "miss"


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ph11-ex06-"))
    port = free_port()
    proc = subprocess.Popen(
        ["redis-server", "--port", str(port), "--save", "", "--appendonly", "no",
         "--dir", str(tmp), "--daemonize", "no"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        r = redis.Redis(host="127.0.0.1", port=port, decode_responses=True)
        wait_ready(r)

        # 1. string 读写 + TTL/EXPIRE
        r.set("device:1001", '{"vin":"V001"}', ex=60)
        print("SET + GET ->", r.get("device:1001"))
        print("TTL       ->", r.ttl("device:1001"), "秒（剩余）")
        r.expire("device:1001", 120)  # 动态调整过期
        print("EXPIRE 后 ->", r.ttl("device:1001"), "秒")

        # 2. 缓存旁路：miss（0.3s 慢查询）→ hit（毫秒级）→ TTL 过期后 miss
        t0 = time.perf_counter()
        data, tag = get_device(r, "D001")
        t_miss = time.perf_counter() - t0
        print(f"首次调用  -> {tag}（慢查询 {t_miss * 1000:.0f} ms）数据: {data}")

        t0 = time.perf_counter()
        data, tag = get_device(r, "D001")
        t_hit = time.perf_counter() - t0
        print(f"第二次调用-> {tag}（缓存 {t_hit * 1000:.1f} ms）数据: {data}")

        time.sleep(TTL + 0.2)  # 超过 TTL，缓存自动过期
        t0 = time.perf_counter()
        data, tag = get_device(r, "D001")
        t_expired = time.perf_counter() - t0
        print(f"TTL 过期后-> {tag}（重新查库 {t_expired * 1000:.0f} ms）数据: {data}")

        print(f"对比: miss {t_miss * 1000:.0f} ms vs hit {t_hit * 1000:.1f} ms "
              f"（缓存快 {t_miss / t_hit:.0f} 倍）")
    finally:
        proc.terminate()  # 干净关闭 server
        proc.wait(timeout=5)
        shutil.rmtree(tmp, ignore_errors=True)
        print("redis-server 已关闭，临时目录已回收")


if __name__ == "__main__":
    main()
