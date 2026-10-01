import { execFileSync } from 'node:child_process'
import type { Locator, Page } from '@playwright/test'
import { REFERENCE_PNG, REPO_ROOT } from './paths'
import { expect, test } from './fixtures'

/**
 * "조작" (user action) = one deliberate step of the user: a file upload, a selection (radio/select) or a click.
 * Waiting, reading and navigating that the app does by itself are not actions. Every action of the (a) scenario goes
 * through this counter, so a fifth action would show up in the total.
 */
function userActions(page: Page) {
  const log: string[] = []
  return {
    log,
    upload: (input: Locator, file: string) => { log.push('upload'); return input.setInputFiles(file) },
    select: (option: Locator) => { log.push('select'); return option.click() },
    click: (target: Locator) => { log.push('click'); return target.click() },
    download: async (target: Locator) => {
      const [download] = await Promise.all([page.waitForEvent('download'), target.click()])
      log.push('download')
      return download
    },
  }
}

const zipNames = (zipPath: string): string[] =>
  JSON.parse(execFileSync('uv', ['run', 'python', '-c', 'import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; print(json.dumps(z.namelist()))', zipPath],
    { cwd: REPO_ROOT, encoding: 'utf8' }))

test('home loads the dashboard', async ({ page, server }) => {
  await server.start()
  await page.goto('/')
  await expect(page.getByTestId('new-character-button')).toBeVisible()
  await expect(page.getByTestId('dashboard-empty')).toBeVisible()
})

test('(a) upload, bundle, generate all and ZIP download take exactly 4 user actions', async ({ page, server }, testInfo) => {
  await server.start()
  const act = userActions(page)
  await page.goto('/new')

  await act.upload(page.getByTestId('dropzone-input'), REFERENCE_PNG) // 1: picking the image creates the character
  await expect(page).toHaveURL(/\/c\/[^/]+\/plan$/)
  await act.select(page.getByTestId('bundle-npc')) // 2: npc = idle (2x2) + walk (2x3)
  await expect(page.getByTestId('action-check-walk')).toBeVisible()
  await act.click(page.getByTestId('generate-all')) // 3: auto-accept is on by default; the batch ends on the export page by itself
  await expect(page.getByTestId('export-zip')).toBeEnabled({ timeout: 60_000 })
  const download = await act.download(page.getByTestId('export-zip')) // 4

  expect(act.log).toEqual(['upload', 'select', 'click', 'download'])
  expect(act.log).toHaveLength(4)
  const zipPath = testInfo.outputPath('character.zip')
  await download.saveAs(zipPath)
  const names = zipNames(zipPath)
  expect(names.some((n) => n.endsWith('.png') && n.includes('atlas'))).toBe(true)
  expect(names.some((n) => n.endsWith('.json') && n.includes('atlas'))).toBe(true)
  expect(names.some((n) => n.endsWith('animations.json'))).toBe(true)
})

test('(b) a reprocess slider change refreshes the preview within 2 seconds', async ({ page, server }, testInfo) => {
  await server.start()
  await server.seedCharacter('hero', 'npc')
  const { job } = await server.api('/api/characters/hero/generate-all', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ auto_accept: true }),
  })
  expect((await server.waitJob(job.id)).state).toBe('succeeded')

  await page.goto('/c/hero/studio/idle')
  const canvas = page.getByTestId('preview-canvas')
  await expect(canvas).toHaveAttribute('data-version', /.+/)
  const before = await canvas.getAttribute('data-version')
  await page.getByTestId('reprocess-toggle').click()
  await page.getByTestId('reprocess-margin_top').getByRole('slider').focus()

  const started = Date.now()
  for (let i = 0; i < 10; i++) await page.keyboard.press('ArrowRight') // a burst of changes, debounced into one reprocess
  await expect(canvas).not.toHaveAttribute('data-version', before!, { timeout: 2000 })
  const elapsed = Date.now() - started
  testInfo.annotations.push({ type: 'preview-refresh-ms', description: String(elapsed) })
  console.log(`preview refresh: ${elapsed} ms`)
  expect(elapsed).toBeLessThan(2000)
})

test('(c) a server killed mid-generation shows 중단됨 after the restart and can regenerate', async ({ page, server }) => {
  await server.start()
  await server.seedCharacter('hero', 'npc')
  await server.kill()
  await server.start('hang') // every Codex call hangs

  await page.goto('/c/hero/studio/idle')
  await page.getByTestId('generate-button').click()
  await expect(page.locator('[data-testid^="job-"]:not([data-testid^="job-failed"])').first()).toBeVisible()
  await server.kill()
  await server.start('success')

  await page.reload()
  await expect(page.getByTestId('interrupted-badge-001')).toBeVisible()
  await expect(page.getByTestId('interrupted-notice')).toBeVisible()
  await page.getByTestId('regenerate-button').click()
  await expect(page.getByTestId('attempt-002')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('attempt-qc-002')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('interrupted-badge-002')).toHaveCount(0)
  const { attempts } = await server.api('/api/characters/hero/actions/idle/attempts')
  expect(attempts.map((a: { attempt: string; generation_status: string }) => [a.attempt, a.generation_status])).toEqual([
    ['001', 'interrupted'], ['002', 'succeeded'],
  ])
})
