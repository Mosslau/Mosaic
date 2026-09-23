# exercises/sol-03-device-json.py —— 练习 3 参考实现：读取 JSON（设备配置 round-trip + 自定义异常）
# 来源：05-file-exception.md 第 7 章「动手练习」练习 3
# 验证环境：Python 3.13.12
# 运行：python3 sol-03-device-json.py
# 验证状态：已验证

"""设备配置 JSON round-trip：读入、修改、写回、重读验证；失败时 raise from 保留根因。"""

import json
import os
import tempfile


class DeviceConfigError(Exception):
    """设备配置异常：文件缺失或 JSON 格式错误时抛出。"""


def load_device(path):
    """读取设备配置 JSON，失败时抛出 DeviceConfigError 并保留根因。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise DeviceConfigError(f"配置文件不存在: {path}") from e
    except json.JSONDecodeError as e:
        raise DeviceConfigError(f"JSON 格式错误: {path}") from e


def main():
    """演示 round-trip：读入 -> 追加 soc_pct -> 写回 -> 重读验证。"""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "device.json")
        device = {
            "device_id": "LSVAU2A28N2100001",
            "component": {"capacity_kwh": 70.0},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(device, f, indent=2, ensure_ascii=False)

        try:
            data = load_device(path)
            data["component"]["soc_pct"] = 85.0
            out_path = os.path.join(d, "device_updated.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            reloaded = load_device(out_path)
            print(f"round-trip 成功: soc={reloaded['component']['soc_pct']}%")
        except DeviceConfigError as e:
            print(f"配置加载失败: {e} (根因: {e.__cause__})")


if __name__ == "__main__":
    main()
