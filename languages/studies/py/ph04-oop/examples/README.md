# ph04 面向对象 OOP 阶段 示例

> 每个示例是主文档 `04-oop.md` 第 6 章对应示例的完整可运行版。验证环境：Python 3.13.12。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-class-var.py` | 类变量共享陷阱：`ClassName.attr` 修改 vs `self.attr` 遮蔽 | `python3 ex01-class-var.py` |
| `ex02-inherit-polymorphism.py` | 继承链与多态：`Motor` 基类 + 直流/步进电机子类 | `python3 ex02-inherit-polymorphism.py` |
| `ex03-property-component.py` | `@property` 部件 SOC 边界保护（只读 + 过充/过放校验） | `python3 ex03-property-component.py` |
| `ex04-magic-methods.py` | 魔术方法：设备容器支持 `len()`/索引/`in`/`==` | `python3 ex04-magic-methods.py` |
| `ex05-device-manager.py` | 设备管理系统：组合 + 多态 + 在线统计 | `python3 ex05-device-manager.py` |

全部已在本环境用 python3（3.13.12）运行验证，输出与文件内注释期望值一致（已验证）。
