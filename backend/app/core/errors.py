from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}


def request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if value:
        return value
    return f"req_{uuid.uuid4().hex[:12]}"


def error_body(code: str, message: str, req_id: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": req_id}}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, request_id(request)),
        headers=exc.headers,
    )