"""pytest 全局配置：让测试不依赖开发者本地 `.env`。

Background
----------
``Settings`` 会按 ``.env`` → ``.env.local`` → 进程环境变量的顺序加载配置，因此开发者本地
把 ``HMAC_REQUIRE_HTTPS`` 改成 ``false``（本地 HTTP 联调需要）时，认证相关用例会因为读到
这份本地配置而失败。测试需要的是**确定性**，不是"本机当前配置"。

本文件在测试进程启动前固定一组与安全分支相关的环境变量；由于进程环境变量优先级高于
``.env`` 文件，用例因此得到稳定输入。需要验证其它取值的用例应当显式构造
``Settings(...)``（必要时传 ``_env_file=None``），不要依赖本文件的默认值。

另外提供逐用例硬超时：回归时若某个用例挂死，应当快速失败而不是卡住整个 CI。
不引入额外依赖，使用 POSIX ``SIGALRM``；Windows 上自动跳过该保护。
"""

import os
import signal

import pytest

# ---------------------------------------------------------------------------
# 确定性环境：必须在任何 Settings 实例化之前执行。
# ---------------------------------------------------------------------------
os.environ.setdefault("HMAC_REQUIRE_HTTPS", "true")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("PUBLIC_MODE", "false")
os.environ.setdefault("CHECKPOINT_BACKEND", "memory")


@pytest.fixture(autouse=True)
def enforce_test_timeout():
    """给每个用例加硬超时，避免回归时挂死整个 CI。

    ``asyncio.run`` 包裹的异步用例同样会被中断（信号在主线程抛出）。
    默认 60 秒，可用 ``PYTEST_TEST_TIMEOUT`` 覆盖。
    """
    if not hasattr(signal, "SIGALRM"):  # pragma: no cover - Windows
        yield
        return
    timeout = float(os.environ.get("PYTEST_TEST_TIMEOUT", "60"))

    def _raise(signum, frame):
        """抛出超时异常，让用例失败而不是挂起。"""
        raise TimeoutError(f"test exceeded {timeout:.0f}s")

    previous = signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
