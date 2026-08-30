# examples/ex05-device-manager.py —— 车联网设备管理系统（组合 + 多态）
# 来源：04-oop.md 第 6 章示例 5
# 验证环境：Python 3.13.12
# 运行：python3 ex05-device-manager.py
# 验证状态：已验证

"""设备管理系统：Component 基类 + Sensor/Actuator 子类多态，DeviceManager 组合管理。"""


class Component:
    """组件基类：统一设备编号、名称与在线状态。"""

    def __init__(self, pid, name):
        self.pid = pid
        self.name = name
        self._status = "offline"

    @property
    def status(self):
        """组件在线状态。"""
        return self._status

    def online(self):
        """上线。"""
        self._status = "online"

    def __repr__(self):
        return f"{type(self).__name__}({self.pid!r}, {self.name!r})"


class Sensor(Component):
    """传感器：能读取当前数值。"""

    def __init__(self, pid, name, unit, value=0.0):
        super().__init__(pid, name)
        self.unit = unit
        self.value = value

    def read(self):
        """读取当前测量值。"""
        return self.value

    def __str__(self):
        return f"[{self.status}] {self.name}: {self.value}{self.unit}"


class Actuator(Component):
    """执行器：能按百分比控制输出。"""

    def __init__(self, pid, name, max_out):
        super().__init__(pid, name)
        self.max_out = max_out
        self._cur = 0

    def control(self, pct):
        """按百分比 0~100 设置当前输出。"""
        self._cur = min(pct, 100) * self.max_out / 100.0

    def __str__(self):
        return f"[{self.status}] {self.name}: {self._cur:.0f}/{self.max_out}"


class DeviceManager:
    """设备管理器：组合组件列表，统一上下线与汇报。"""

    def __init__(self, name):
        self.name = name
        self.comps = []

    def add(self, c):
        """添加一个组件。"""
        self.comps.append(c)

    def online_all(self):
        """全部组件上线。"""
        for c in self.comps:
            c.online()

    @property
    def online_n(self):
        """在线组件数量。"""
        return sum(1 for c in self.comps if c.status == "online")

    def report(self):
        """打印设备状态汇报。"""
        print(f"=== {self.name} ===")
        for c in self.comps:
            print(c)
        print(f"在线: {self.online_n}/{len(self.comps)}")


def main():
    """演示组合 + 多态 + 在线统计。"""
    mgr = DeviceManager("前电机控制器")
    mgr.add(Sensor("T-001", "绕组温度", "°C", 32.5))
    mgr.add(Sensor("V-001", "母线电压", "V", 400.0))
    mgr.add(Actuator("M-001", "驱动电机", 5000))
    mgr.online_all()
    mgr.comps[2].control(60)
    mgr.report()


if __name__ == "__main__":
    main()
