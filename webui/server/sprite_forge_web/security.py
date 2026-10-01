"""Host header allow-list (docs/10 §7, docs/01 §9): DNS-rebinding guard. Any port is accepted
(by default the server binds 127.0.0.1; the port is configurable). When the operator binds a non-loopback
address on purpose (``--host``), the guard is disabled: the Host header can no longer be predicted."""

from __future__ import annotations

import re

from starlette.types import ASGIApp, Receive, Scope, Send

from .errors import error_response

HOST_RE = re.compile(r"^(127\.0\.0\.1|localhost)(:\d{1,5})?$", re.I)


class HostGuardMiddleware:
    def __init__(self, app: ASGIApp, allow_any: bool = False):
        self.app = app
        self.allow_any = allow_any

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if not self.allow_any and scope["type"] in ("http", "websocket"):
            host = dict(scope["headers"]).get(b"host", b"").decode("latin-1")
            if not HOST_RE.match(host):
                if scope["type"] == "http":
                    resp = error_response(403, "forbidden_host", "Host header must be 127.0.0.1 or localhost",
                                          {"host": host})
                    return await resp(scope, receive, send)
                return await send({"type": "websocket.close", "code": 1008})
        await self.app(scope, receive, send)
