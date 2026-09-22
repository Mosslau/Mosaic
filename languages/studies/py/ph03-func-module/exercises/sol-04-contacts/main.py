# exercises/sol-04-contacts/main.py —— 通讯录 CLI 入口脚本参考实现
# 验证环境：Python 3.13.12
# 运行：在本目录下执行 python3 main.py --demo，或 python3 main.py 进入交互
# 已验证：本环境运行输出与期望一致

"""通讯录命令行入口。"""
import sys

import contacts

def print_usage() -> None:
    """打印用法说明。"""
    print("可用命令:")
    print("  add <姓名> <电话>    添加/更新联系人")
    print("  find <姓名>          查找联系人")
    print("  delete <姓名>        删除联系人")
    print("  list                 列出全部联系人")
    print("  quit                 退出")

def demo() -> None:
    """演示数据操作模块的完整流程（非交互）。"""
    book: dict[str, str] = {}
    contacts.add_contact(book, "Alice", "123")
    contacts.add_contact(book, "Bob", "456")
    print("list:", contacts.list_contacts(book))             # [('Alice', '123'), ('Bob', '456')]
    print("find Bob:", contacts.find_contact(book, "Bob"))   # 456
    print("delete Alice:", contacts.delete_contact(book, "Alice"))  # True
    print("find Alice:", contacts.find_contact(book, "Alice"))      # None

def run_loop() -> None:
    """交互式命令循环。"""
    book: dict[str, str] = {}
    print("通讯录 CLI（输入 help 查看命令，quit 退出）")
    while True:
        raw = input("> ").strip()
        if not raw:
            continue
        parts = raw.split()
        cmd = parts[0]
        if cmd == "quit":
            break
        if cmd == "help":
            print_usage()
        elif cmd == "add" and len(parts) == 3:
            contacts.add_contact(book, parts[1], parts[2])
            print(f"已添加: {parts[1]} -> {parts[2]}")
        elif cmd == "find" and len(parts) == 2:
            phone = contacts.find_contact(book, parts[1])
            print(phone if phone is not None else "未找到")
        elif cmd == "delete" and len(parts) == 2:
            removed = contacts.delete_contact(book, parts[1])
            print("已删除" if removed else "未找到")
        elif cmd == "list":
            if not book:
                print("通讯录为空")
            for name, phone in contacts.list_contacts(book):
                print(f"{name}: {phone}")
        else:
            print_usage()

if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    else:
        run_loop()
