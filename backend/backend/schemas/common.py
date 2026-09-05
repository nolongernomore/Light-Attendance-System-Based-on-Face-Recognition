from typing import Any


def ok(data: Any = None, message: str = "操作成功"):
    return {
        "success": True,
        "code": "OK",
        "message": message,
        "data": data,
    }


def fail(code: str, message: str, data: Any = None):
    return {
        "success": False,
        "code": code,
        "message": message,
        "data": data,
    }

