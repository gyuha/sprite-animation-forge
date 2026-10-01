"""Host header allow-list (docs/10 §7, docs/01 §9): DNS-rebinding guard. Any port is accepted
(the server only ever binds 127.0.0.1; the port is configurable)."""

from __future__ import annotations

import re

from starlette.types import ASGIApp, Receive, Scope, Send

from .errors import error_response

HOST_RE = re.compile(r"^(127\.0\.0\.1|localhost)(:\d{1,5})?$", re.I)


class HostGuardMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] in ("http", "websocket"):
            host = dict(scope["headers"]).get(b"host", b"").decode("latin-1")
            if not HOST_RE.match(host):
                if scope["type"] == "http":
                    resp = error_response(403, "forbidden_host", "Host header must be 127.0.0.1 or localhost",
                                          {"host": host})
                    return await resp(scope, receive, send)
                return await send({"type": "websocket.close", "code": 1008})
        await self.app(scope, receive, send)
