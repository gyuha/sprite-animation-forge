/** Pure geometry for GridOverlay: process.json `derived` (raw sheet pixels) -> SVG shapes in the same pixel space. */

type Rect = [number, number, number, number]
export interface DerivedFrame { index: number; cell: Rect; empty?: boolean; gutter_missing?: boolean; bbox: Rect | null; anchor: [number, number] | null }
export interface Derived { row_boundaries: number[]; col_boundaries: number[][]; frames: DerivedFrame[] }

export interface GridLine { x1: number; y1: number; x2: number; y2: number; missing: boolean }
export interface Box { x: number; y: number; width: number; height: number }
export interface GridGeometry {
  width: number
  height: number
  lines: GridLine[]
  /** bbox per non-empty frame, as x/y/width/height */
  boxes: (Box & { index: number })[]
  anchors: { index: number; x: number; y: number }[]
}

export const rectToBox = ([x0, y0, x1, y1]: Rect): Box => ({ x: x0, y: y0, width: x1 - x0, height: y1 - y0 })

/** `derived` of AttemptResult / process.json, or null when the shape is not usable. */
export function parseDerived(d: Record<string, unknown> | undefined | null): Derived | null {
  if (!d || !Array.isArray(d.row_boundaries) || !Array.isArray(d.col_boundaries) || !Array.isArray(d.frames)) return null
  if (d.row_boundaries.length < 2 || d.col_boundaries.length === 0) return null
  return d as unknown as Derived
}

/**
 * Row boundaries are horizontal lines across the sheet, column boundaries vertical segments inside their row. A boundary
 * is "missing" (no gutter found) when the cells next to it are flagged `gutter_missing` (docs/05 4): both neighbours for
 * a column boundary, every cell of the two rows for a row boundary. Outer boundaries are the image edge and never missing.
 */
export function gridGeometry(d: Derived): GridGeometry {
  const rows = d.row_boundaries
  const height = rows[rows.length - 1]
  const width = d.col_boundaries[0][d.col_boundaries[0].length - 1]
  const cellsInRow = (r: number) => d.frames.filter((f) => f.cell[1] === rows[r])
  const lines: GridLine[] = []

  rows.forEach((y, r) => {
    const inner = r > 0 && r < rows.length - 1
    const around = inner ? [...cellsInRow(r - 1), ...cellsInRow(r)] : []
    lines.push({ x1: 0, y1: y, x2: width, y2: y, missing: around.length > 0 && around.every((f) => f.gutter_missing) })
  })
  d.col_boundaries.forEach((cols, r) => {
    const cells = cellsInRow(r)
    cols.forEach((x, k) => {
      const inner = k > 0 && k < cols.length - 1
      const next = inner ? [cells[k - 1], cells[k]] : []
      lines.push({ x1: x, y1: rows[r], x2: x, y2: rows[r + 1], missing: next.length > 0 && next.every((f) => f?.gutter_missing) })
    })
  })

  const filled = d.frames.filter((f) => !f.empty)
  return {
    width,
    height,
    lines,
    boxes: filled.filter((f) => f.bbox).map((f) => ({ index: f.index, ...rectToBox(f.bbox as Rect) })),
    anchors: filled.filter((f) => f.anchor).map((f) => ({ index: f.index, x: (f.anchor as number[])[0], y: (f.anchor as number[])[1] })),
  }
}
