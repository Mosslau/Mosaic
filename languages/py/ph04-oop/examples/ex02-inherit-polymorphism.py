# examples/ex02-inherit-polymorphism.py —— 继承链与多态：电机控制
# 来源：04-oop.md 第 6 章示例 2
# 验证环境：Python 3.13.12
# 运行：python3 ex02-inherit-polymorphism.py
# 验证状态：已验证

"""继承与多态：基类定义接口，子类差异化实现 control_signal。"""


class Motor:
    """电机基类：子类必须实现 control_signal。"""

    def __init__(self, name, max_rpm):
        self.name = name
        self.max_rpm = max_rpm

    def control_signal(self, pct):
        """计算控制信号（百分比 0~100），子类必须实现。"""
        raise NotImplementedError("子类必须实现")


class DCMotor(Motor):
    """直流电机：按百分比输出驱动电压与目标转速。"""

    def control_signal(self, pct):
        return f"{self.name} DC {(pct / 100) * 12:.1f}V, {int(self.max_rpm * pct / 100)}rpm"


class StepperMotor(Motor):
    """步进电机：按百分比输出脉冲频率。"""

    def __init__(self, name, max_rpm, steps=200):
        super().__init__(name, max_rpm)
        self.steps = steps

    def control_signal(self, pct):
        return f"{self.name} 步进 {pct / 100 * 1000:.0f}Hz {self.steps}步/转"


def main():
    """同一接口不同实现：多态分发到两个子类。"""
    motors = [DCMotor("驱动电机", 8000), StepperMotor("转向电机", 1000)]
    for m in motors:
        print(m.control_signal(50))
    print(isinstance(StepperMotor("x", 100), Motor))  # True


if __name__ == "__main__":
    main()
