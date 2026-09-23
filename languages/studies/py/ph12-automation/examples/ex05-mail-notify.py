#!/usr/bin/env python3
# examples/ex05-mail-notify.py —— 邮件通知：smtplib + 进程内最小 SMTP 调试服务器
# 验证环境：Python 3.13.9（stdlib，无第三方依赖；smtpd 模块自 3.12 起已移除，故用
#           socketserver 手写一个「只收不发」的最小调试服务器——顺便看清 SMTP 是文本协议）
# 运行：python3 ex05-mail-notify.py（离线可跑，已验证；CSV 附件与邮件都在内存/临时目录）
# 说明：对应主文档 3.6/4.4。生成一个设备状态 CSV 报表 → 组装 EmailMessage（文本 + 附件）
#       → smtplib.SMTP 发送到本地调试服务器 → 服务器把收到的邮件原样存进内存列表并打印。
import csv
import socketserver
import tempfile
import threading
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path

import smtplib


class SinkHandler(socketserver.StreamRequestHandler):
    """最小 SMTP 调试服务器：逐行读命令、按 SMTP 状态机应答，收到的邮件存进 server.messages。"""

    def handle(self) -> None:
        self._respond(b"220 ph12-sink ESMTP")
        while True:
            line = self.rfile.readline()
            if not line:
                break
            cmd = line.decode("utf-8", "replace").strip().upper()
            if cmd.startswith(("HELO", "EHLO")):
                self._respond(b"250 ph12-sink")
            elif cmd.startswith("MAIL"):
                self._respond(b"250 OK")
            elif cmd.startswith("RCPT"):
                self._respond(b"250 OK")
            elif cmd.startswith("DATA"):
                self._respond(b"354 End data with <CR><LF>.<CR><LF>")
                msg = bytearray()
                while True:
                    line_body = self.rfile.readline()
                    if not line_body or line_body.strip() == b".":  # 正文以单独一行 "." 结束
                        break
                    msg += line_body
                self.server.messages.append(bytes(msg))
                self._respond(b"250 OK: queued")
            elif cmd.startswith("QUIT"):
                self._respond(b"221 Bye")
                break
            else:
                self._respond(b"250 OK")

    def _respond(self, data: bytes) -> None:
        self.wfile.write(data + b"\r\n")
        self.wfile.flush()  # wfile 是缓冲流，必须 flush 客户端才能收到应答


def build_report_csv() -> Path:
    work = Path(tempfile.mkdtemp(prefix="ph12-ex05-"))
    report = work / "device-report.csv"
    with report.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["设备", "状态", "累计运行量(km)"])
        writer.writerow(["EV-001", "正常", 368.3])
        writer.writerow(["EV-002", "正常", 314.0])
        writer.writerow(["EV-003", "告警", 226.2])
    return report


def send_report(host: str, port: int, report: Path) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = "ops@example.com"
    msg["To"] = "admin@example.com"
    msg["Subject"] = "设备状态日报"
    msg["Date"] = formatdate(localtime=True)
    msg.set_content("今日设备状态汇总见附件，请查收。")
    msg.add_attachment(
        report.read_bytes(), maintype="text", subtype="csv", filename=report.name
    )
    with smtplib.SMTP(host, port, timeout=5) as smtp:  # with 结束自动 quit()
        smtp.send_message(msg)
    return msg


def main() -> None:
    server = socketserver.TCPServer(("127.0.0.1", 0), SinkHandler)
    server.messages = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        report = build_report_csv()
        msg = send_report("127.0.0.1", port, report)
        print("SMTP 调试服务器 -> 127.0.0.1:", port)
        print("已发送 -> 收件人:", msg["To"], "| 主题:", msg["Subject"])
        print("服务器收到邮件 ->", len(server.messages), "封")
        received = server.messages[0].decode("utf-8", "replace")
        lines = received.splitlines()
        print("邮件头 From ->", next(ln for ln in lines if ln.startswith("From")))
        print("附件数 ->", received.count("Content-Type: text/csv"))
        print("附件文件名 ->", next(ln for ln in lines if "filename" in ln))
    finally:
        server.shutdown()
        server.server_close()
        print("SMTP 调试服务器已关闭")


if __name__ == "__main__":
    main()
