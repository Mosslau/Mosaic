# exercises/sol-01-todo-api.py —— 练习 1 参考实现：Todo API（内存版 CRUD）
# 验证环境：Python 3.13.9；fastapi 0.139.1 / pydantic 2.12.4 / httpx 0.28.1
# 运行：python3 sol-01-todo-api.py（离线可跑，TestClient 验证，不起真实服务）
# 验证状态：已验证 —— 实测输出：POST 201 {"id": 1, "title": "学 FastAPI", "done": false}；
#           GET /todos 200（2 条）；GET /todos/1 200；GET /todos/999 404；PUT 200；DELETE 204；
#           title 空串 422；?done=true 过滤 200（仅完成项）
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

app = FastAPI(title="Todo API")


class Todo(BaseModel):
    title: str = Field(min_length=1, max_length=100)   # 校验：非空、限长
    done: bool = False


todos: dict[int, Todo] = {}          # 内存存储：重启即丢（练习要求说明这一点）


@app.post("/todos", status_code=201)
def create_todo(todo: Todo):
    todo_id = max(todos, default=0) + 1
    todos[todo_id] = todo
    return {"id": todo_id, **todo.model_dump()}


@app.get("/todos")
def list_todos(done: bool | None = None):
    result = [{"id": i, **t.model_dump()} for i, t in todos.items()]
    if done is not None:
        result = [t for t in result if t["done"] == done]
    return result


@app.get("/todos/{todo_id}")
def get_todo(todo_id: int):
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo 不存在")
    return {"id": todo_id, **todos[todo_id].model_dump()}


@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, todo: Todo):
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo 不存在")
    todos[todo_id] = todo
    return {"id": todo_id, **todo.model_dump()}


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    todos.pop(todo_id, None)          # 幂等：不存在也返回 204


def main() -> None:
    with TestClient(app) as client:
        r = client.post("/todos", json={"title": "学 FastAPI"})
        print("POST /todos        ->", r.status_code, r.json())
        client.post("/todos", json={"title": "复习 Pydantic", "done": True})

        r = client.get("/todos")
        print("GET /todos         ->", r.status_code, "条数:", len(r.json()))
        r = client.get("/todos?done=true")
        print("GET /todos?done=true ->", r.status_code, r.json())

        r = client.get("/todos/1")
        print("GET /todos/1       ->", r.status_code, r.json())
        r = client.get("/todos/999")
        print("GET /todos/999     ->", r.status_code, r.json())

        r = client.put("/todos/1", json={"title": "学 FastAPI", "done": True})
        print("PUT /todos/1       ->", r.status_code, r.json())

        r = client.post("/todos", json={"title": ""})          # Field(min_length=1) 触发 422
        print("POST 空 title      ->", r.status_code, r.json()["detail"][0]["type"])

        r = client.delete("/todos/2")
        print("DELETE /todos/2    ->", r.status_code, r.text)


if __name__ == "__main__":
    main()
