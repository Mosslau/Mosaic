#!/usr/bin/env python3
# project/device_manager.py —— 设备管理系统：类层次 + 继承多态 + JSON 持久化
# 来源：python.md roadmap ph04 推荐项目第一个「设备管理系统」
# 验证环境：Python 3.13.12
# 运行：python3 device_manager.py（交互式，可用管道喂命令；命令见 README）
# 验证状态：已验证

"""设备管理系统：Component 基类 + Sensor/Actuator 子类多态，Device 组合，DeviceManager 统一管理。

数据经 to_dict/from_dict 与 JSON 互转，落在脚本同目录的 devices.json（json 读写属 ph05，
此处先用最简形态：json.dump / json.load 两个 API，不展开异常处理）。
"""

import json
import os

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "devices.json")


class Component:
    """组件基类：设备编号、名称、在线状态，统一 JSON 序列化接口。"""

    def __init__(self, pid, name):
        self.pid = pid
        self.name = name
        self._status = "offline"

    @property
    def status(self):
        """在线状态（只读）。"""
        return self._status

    def online(self):
        """上线。"""
        self._status = "online"

    def to_dict(self):
        """导出为 dict，kind 字段标记具体子类，供重建时分发。"""
        return {"kind": type(self).__name__.lower(), "pid": self.pid, "name": self.name}

    @classmethod
    def from_dict(cls, data):
        """按 kind 字段重建对应子类。"""
        kind = data["kind"]
        if kind == "sensor":
            return Sensor(data["pid"], data["name"], data["unit"], data["value"])
        if kind == "actuator":
            return Actuator(data["pid"], data["name"], data["max_out"])
        raise ValueError(f"未知组件类型: {kind}")

    def __repr__(self):
        return f"{type(self).__name__}({self.pid!r}, {self.name!r})"


class Sensor(Component):
    """传感器：能读取当前测量值。"""

    def __init__(self, pid, name, unit, value=0.0):
        super().__init__(pid, name)
        self.unit = unit
        self.value = value

    def read(self):
        """读取当前测量值。"""
        return self.value

    def to_dict(self):
        data = super().to_dict()
        data.update({"unit": self.unit, "value": self.value})
        return data

    def __str__(self):
        return f"[{self.status}] {self.name}: {self.value}{self.unit}"


class Actuator(Component):
    """执行器：能按百分比控制输出。"""

    def __init__(self, pid, name, max_out):
        super().__init__(pid, name)
        self.max_out = max_out
        self._current = 0

    def control(self, pct):
        """按百分比 0~100 设置当前输出。"""
        self._current = min(pct, 100) * self.max_out / 100.0

    @property
    def current(self):
        """当前输出值。"""
        return self._current

    def to_dict(self):
        data = super().to_dict()
        data.update({"max_out": self.max_out})
        return data

    def __str__(self):
        return f"[{self.status}] {self.name}: {self._current:.0f}/{self.max_out:.0f}"


class Device:
    """设备：一组组件的容器，通过魔术方法支持 len() 与索引。"""

    def __init__(self, did, name):
        self.did = did
        self.name = name
        self.components = []

    def add(self, comp):
        """添加一个组件。"""
        self.components.append(comp)

    def __len__(self):
        """len(dev)：组件数量。"""
        return len(self.components)

    def __getitem__(self, i):
        """dev[i]：按下标取组件。"""
        return self.components[i]

    def __str__(self):
        online = sum(1 for c in self.components if c.status == "online")
        return f"设备 {self.did} ({self.name}): {len(self)} 组件, {online} 在线"

    def to_dict(self):
        return {
            "did": self.did,
            "name": self.name,
            "components": [c.to_dict() for c in self.components],
        }

    @classmethod
    def from_dict(cls, data):
        dev = cls(data["did"], data["name"])
        for c in data["components"]:
            dev.add(Component.from_dict(c))
        return dev


