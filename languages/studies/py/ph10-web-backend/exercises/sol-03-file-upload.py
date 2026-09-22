# exercises/sol-03-file-upload.py —— 练习 3 参考实现：文件上传（UploadFile + 校验 + 随机名落盘）
# 验证环境：Python 3.13.9；fastapi 0.139.1 / python-multipart / httpx 0.28.1
# 运行：python3 sol-03-file-upload.py（离线可跑，TestClient 验证，不起真实服务）
# 验证状态：已验证 —— 实测输出：.txt 上传 200（saved_as 为 uuid 随机名）；.exe 400；
#           超 5MB 413；缺 file 字段 422；上传目录为临时目录、无仓库残留
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.testclient import TestClient

UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="ph10-sol03-uploads-"))   # 上传目录写临时目录
ALLOWED_SUFFIXES = {".txt", ".png", ".jpg", ".jpeg", ".bin"}
MAX_SIZE = 5 * 1024 * 1024          # 5MB

app = FastAPI(title="Upload API")


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {suffix}")
    content = await file.read()                       # UploadFile 是异步接口
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 5MB")
    dest = UPLOAD_DIR / f"{uuid4().hex}{suffix}"      # 服务端生成文件名：防覆盖/路径穿越
    dest.write_bytes(content)
    return {"filename": file.filename, "saved_as": dest.name, "size": len(content)}


def main() -> None:
    print("上传目录:", UPLOAD_DIR)
    with TestClient(app) as client:
        r = client.post("/upload", files={"file": ("notes.txt", b"hello world", "text/plain")})
        print("上传 notes.txt       ->", r.status_code, r.json())

        r = client.post("/upload", files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
        print("上传 evil.exe       ->", r.status_code, r.json())

        big = b"x" * (MAX_SIZE + 1)                    # 6MB 字节串，直接构造
        r = client.post("/upload", files={"file": ("big.bin", big, "application/octet-stream")})
        print("上传超 5MB          ->", r.status_code, r.json())

        r = client.post("/upload")                     # 缺 file 字段
        print("缺 file 字段        ->", r.status_code, r.json()["detail"][0]["type"])

    files = list(UPLOAD_DIR.iterdir())
    print("落盘文件数:", len(files), "| 文件名样例:", files[0].name if files else None)


if __name__ == "__main__":
    main()
