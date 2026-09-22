# examples/ex03-property-battery.py —— @property 电池 SOC 边界保护
# 来源：04-oop.md 第 6 章示例 3
# 验证环境：Python 3.13.12
# 运行：python3 ex03-property-battery.py
# 验证状态：已验证

"""@property 封装：只读属性 + 可计算属性，charge/discharge 做边界校验。"""


class Battery:
    """电池模型：SOC 只读，可用电量按 SOC 实时计算。"""

    def __init__(self, cap):
        self.cap = cap
        self._soc = 100.0  # 初始满电

    @property
    def soc(self):
        """当前剩余电量百分比（只读）。"""
        return self._soc

    @property
    def available(self):
        """当前可用电量（kWh），由容量与 SOC 计算。"""
        return self.cap * self._soc / 100.0

    def charge(self, a):
        """充电 a 个百分点，超过 100% 报过充错误。"""
        n = self._soc + a
        if n > 100:
            raise ValueError(f"过充: 当前{self._soc}%")
        self._soc = n

    def discharge(self, a):
        """放电 a 个百分点，低于 0% 报过放错误。"""
        n = self._soc - a
        if n < 0:
            raise ValueError(f"过放: 当前{self._soc}%")
        self._soc = n


def main():
    """演示放电、充电与越界校验。"""
    b = Battery(70.0)
    print(f"SOC={b.soc}% 可用={b.available:.1f}kWh")  # SOC=100.0% 可用=70.0kWh
    b.discharge(30)
    print(f"SOC={b.soc}%")  # SOC=70.0%
    b.charge(15)
    print(f"SOC={b.soc}%")  # SOC=85.0%
    try:
        b.discharge(200)
    except ValueError as e:
        print(f"失败: {e}")


if __name__ == "__main__":
    main()