class DeviceManager:
    """设备管理器：管理多个设备，支持批量上线、汇报与 JSON 持久化。"""

    def __init__(self):
        self.devices = []

    def find(self, did):
        """按设备编号查找设备，未找到返回 None。"""
        for dev in self.devices:
            if dev.did == did:
                return dev
        return None

    def add_device(self, did, name):
        """添加新设备，编号重复抛 ValueError。"""
        if self.find(did) is not None:
            raise ValueError(f"设备编号重复: {did}")
        self.devices.append(Device(did, name))

    def online_all(self):
        """全部设备的所有组件上线。"""
        for dev in self.devices:
            for comp in dev:
                comp.online()

    def save(self, path):
        """把全部设备序列化为 JSON 文件。"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump([d.to_dict() for d in self.devices], f,
                      ensure_ascii=False, indent=2)

    def load(self, path):
        """从 JSON 文件重建全部设备。"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.devices = [Device.from_dict(d) for d in data]

    def report(self):
        """打印全系统状态汇报。"""
        print("=== 设备管理系统 ===")
        for dev in self.devices:
            print(dev)
            for comp in dev:
                print(f"  {comp}")
        total = sum(len(dev) for dev in self.devices)
        online = sum(1 for dev in self.devices for c in dev if c.status == "online")
        print(f"总计: {len(self.devices)} 设备, {total} 组件, {online} 在线")


def main():
    """交互式命令入口。命令：show / add device/sensor/actuator / online / control / save / load / quit。"""
    mgr = DeviceManager()
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        parts = line.split()
        if not parts:
            continue
        cmd = parts[0]
        try:
            if cmd == "quit":
                break
            elif cmd == "show":
                mgr.report()
            elif cmd == "add":
                handle_add(mgr, parts)
            elif cmd == "online":
                mgr.online_all()
                print("全部组件已上线")
            elif cmd == "control":
                handle_control(mgr, parts)
            elif cmd == "save":
                mgr.save(DATA_FILE)
                print(f"已保存到 {os.path.basename(DATA_FILE)}")
            elif cmd == "load":
                if not os.path.exists(DATA_FILE):
                    print(f"错误: {os.path.basename(DATA_FILE)} 不存在，请先 save")
                else:
                    mgr.load(DATA_FILE)
                    print(f"已从 {os.path.basename(DATA_FILE)} 加载")
            else:
                print("未知命令。可用: show | add device/sensor/actuator | online | control | save | load | quit")
        except (ValueError, IndexError) as e:
            print(f"错误: {e}")


def handle_add(mgr, parts):
    """处理 add 子命令：add device <did> <名称> / add sensor <did> <名称> <单位> <值> / add actuator <did> <名称> <最大输出>。"""
    kind = parts[1]
    if kind == "device":
        mgr.add_device(parts[2], parts[3])
        print(f"已添加设备 {parts[2]}")
        return
    dev = mgr.find(parts[2])
    if dev is None:
        raise ValueError(f"设备不存在: {parts[2]}")
    pid = f"{dev.did}-{parts[3]}"
    if kind == "sensor":
        dev.add(Sensor(pid, parts[3], parts[4], float(parts[5])))
    elif kind == "actuator":
        dev.add(Actuator(pid, parts[3], float(parts[4])))
    else:
        raise ValueError(f"未知组件类型: {kind}")
    print(f"已向 {dev.did} 添加 {parts[3]}")


def handle_control(mgr, parts):
    """处理 control 命令：control <did> <组件索引> <百分比>。"""
    dev = mgr.find(parts[1])
    if dev is None:
        raise ValueError(f"设备不存在: {parts[1]}")
    comp = dev[int(parts[2])]
    if not isinstance(comp, Actuator):
        raise ValueError(f"组件 {comp.name} 不是执行器，无法控制")
    comp.control(float(parts[3]))
    print(f"{comp.name} 输出已设为 {comp.current:.0f}")


if __name__ == "__main__":
    main()
