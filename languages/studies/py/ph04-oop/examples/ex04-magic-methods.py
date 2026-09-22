# examples/ex04-magic-methods.py —— 魔术方法：设备容器支持 len/索引/比较
# 来源：04-oop.md 第 6 章示例 4
# 验证环境：Python 3.13.12
# 运行：python3 ex04-magic-methods.py
# 验证状态：已验证

"""魔术方法：让 Device 像容器一样支持 len()、索引、成员判断与相等比较。"""


class SensorModule:
    """传感器模块：仅演示 __repr__ 的开发者表示。"""

    def __init__(self, sn, stype, unit):
        self.sn = sn
        self.stype = stype
        self.unit = unit

    def __repr__(self):
        return f"SensorModule({self.sn!r}, {self.stype!r})"


class Device:
    """设备容器：通过魔术方法融入语言协议。"""

    def __init__(self, did, modules=None):
        self.did = did
        self._ms = list(modules) if modules else []

    def add(self, m):
        """添加一个传感器模块。"""
        self._ms.append(m)

    def __len__(self):
        """len(dev)：模块数量。"""
        return len(self._ms)

    def __getitem__(self, i):
        """dev[i]：按下标取模块。"""
        return self._ms[i]

    def __contains__(self, sn):
        """sn in dev：按序列号判断是否包含。"""
        return any(m.sn == sn for m in self._ms)

    def __eq__(self, o):
        """dev == 其他：设备编号相同即相等。"""
        if not isinstance(o, Device):
            return NotImplemented
        return self.did == o.did

    def __hash__(self):
        """hash(dev)：与 __eq__ 保持一致，可放入 set/dict key。"""
        return hash(self.did)

    def __str__(self):
        """str(dev)/print(dev)：给用户看的简短表示。"""
        return f"Device({self.did}, {len(self)}模块)"


def main():
    """演示 len()、索引、in 与 ==。"""
    dev = Device("VCU-001")
    for sn, st in [("T-01", "温度"), ("V-02", "电压"), ("C-03", "电流")]:
        dev.add(SensorModule(sn, st, "N/A"))
    print(dev, f"len={len(dev)} [0]={dev[0]}")  # Device(VCU-001, 3模块) len=3 ...
    print("T-01" in dev, dev == Device("VCU-001"))  # True True


if __name__ == "__main__":
    main()
