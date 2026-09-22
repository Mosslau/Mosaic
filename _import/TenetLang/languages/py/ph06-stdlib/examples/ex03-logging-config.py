# examples/ex03-logging-config.py —— logging 配置与模块化日志（控制台全级别 + 文件回滚）
# 来源：06-stdlib.md 第 6 章示例 3
# 验证环境：Python 3.13.12
# 运行：python3 ex03-logging-config.py
# 验证状态：已验证

"""演示模块化 logger：控制台输出全部级别，文件 RotatingFileHandler 只留 INFO 以上、超 1KB 回滚。"""

import logging
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(log_file: Path) -> logging.Logger:
    """构造模块化 logger：控制台 DEBUG+、文件 INFO+（RotatingFileHandler 超 1KB 回滚）。"""
    logger = logging.getLogger("batch_tool")     # 模块化 logger，而非 root
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()            # 控制台：全部级别
    console.setLevel(logging.DEBUG)
    console.setFormatter(fmt)
    rotate = RotatingFileHandler(                # 文件：INFO 以上，超 1KB 回滚
        log_file, maxBytes=1024, backupCount=2, encoding="utf-8",
    )
    rotate.setLevel(logging.INFO)
    rotate.setFormatter(fmt)
    logger.addHandler(console)
    logger.addHandler(rotate)
    return logger


def main() -> None:
    """在临时目录演示分级日志与文件回滚，最后打印回滚文件数。"""
    with tempfile.TemporaryDirectory() as d:
        logger = setup_logger(Path(d) / "tool.log")
        logger.debug("调试细节（仅控制台可见）")
        logger.info("任务开始")
        for i in range(50):
            logger.warning(f"第 {i} 条告警")
        logger.error("处理失败")
        print("回滚文件数:", len(list(Path(d).glob("tool.log*"))))


if __name__ == "__main__":
    main()
