# exercises/sol-04-config.py —— 配置管理类：@property 校验 + dict 导出导入（参考实现）
# 来源：exercises/README.md 练习 4
# 验证环境：Python 3.13.12
# 运行：python3 sol-04-config.py
# 验证状态：已验证

"""配置管理类：api_key 只读，timeout 用 property setter 校验，支持 dict 导出导入。"""


class Config:
    """配置对象：不可改的 api_key + 带范围校验的 timeout。"""

    TIMEOUT_MIN = 5
    TIMEOUT_MAX = 300

    def __init__(self, api_key, timeout=30):
        if not isinstance(api_key, str) or len(api_key) < 8:
            raise ValueError("api_key 必须是不短于 8 字符的字符串")
        self.__api_key = api_key  # name mangling：防子类意外覆盖
        self._timeout = timeout  # 直接写私有字段，绕过 setter 校验
        self.timeout = timeout  # 走 setter 做一次范围校验

    @property
    def api_key(self):
        """只读：只提供 getter，不提供 setter。"""
        return self.__api_key

    @property
    def timeout(self):
        """读取超时秒数。"""
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        """赋值时校验范围，非法值抛 ValueError。"""
        if not self.TIMEOUT_MIN <= value <= self.TIMEOUT_MAX:
            raise ValueError(
                f"timeout 必须在 {self.TIMEOUT_MIN}~{self.TIMEOUT_MAX} 之间: {value}"
            )
        self._timeout = value

    def to_dict(self):
        """导出为普通 dict，便于 JSON 序列化。"""
        return {"api_key": self.api_key, "timeout": self.timeout}

    @classmethod
    def from_dict(cls, data):
        """从 dict 重建配置对象（工厂方法）。"""
        return cls(data["api_key"], data["timeout"])

    def __eq__(self, other):
        """api_key 相同即相等。"""
        if not isinstance(other, Config):
            return NotImplemented
        return self.api_key == other.api_key

    def __hash__(self):
        return hash(self.api_key)

    def __repr__(self):
        return f"Config(api_key={self.api_key!r}, timeout={self.timeout})"


def main():
    """演示只读校验、setter 校验与 dict 往返。"""
    cfg = Config("sk-abc12345", timeout=30)
    print(cfg)

    cfg.timeout = 10  # setter 校验通过
    print(f"timeout 改为 10 后: {cfg.timeout}")

    try:
        cfg.timeout = 400  # 超出上限
    except ValueError as e:
        print(f"越界被拦: {e}")

    try:
        cfg.api_key = "hacked"
    except AttributeError as e:
        print(f"api_key 只读被拦: {e}")

    restored = Config.from_dict(cfg.to_dict())
    print(f"dict 往返相等: {restored == cfg}")  # True


if __name__ == "__main__":
    main()
