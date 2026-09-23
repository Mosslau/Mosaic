# examples/ex01-read-config.py —— 读取设备配置文件：手动解析 INI 格式并演示四段式异常处理
# 来源：05-file-exception.md 第 6 章示例 1
# 验证环境：Python 3.13.12
# 运行：python3 ex01-read-config.py
# 验证状态：已验证

"""手动解析 INI 风格配置文件，演示 open 模式、with 与 try/except/else/finally 的配合。"""

import os
import tempfile


def parse_config(path):
    """解析 [section] key = value 风格的配置文件，返回 {section: {key: value}}。"""
    config, section = {}, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1]
                    config[section] = {}
                elif "=" in line and section is not None:
                    key, value = line.split("=", 1)
                    config[section][key.strip()] = value.strip()
    except FileNotFoundError:
        print("错误: 文件不存在")
    except PermissionError:
        print("错误: 无权限读取")
    else:
        # 仅在 try 无异常时执行 —— 适合放"依赖读取成功"的逻辑
        print(f"配置解析成功: {config}")
        return config
    return None


def main():
    """在临时目录生成设备平台配置并解析，随后演示文件不存在分支。"""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "app.cfg")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# 设备平台配置\n[server]\nhost = 0.0.0.0\nport = 8080\n")
            f.write("[component]\nchemistry = LFP\ncapacity_kwh = 70.0\n")

        parse_config(path)
        parse_config(os.path.join(d, "missing.cfg"))  # 触发 FileNotFoundError 分支


if __name__ == "__main__":
    main()
