# exercises/sol-03-sensor.py —— 传感器类：Sensor 基类 + 多态 read()（参考实现）
# 来源：exercises/README.md 练习 3
# 验证环境：Python 3.13.12
# 运行：python3 sol-03-sensor.py
# 验证状态：已验证

"""传感器类：基类定义 read() 接口，子类多态实现；类变量统计实例数量。"""


class Sensor:
    """传感器基类：子类必须实现 read()。"""

    count = 0  # 类变量：统计已创建的全部传感器数量

    def __init__(self, name, unit):
        self.name = name
        self.unit = unit
        Sensor.count += 1  # 通过类名修改类变量

    def read(self):
        """读取测量值，子类必须实现。"""
        raise NotImplementedError("子类必须实现 read()")

    def __str__(self):
        return f"[{type(self).__name__}] {self.name}: {self.read()}{self.unit}"


class TemperatureSensor(Sensor):
    """温度传感器。"""

    def __init__(self, name, value):
        super().__init__(name, "°C")
        self.value = value

    def read(self):
        return self.value


class VoltageSensor(Sensor):
    """电压传感器。"""

    def __init__(self, name, value):
        super().__init__(name, "V")
        self.value = value

    def read(self):
        return self.value


def collect_all(sensors):
    """多态入口：遍历调用 read() 并打印，不关心具体子类。"""
    for s in sensors:
        print(s)


def main():
    """演示多态采集与类变量统计。"""
    collect_all([TemperatureSensor("车外温度", 25.5),
                 VoltageSensor("母线电压", 12.8)])
    # [TemperatureSensor] 车外温度: 25.5°C
    # [VoltageSensor] 母线电压: 12.8V

    extra = TemperatureSensor("电机温度", 88.0)
    print(f"传感器总数: {Sensor.count}")  # 3


if __name__ == "__main__":
    main()
