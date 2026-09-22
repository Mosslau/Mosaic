# 来源：languages/py/ph02-data-structure/exercises/README.md 练习 2「dict 做通讯录」
# 说明：参考实现——通讯录的添加、get 安全查询、修改、删除与遍历。
# 验证环境：Python 3.13.12（macOS arm64）
# 运行命令：python3 sol-02-contacts.py
# 验证状态：已验证

"""练习 2 参考实现：用 dict 做通讯录。"""


def add_contact(contacts: dict, name: str, phone: str, city: str) -> None:
    """添加（或覆盖）一个联系人。"""
    contacts[name] = {"phone": phone, "city": city}


def find_contact(contacts: dict, name: str) -> None:
    """按姓名查询并打印；查不到时提示而不是抛 KeyError。"""
    info = contacts.get(name)
    if info is None:
        print(f"未找到 {name}")
    else:
        print(f"{name}: {info['phone']}, {info['city']}")


def main() -> None:
    """演示通讯录的增删改查与遍历。"""
    contacts = {}

    add_contact(contacts, "Alice", "13800138000", "Shanghai")
    add_contact(contacts, "Bob", "13900139000", "Beijing")

    # 查询 Bob
    find_contact(contacts, "Bob")

    # 修改 Alice 的电话
    contacts["Alice"]["phone"] = "13600136000"
    find_contact(contacts, "Alice")

    # 删除 Bob
    del contacts["Bob"]
    find_contact(contacts, "Bob")

    # 列出全部联系人
    print("全部联系人:")
    for name, info in contacts.items():
        print(f"  {name}: {info['phone']}, {info['city']}")


if __name__ == "__main__":
    main()
