# examples/ex04-jinja2-template.py —— Jinja2 模板渲染（TestClient 离线验证）
# 验证环境：Python 3.13.9，fastapi 0.139.1 / jinja2 3.1.6 / httpx 0.28.1
# 运行：python3 ex04-jinja2-template.py（离线可跑，已验证，不起真实服务）
# 说明：服务端模板渲染入门——Jinja2Templates 把 HTML 模板 + 上下文渲染成页面，
#       展示变量插值、if/for 控制流与过滤器（主文档 3.11）。模板文件在同目录 templates/。
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
app = FastAPI(title="模板渲染 Demo")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# 内存「数据库」：vin -> (车型, 是否在线)；readings 为最近遥测（真实场景来自 SQLAlchemy，ph11 深入）
DEVICES = {
    "V001": {"model": "EV-A", "online": True},
    "V002": {"model": "EV-B", "online": False},
}
READINGS = {
    "V001": [
        {"time": "08:00:01", "speed": 59.44, "soc": 78.5},
        {"time": "08:00:31", "speed": 62.87, "soc": 78.1},
        {"time": "08:01:01", "speed": 55.02, "soc": 77.6},
    ],
    "V002": [],
}


@app.get("/device/{vin}")
def device_page(request: Request, vin: str):
    device = DEVICES.get(vin)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return templates.TemplateResponse(
        request,                       # Starlette 0.29+ 要求把 request 显式传入（主文档 3.11 的坑）
        "device.html",
        {"device": {"vin": vin, **device}, "readings": READINGS.get(vin, [])},
    )


def main() -> None:
    with TestClient(app) as client:
        r = client.get("/device/V001")
        print("GET /device/V001  ->", r.status_code, "| content-type:", r.headers["content-type"])
        text = r.text
        for expected in ("设备 V001", "EV-A", "在线 ✅", "59.4", "78", "共 3 条记录"):
            assert expected in text, f"缺少渲染片段: {expected}"
        print("  V001 渲染片段: 标题/车型/在线/速度保留 1 位小数/共 3 条记录 —— 全部命中")

        r2 = client.get("/device/V002")
        print("GET /device/V002  ->", r2.status_code,
              "| 离线分支:", "离线 ⛔" in r2.text, "| 空列表分支:", "暂无遥测记录" in r2.text)

        r3 = client.get("/device/UNKNOWN")
        print("GET /device/UNKNOWN ->", r3.status_code, r3.json())


if __name__ == "__main__":
    main()
