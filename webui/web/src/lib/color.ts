/** Hex colour helpers + the background key colour rule of the backend (pipeline/chroma.py resolve_key_color). */

export const HEX_RE = /^#[0-9A-Fa-f]{6}$/
export const KEY_MAGENTA = '#FF00FF'
export const KEY_GREEN = '#00FF00'
export const KEY_CONFLICT_DISTANCE = 120

export const isHexColor = (s: string) => HEX_RE.test(s)

const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))

export function colorDistance(a: string, b: string) {
  const [x, y] = [rgb(a), rgb(b)]
  return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2])
}

export interface KeyColorResult {
  key: typeof KEY_MAGENTA | typeof KEY_GREEN
  /** none: magenta is fine; magenta: magenta conflicts, green is used; both: neither is free, magenta is kept */
  conflict: 'none' | 'magenta' | 'both'
}

/** Invalid hex strings are ignored (the server only reads valid ones too). */
export function resolveKeyColor(colors: string[]): KeyColorResult {
  const valid = colors.filter(isHexColor)
  const free = (key: string) => valid.every((c) => colorDistance(c, key) >= KEY_CONFLICT_DISTANCE)
  if (free(KEY_MAGENTA)) return { key: KEY_MAGENTA, conflict: 'none' }
  if (free(KEY_GREEN)) return { key: KEY_GREEN, conflict: 'magenta' }
  return { key: KEY_MAGENTA, conflict: 'both' }
}
