from fastapi.testclient import TestClient
from fastapi_test import app  # 假设你的FastAPI应用保存在main.py文件中
import pytest

client = TestClient(app)

# def test_create_user():
#     response = client.post("/users", json={"name": "John Doe", "email": "john.doe@example.com", "age": 30})
#     assert response.status_code == 200
#     print(response.json())
#     assert response.json() == {"user_id": 123, "name": "John Doe", "email": "john.doe@example.com", "age": 30}

# def test_read_books():
#     response = client.get("/books")
#     assert response.status_code == 200
#     assert response.json() == [{"title": "FastAPI入门", "author": "顶级专家"}]
#
#
# def test_read_book1():
#     # 测试正常情况下的书籍读取
#     response = client.get("/books/2")
#     assert response.status_code == 200
#     assert response.json() == {"book_id": 1, "title": "FastAPI进阶", "author": "魔法大师"}
#



def test_read_author_book():
    # 测试存在的作者和书籍
    response = client.get("/authors/1/books/1")
    assert response.status_code == 200
    assert response.json() == {"title": "FastAPI入门", "author": "顶级专家"}

    # 测试存在的作者但书籍不存在
    response = client.get("/authors/1/books/99")
    assert response.status_code == 200
    assert response.json() == {"error": "书籍未找到"}

    # 测试不存在的作者
    response = client.get("/authors/99/books/1")
    assert response.status_code == 200
    assert response.json() == {"error": "作者未找到"}

    # 测试存在的作者和另一本存在的书籍
    response = client.get("/authors/1/books/2")
    assert response.status_code == 200
    assert response.json() == {"title": "FastAPI进阶", "author": "顶级专家"}

    # 测试另一存在的作者和其书籍
    response = client.get("/authors/2/books/3")
    assert response.status_code == 200
    assert response.json() == {"title": "FastAPI实战", "author": "魔法大师"}

    # 测试存在的作者但书籍ID为0（通常书籍ID应为正整数）
    response = client.get("/authors/1/books/0")
    assert response.status_code == 200
    assert response.json() == {"error": "书籍未找到"}

    # 测试负数作者ID
    response = client.get("/authors/-1/books/1")
    assert response.status_code == 200
    assert response.json() == {"error": "作者未找到"}

    # 测试负数书籍ID
    response = client.get("/authors/1/books/-1")
    assert response.status_code == 200
    assert response.json() == {"error": "书籍未找到"}

def test_get_item():
    # 测试正常情况
    response = client.get("/products/electronics/1")
    assert response.status_code == 200
    assert response.json() == {"category": "electronics", "item_id": 1, "stock": 100}

# def test_create_user_missing_age():
#     response = client.post("/users", json={"name": "Jane Doe", "email": "jane.doe@example.com"})
#     assert response.status_code == 200
#     assert response.json() == {"user_id": 123, "name": "Jane Doe", "email": "jane.doe@example.com", "age": None}
#
# def test_create_user_invalid_email():
#     response = client.post("/users", json={"name": "John Doe", "email": "invalid_email", "age": 30})
#     assert response.status_code == 422
#
# def test_create_user_missing_name():
#     response = client.post("/users", json={"email": "john.doe@example.com", "age": 30})
#     assert response.status_code == 422
#
# def test_create_user_missing_email():
#     response = client.post("/users", json={"name": "John Doe", "age": 30})
#     assert response.status_code == 422
#
# def test_create_user_negative_age():
#     response = client.post("/users", json={"name": "John Doe", "email": "john.doe@example.com", "age": -1})
#     assert response.status_code == 422
# #
# def test_create_user_age_as_string():
#     response = client.post("/users", json={"name": "sgg", "email": "john.doe@example.com", "age": "30"})
#     print((response.json()))
#     assert response.status_code == 422


