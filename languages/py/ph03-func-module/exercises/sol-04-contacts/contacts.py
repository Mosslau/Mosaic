# exercises/sol-04-contacts/contacts.py —— 通讯录数据操作模块参考实现
# 验证环境：Python 3.13.12
# 运行：在本目录下执行 python3 main.py --demo 或交互运行
# 已验证：本环境运行输出与期望一致

"""通讯录数据操作函数。联系人用 dict 存储：name -> phone。"""

def add_contact(contacts: dict[str, str], name: str, phone: str) -> None:
    """添加或更新联系人。"""
    contacts[name] = phone

def find_contact(contacts: dict[str, str], name: str) -> str | None:
    """按姓名查找电话，未找到返回 None。"""
    return contacts.get(name)

def delete_contact(contacts: dict[str, str], name: str) -> bool:
    """删除联系人，存在并删除返回 True，否则返回 False。"""
    if name in contacts:
        del contacts[name]
        return True
    return False

def list_contacts(contacts: dict[str, str]) -> list[tuple[str, str]]:
    """返回按姓名排序的 (name, phone) 列表。"""
    return sorted(contacts.items())
