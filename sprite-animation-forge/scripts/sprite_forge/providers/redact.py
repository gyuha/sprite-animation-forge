"""What a video provider's error text may show (docs/13): secrets masked, the provider's own code named.

``redact(text, secret)``      one string with key-shaped values, ``Bearer`` tokens, the request's own credential and the
                              query string of a URL (where a signature lives) replaced by ``[redacted]``.
``masked(body, secret)``      the same for every string inside a parsed JSON body; applied BEFORE the body is put on one
                              line or cut, so no cut can leave half of a key and no quote written here can hide one.
``refusal_line(reason, status, body, secret, policy)``
                              ``<reason> (HTTP n)[ code=<code>]: <body>`` - the shape callers read the status and code from.
``provider_code(body)``       ``error.code`` (object form) or a top-level ``code``, only when it looks like an identifier.
"""

from __future__ import annotations

import json
import re

REDACTED = "[redacted]"
CONTENT_POLICY = "refused by the provider's content policy"
MAX_BODY_CHARS = 400
_CODE = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
# a key = known prefix + a long run of key characters; a letter/digit before the prefix makes it part of a word,
# but `_` or `-` before it does not (`api_key_xai-...`). A value the provider already masked carries `*`.
_KEY = re.compile(r"(?<![A-Za-z0-9])(sk|xai)-([A-Za-z0-9_*-]{16,})")
_BEARER = re.compile(r"(?i)(?<![A-Za-z0-9])(bearer\s+)[A-Za-z0-9._~+/=-]{16,}")
_URL_QUERY = re.compile(r"(?i)(https?://[^\s?#\"'<>\\]+)\?[^\s#\"'<>\\]*")


def redact(text: str, secret: str | None = None) -> str:
    if secret and len(secret) >= 8:
        text = text.replace(secret, REDACTED)  # an echo of the credential is a key whatever its shape
    text = _KEY.sub(lambda m: m.group(0) if "*" in m.group(2) else f"{m.group(1)}-{REDACTED}", text)
    text = _BEARER.sub(lambda m: m.group(1) + REDACTED, text)
    return _URL_QUERY.sub(lambda m: f"{m.group(1)}?{REDACTED}", text)


def masked(body, secret: str | None = None):
    if isinstance(body, str):
        return redact(body, secret)
    if isinstance(body, dict):
        return {masked(k, secret): masked(v, secret) for k, v in body.items()}
    if isinstance(body, list):
        return [masked(v, secret) for v in body]
    return body


def parse_body(data: bytes):
    """JSON when it is JSON, else the text as received (``None`` for an empty body)."""
    text = data.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return text


def provider_code(body) -> str | None:
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    code = error.get("code") if isinstance(error, dict) else body.get("code")
    return code if isinstance(code, str) and _CODE.fullmatch(code) else None


def said(body, secret: str | None = None) -> str:
    """``: <body>`` for the end of a line (masked first, then one line, then cut), or ``""`` for an empty body."""
    body = masked(body, secret)
    if body in (None, "", {}, []):
        return ""
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    text = " ".join(text.split())
    if len(text) > MAX_BODY_CHARS:
        text = text[:MAX_BODY_CHARS] + "..."
    return f": {text}"


def refusal_line(reason: str, status: int, body, secret: str | None = None, policy: bool = False) -> str:
    code = provider_code(body)
    return f"{CONTENT_POLICY if policy else reason} (HTTP {status})" + (f" code={code}" if code else "") + said(body, secret)
