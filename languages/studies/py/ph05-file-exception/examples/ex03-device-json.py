# examples/ex03-device-json.py —— 设备配置 JSON 读写：dump/load round-trip
# 来源：05-file-exception.md 第 6 章示例 3
# 验证环境：Python 3.13.12
# 运行：python3 ex03-device-json.py
# 验证状态：已验证

"""JSON 读写 round-trip：indent 可读写入、ensure_ascii=False 保留中文。"""

import json
import os
import tempfile


def load_device(path):
    """读取 JSON 设备配置，解析失败返回 None。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("JSON 文件不存在")
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
    except KeyError as e:
        print(f"缺少字段: {e}")
    return None


def main():
    """写入设备配置 JSON，round-trip 读回后追加 SOC 字段并再次落盘。"""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "device.json")
        device = {
            "device_id": "LSVAU2A28N2100001",
            "model": "Model-Y",
            "component": {"capacity_kwh": 70.0, "nominal_voltage_v": 400},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(device, f, indent=2, ensure_ascii=False)

        data = load_device(path)
        if data is None:
            return
        print(f"DEVICE_ID={data['device_id']} 容量={data['component']['capacity_kwh']}kWh")
        data["component"]["soc_pct"] = 85.0
        out_path = os.path.join(d, "device_updated.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        reloaded = load_device(out_path)
        if reloaded is not None:
            print(f"round-trip 成功: soc={reloaded['component']['soc_pct']}%")


if __name__ == "__main__":
    main()
