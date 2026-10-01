"""Error format (docs/10 §4): ``{"error": {"code", "message", "detail"}}`` for every non-2xx response.

Notes on ambiguous spots
------------------------
* Core error codes differ from the doc's examples, so they are translated here (``_BY_CODE``). Unlisted codes
  keep their Core code; the status comes from the Core exit code: 1 -> 400, 3 -> 412 (code becomes
  ``precondition_failed``, the Core code moves to ``detail.reason``), 2 -> 502.
* Request-body validation errors keep status 422 but use this shape (code ``validation_error``,
  ``detail.errors`` = FastAPI's error list). Starlette HTTP errors (unknown route, 405) are normalized too.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sprite_forge.errors import EXIT_INVALID, EXIT_PRECONDITION, ForgeError

# Core code -> (HTTP status, API code)
_BY_CODE = {
    "no_character": (404, "not_found"),
    "no_attempt": (404, "not_found"),
    "unknown_action": (404, "not_found"),
    "exists": (409, "already_exists"),
    "busy": (409, "busy"),
    "mirrored_direction": (409, "mirrored_direction"),
    "invalid_params": (400, "invalid_param"),
}
_HTTP_CODES = {400: "invalid_param", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str = "", detail: dict | None = None):
        super().__init__(message or code)
        self.status, self.code, self.message, self.detail = status, code, message, detail or {}


def error_response(status: int, code: str, message: str = "", detail: dict | None = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "detail": detail or {}}}
    return JSONResponse(body, status_code=status)


def forge_to_api(exc: ForgeError) -> ApiError:
    detail = dict(exc.extra)
    if exc.code in _BY_CODE:
        status, code = _BY_CODE[exc.code]
    elif exc.exit_code == EXIT_PRECONDITION:
        status, code = 412, "precondition_failed"
        detail["reason"] = exc.code
    elif exc.exit_code == EXIT_INVALID:
        status, code = 400, exc.code
    else:
        status, code = 502, exc.code
    return ApiError(status, code, exc.message, detail)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError):
        return error_response(exc.status, exc.code, exc.message, exc.detail)

    @app.exception_handler(ForgeError)
    async def _forge(_: Request, exc: ForgeError):
        e = forge_to_api(exc)
        return error_response(e.status, e.code, e.message, e.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
        for err in errors:
            err.pop("input", None)
            err.pop("ctx", None)
        return error_response(422, "validation_error", "request validation failed", {"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return error_response(exc.status_code, _HTTP_CODES.get(exc.status_code, "http_error"), str(exc.detail))
