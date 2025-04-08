from fastapi import FastAPI
from pydantic import BaseModel, EmailStr

app = FastAPI()


# 定义数据模型
class User(BaseModel):
    name: str
    email: str
    age: int = None  # 可选字段


@app.post("/users")
async def create_user(user: User):
    # 直接访问类型安全的user对象
    return {"user_id": 123, **user.dict()}


@app.get("/books")
async def read_books():
    return [{"title": "FastAPI入门", "author": "顶级专家"}]


@app.get("/books/{book_id}")
async def read_book(book_id: int):
    return {"book_id": book_id, "title": "FastAPI进阶", "author": "魔法大师"}


@app.get("/authors/{author_id}/books/{book_id}")
async def read_author_book(author_id: int, book_id: int):
    authors = {
        1: {"name": "顶级专家", "books": [1, 2]},
        2: {"name": "魔法大师", "books": [3]}
    }
    books = {
        1: {"title": "FastAPI入门", "author": "顶级专家"},
        2: {"title": "FastAPI进阶", "author": "顶级专家"},
        3: {"title": "FastAPI实战", "author": "魔法大师"}
    }
    author = authors.get(author_id)
    if not author:
        return {"error": "作者未找到"}
    if book_id not in author["books"]:
        return {"error": "书籍未找到"}
    return books.get(book_id)

@app.get("/products/{category}/{item_id}")
async def get_item(category: str, item_id: int):
    return {"category": category, "item_id": item_id, "stock": 100}


class UserCreate(BaseModel):
    username: str
    email: EmailStr  # 邮箱格式自动校验
    age: int = 18  # 默认值
    tags: list[str] = []  # 字符串列表


@app.post("/users")
async def create_user(user: UserCreate):
    # 直接访问已验证的数据
    return {"status": "success", "data": user.dict()}