# exercises/sol-02-auth-jwt.py —— 练习 2 参考实现：登录注册（密码哈希 + JWT + Depends 鉴权）
# 验证环境：Python 3.13.9；fastapi 0.139.1 / pyjwt 2.10.1 / httpx 0.28.1
# 运行：python3 sol-02-auth-jwt.py（离线可跑，TestClient 验证，不起真实服务）
# 验证状态：已验证 —— 实测输出：注册 201；重复注册 409；登录 200 返回 access_token；
#           带 token 调 /auth/me 200；无 token 401；篡改 token 401；密码错误 401；
#           注册表存储的是盐+摘要哈希（非明文）
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient
from pydantic import BaseModel

SECRET_KEY = "dev-secret-change-me-in-production-32bytes"   # 生产必须从环境变量读取（主文档 3.6）
ALGORITHM = "HS256"
TOKEN_TTL = timedelta(hours=24)

app = FastAPI(title="Auth API")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
users: dict[str, str] = {}                 # username -> 加盐哈希（演示用内存，生产用数据库）


class AuthBody(BaseModel):
    username: str
    password: str


def hash_password(password: str) -> str:                 # 绝不存明文
    salt = secrets.token_hex(8)                          # 每用户随机盐
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100_000
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$")
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100_000
    ).hex() == digest


def create_token(username: str) -> str:
    return jwt.encode(
        {"sub": username, "exp": datetime.now(timezone.utc) + TOKEN_TTL},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


@app.post("/auth/register", status_code=201)
def register(body: AuthBody):
    if body.username in users:
        raise HTTPException(status_code=409, detail="用户名已存在")
    users[body.username] = hash_password(body.password)
    return {"username": body.username}


@app.post("/auth/login")
def login(body: AuthBody):
    stored = users.get(body.username)
    if not stored or not verify_password(body.password, stored):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"access_token": create_token(body.username), "token_type": "bearer"}


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"]
    except jwt.PyJWTError:                          # 过期/被篡改统一在这抛 401
        raise HTTPException(status_code=401, detail="无效或过期的 token")


@app.get("/auth/me")
def me(username: str = Depends(get_current_user)):
    return {"username": username}


def main() -> None:
    with TestClient(app) as client:
        r = client.post("/auth/register", json={"username": "alice", "password": "s3cret"})
        print("注册 alice          ->", r.status_code, r.json())
        r = client.post("/auth/register", json={"username": "alice", "password": "x"})
        print("重复注册            ->", r.status_code, r.json())

        print("存储的密码值        ->", users["alice"][:32] + "...（salt$digest 哈希，非明文）")

        r = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
        print("密码错误登录        ->", r.status_code, r.json())

        r = client.post("/auth/login", json={"username": "alice", "password": "s3cret"})
        token = r.json()["access_token"]
        print("正确登录            ->", r.status_code, "token 前缀:", token[:20] + "...")

        r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        print("带 token 调 /auth/me ->", r.status_code, r.json())

        r = client.get("/auth/me")
        print("无 token             ->", r.status_code, r.json())

        r = client.get("/auth/me", headers={"Authorization": "Bearer " + token[:-2] + "xx"})
        print("篡改 token           ->", r.status_code, r.json())


if __name__ == "__main__":
    main()
