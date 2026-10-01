/** fetch wrapper: every failure (server error JSON, non-JSON body, network) becomes an ApiError. */

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: unknown

  constructor(status: number, code: string, message: string, detail: unknown = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null
}

/** Server shape is `{"error": {code, message, detail}}`; FastAPI 422 is `{"detail": [...]}`. */
function fromBody(status: number, statusText: string, body: unknown): ApiError {
  if (isRecord(body) && isRecord(body.error) && typeof body.error.code === 'string') {
    const { code, message, detail } = body.error
    return new ApiError(status, code, typeof message === 'string' ? message : statusText, detail ?? {})
  }
  if (isRecord(body) && 'detail' in body) {
    return new ApiError(status, status === 422 ? 'validation_error' : `http_${status}`, statusText || '요청 오류', body.detail)
  }
  return new ApiError(status, `http_${status}`, statusText || `HTTP ${status}`)
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch (e) {
    throw new ApiError(0, 'network_error', '서버에 연결할 수 없습니다', { cause: String(e) })
  }
  const text = await res.text()
  let body: unknown
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    if (res.ok) throw new ApiError(res.status, 'invalid_response', '서버 응답이 JSON이 아닙니다')
    throw new ApiError(res.status, `http_${res.status}`, res.statusText || `HTTP ${res.status}`, { body: text.slice(0, 200) })
  }
  if (!res.ok) throw fromBody(res.status, res.statusText, body)
  return body as T
}

export function apiJson<T>(path: string, method: 'POST' | 'PUT', body?: unknown): Promise<T> {
  return api<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}
