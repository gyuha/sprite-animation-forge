import { describe, expect, it } from 'vitest'
import { gridGeometry, parseDerived, rectToBox, type Derived } from './grid'

// 2x2 sheet of 200x100: both row boundaries and the first row's column boundary have a gutter, the second row's column boundary does not.
const frame = (index: number, cell: [number, number, number, number], extra: Partial<Derived['frames'][number]> = {}) => ({
  index, cell, bbox: [cell[0] + 10, cell[1] + 5, cell[2] - 10, cell[3] - 5] as [number, number, number, number],
  anchor: [(cell[0] + cell[2]) / 2, cell[3] - 5] as [number, number], ...extra,
})
const derived: Derived = {
  row_boundaries: [0, 100, 200],
  col_boundaries: [[0, 100, 200], [0, 100, 200]],
  frames: [
    frame(0, [0, 0, 100, 100]), frame(1, [100, 0, 200, 100]),
    frame(2, [0, 100, 100, 200], { gutter_missing: true }), frame(3, [100, 100, 200, 200], { gutter_missing: true }),
  ],
}

describe('gridGeometry', () => {
  it('turns boundaries into lines in raw pixel space', () => {
    const g = gridGeometry(derived)
    expect([g.width, g.height]).toEqual([200, 200])
    const horizontal = g.lines.filter((l) => l.y1 === l.y2).map((l) => l.y1)
    expect(horizontal).toEqual([0, 100, 200])
    // column boundaries span only their own row
    expect(g.lines.filter((l) => l.x1 === 100).map((l) => [l.y1, l.y2])).toEqual([[0, 100], [100, 200]])
  })

  it('marks a boundary missing only when both neighbouring cells are flagged', () => {
    const g = gridGeometry(derived)
    const col = (row: number) => g.lines.find((l) => l.x1 === 100 && l.y1 === row * 100)!
    expect(col(0).missing).toBe(false)
    expect(col(1).missing).toBe(true)
    expect(g.lines.filter((l) => l.x1 === 0 || l.x1 === 200).every((l) => !l.missing)).toBe(true) // image edges
  })

  it('converts bbox and anchor of non-empty frames', () => {
    const g = gridGeometry({ ...derived, frames: [...derived.frames.slice(0, 3), { ...derived.frames[3], empty: true, bbox: null, anchor: null }] })
    expect(g.boxes[0]).toEqual({ index: 0, x: 10, y: 5, width: 80, height: 90 })
    expect(g.boxes).toHaveLength(3)
    expect(g.anchors[1]).toEqual({ index: 1, x: 150, y: 95 })
    expect(rectToBox([1, 2, 4, 8])).toEqual({ x: 1, y: 2, width: 3, height: 6 })
  })

  it('parseDerived rejects unusable data', () => {
    expect(parseDerived(undefined)).toBeNull()
    expect(parseDerived({ row_boundaries: [0], col_boundaries: [], frames: [] })).toBeNull()
    expect(parseDerived(derived as unknown as Record<string, unknown>)).not.toBeNull()
  })
})
