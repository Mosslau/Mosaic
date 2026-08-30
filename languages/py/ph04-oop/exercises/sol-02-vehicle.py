# exercises/sol-02-vehicle.py —— 车辆类：Vehicle + ElectricVehicle 继承与多态（参考实现）
# 来源：exercises/README.md 练习 2
# 验证环境：Python 3.13.12
# 运行：python3 sol-02-vehicle.py
# 验证状态：已验证

"""车辆类：基类 Vehicle + 子类 ElectricVehicle，super() 链 + 多态 describe。"""


class Vehicle:
    """普通车辆：品牌 + 速度。"""

    def __init__(self, brand, speed=0):
        self.brand = brand
        self.speed = speed

    def accelerate(self, delta):
        """加速 delta km/h（不允许为负）。"""
        self.speed = max(0, self.speed + delta)

    def describe(self):
        """返回车辆描述。"""
        return f"{self.brand} 速度 {self.speed}km/h"


class ElectricVehicle(Vehicle):
    """电动汽车：额外携带电池容量。"""

    RANGE_PER_KWH = 6  # 每 kWh 续航 6 km

    def __init__(self, brand, battery_cap, speed=0):
        super().__init__(brand, speed)  # 必须调用父类 __init__
        self.battery_cap = battery_cap
        self._soc = 100.0

    def charge(self, amount):
        """充电 amount 个百分点（0~100 边界保护）。"""
        self._soc = min(100.0, self._soc + amount)

    def range(self):
        """满电续航里程（km）。"""
        return self.battery_cap * self.RANGE_PER_KWH

    def describe(self):
        """重写父类方法：先取父类描述再追加电池信息。"""
        base = super().describe()
        return f"{base}, 电池 {self.battery_cap}kWh 续航 {self.range()}km"


def show_vehicle(v):
    """多态入口：同一函数对不同子类对象输出各自 describe。"""
    print(v.describe())


def main():
    """演示 super() 链、重写与多态。"""
    tesla = ElectricVehicle("Tesla", 70)
    print(f"续航: {tesla.range()}km")  # 420
    tesla.accelerate(50)
    show_vehicle(tesla)  # Tesla 速度 50km/h, 电池 70kWh 续航 420km

    bmw = Vehicle("BMW")
    bmw.accelerate(30)
    show_vehicle(bmw)  # BMW 速度 30km/h

    print(isinstance(tesla, Vehicle))  # True


if __name__ == "__main__":
    main()
