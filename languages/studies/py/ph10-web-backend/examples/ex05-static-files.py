# examples/ex05-static-files.py —— 静态文件与 FileResponse（TestClient 离线验证）
# 验证环境：Python 3.13.9，fastapi 0.139.1 / starlette 0.49.3 / httpx 0.28.1
# 运行：python3 ex05-static-files.py（离线可跑，已验证，不起真实服务）
# 说明：StaticFiles 把磁盘目录原样挂到 URL 前缀（CSS/JS/图片等资源服务）；
#       FileResponse 按需返回单个文件（如动态生成的 CSV 报表）。
#       生成的下载文件写入系统临时目录（tempfile），运行后仓库无残留。
import csv
import io
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

STATIC_DIR = Path(__file__).resolve().parent / "static"
app = FastAPI(title="静态文件 Demo")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")  # 目录 → URL 前缀


@app.get("/download/report")
def download_report():
    """动态生成一份 CSV 报表并作为附件返回（产物写临时目录，防仓库污染）。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["device_id", "avg_speed", "avg_soc"])
    writer.writerow(["V001", 59.44, 78.5])
    writer.writerow(["V002", 62.87, 76.1])

    out = Path(tempfile.mkdtemp(prefix="ph10-ex05-")) / "report.csv"
    out.write_text(buf.getvalue(), encoding="utf-8")
    return FileResponse(out, filename="report.csv", media_type="text/csv")


def main() -> None:
    with TestClient(app) as client:
        r = client.get("/static/style.css")
        print("GET /static/style.css ->", r.status_code,
              "| content-type:", r.headers["content-type"], "| 大小:", len(r.content), "字节")

        r2 = client.get("/static/missing.css")
        print("GET /static/missing.css ->", r2.status_code)          # 目录里没有 → 404

        r3 = client.get("/download/report")
        print("GET /download/report ->", r3.status_code,
              "| content-type:", r3.headers["content-type"],
              "| Content-Disposition:", r3.headers.get("content-disposition"))
        print("  响应体:\n" + r3.text.rstrip())


if __name__ == "__main__":
    main()
