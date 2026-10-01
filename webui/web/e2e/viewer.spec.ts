import type { Page } from '@playwright/test'
import { expect, test, type Server } from './fixtures'

/** Seeds a character, generates every unit with auto-accept and waits for the batch. Returns the accepted/mirrored unit names. */
async function generated(server: Server, id: string, bundle: string, view?: 'side' | 'topdown') {
  await server.seedCharacter(id, bundle, view)
  const { job } = await server.api(`/api/characters/${id}/generate-all`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ auto_accept: true }),
  })
  expect((await server.waitJob(job.id)).state).toBe('succeeded')
  const { status } = await server.api(`/api/characters/${id}`)
  return (status.units as { unit: string; state: string; accepted_attempt: string | null }[])
    .filter((u) => u.state === 'accepted' || (u.state === 'mirrored' && u.accepted_attempt))
    .map((u) => u.unit)
}

const tiles = (page: Page) => page.locator('canvas[data-testid^="viewer-tile-"]')

/** every canvas is painted, holds opaque pixels and (being multi-frame) changes data-frame within a few seconds */
async function expectAnimated(page: Page, units: string[]) {
  await expect(tiles(page)).toHaveCount(units.length)
  await expect(page.locator('canvas[data-testid^="viewer-tile-"][data-painted="true"]')).toHaveCount(units.length)
  const result = await page.evaluate(async () => {
    const out: Record<string, { opaque: boolean; frames: number; count: number }> = {}
    const canvases = [...document.querySelectorAll<HTMLCanvasElement>('canvas[data-testid^="viewer-tile-"]')]
    const seen = new Map<string, Set<string>>(canvases.map((c) => [c.dataset.unit!, new Set<string>()]))
    const until = performance.now() + 2500
    while (performance.now() < until) {
      for (const c of canvases) seen.get(c.dataset.unit!)!.add(c.dataset.frame!)
      await new Promise((r) => setTimeout(r, 30))
    }
    for (const c of canvases) {
      const data = c.getContext('2d')!.getImageData(0, 0, c.width, c.height).data
      let opaque = false
      for (let i = 3; i < data.length && !opaque; i += 4) opaque = data[i] > 0
      out[c.dataset.unit!] = { opaque, frames: seen.get(c.dataset.unit!)!.size, count: Number(c.dataset.frameCount) }
    }
    return out
  })
  expect(Object.keys(result).sort()).toEqual([...units].sort())
  for (const [unit, r] of Object.entries(result)) {
    expect(r.opaque, `${unit} has opaque pixels`).toBe(true)
    if (r.count > 1) expect(r.frames, `${unit} data-frame changes`).toBeGreaterThan(1)
  }
}

test('viewer plays every accepted unit of a side-view character', async ({ page, server }) => {
  await server.start()
  const units = await generated(server, 'hero', 'npc')
  expect(units.length).toBe(2)
  await page.goto('/c/hero/view')
  await expect(page.getByTestId('viewer-page')).toBeVisible()
  await expectAnimated(page, units)

  await page.getByTestId('viewer-play-all').click()
  await expect(page.getByTestId('viewer-grid')).toHaveAttribute('data-playing', 'false')
  const frame = await page.getByTestId('viewer-tile-walk').getAttribute('data-frame')
  await page.waitForTimeout(600)
  await expect(page.getByTestId('viewer-tile-walk')).toHaveAttribute('data-frame', frame!)

  await page.getByTestId('viewer-tile-walk').click()
  await expect(page.getByTestId('viewer-zoom-dialog')).toBeVisible()
})

test('viewer lays out a topdown character with the mirrored left tile playable', async ({ page, server }) => {
  await server.start()
  const units = await generated(server, 'tdhero', 'idle', 'topdown')
  expect(units.sort()).toEqual(['idle/down', 'idle/left', 'idle/right', 'idle/up'])
  await page.goto('/c/tdhero/view')
  await expectAnimated(page, units)
  await expect(page.locator('[data-testid^="viewer-tile-missing-"]')).toHaveCount(0)
})

test('the viewer is reachable from the dashboard, the export page and the studio', async ({ page, server }) => {
  await server.start()
  await generated(server, 'hero', 'npc')

  await page.goto('/')
  await page.getByTestId('character-view-hero').click()
  await expect(page).toHaveURL(/\/c\/hero\/view$/)
  await expect(page.getByTestId('viewer-page')).toBeVisible()

  await page.goto('/c/hero/export')
  await page.getByTestId('export-view-link').click()
  await expect(page).toHaveURL(/\/c\/hero\/view$/)

  await page.goto('/c/hero/studio/idle')
  await page.getByTestId('studio-view-link').click()
  await expect(page).toHaveURL(/\/c\/hero\/view$/)
  await expect(tiles(page).first()).toBeVisible()
})
