# exercises/sol-01-config-parser.py —— 练习 1 参考实现：读配置文件（INI 手动解析，容错非法行）
# 来源：05-file-exception.md 第 7 章「动手练习」练习 1
# 验证环境：Python 3.13.12
# 运行：python3 sol-01-config-parser.py
# 验证状态：已验证

"""解析 INI 风格配置文件：支持注释/空行/小节/键值对，非法行打印行号并跳过。"""

import os
import tempfile


def parse_config(path):
    """解析配置文件，返回 {section: {key: value}}；非法行打印行号并跳过。"""
    config, section = {}, None
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                config[section] = {}
            elif "=" in line:
                if section is None:
                    print(f"第 {lineno} 行: 键值对出现在 [section] 之前, 已跳过")
                    continue
                key, value = line.split("=", 1)
                config[section][key.strip()] = value.strip()
            else:
                print(f"第 {lineno} 行: 无法识别的行 - {line!r}, 已跳过")
    return config


def main():
    """用临时配置文件演示解析，文件内故意含一条非法行。"""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "app.cfg")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# 设备平台配置\n")
            f.write("[server]\n")
            f.write("host = 0.0.0.0\n")
            f.write("port = 8080\n")
            f.write("this is a bad line\n")  # 非法行 -> 报行号并跳过
            f.write("[component]\n")
            f.write("chemistry = LFP\n")

        config = parse_config(path)
        print(f"解析结果: {config}")


if __name__ == "__main__":
    main()
