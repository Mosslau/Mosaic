# project/txtool/__main__.py —— 包入口，支持 python3 -m txtool
# 验证环境：Python 3.13.12
# 运行：在 project/ 目录下执行 python3 -m txtool <子命令> ...
# 已验证：本环境 wc/grep/head/tail 子命令及 --help 均验证通过

import sys

from txtool.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
