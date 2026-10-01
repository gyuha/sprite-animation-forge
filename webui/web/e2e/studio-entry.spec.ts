import type { Page } from '@playwright/test'
import { expect, test, type Server } from './fixtures'

// A character whose every unit is accepted used to have no way back into the studio: its dashboard card goes
// straight to export. These three entry points must reach a working studio for such a character.
test('a fully accepted character can be opened in the studio from the dashboard and the export page', async ({ page, server }) => {
  await server.start()
  await server.seedCharacter('hero', 'npc')
  const { job } = await server.api('/api/characters/hero/generate-all', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ auto_accept: true }),
  })
  expect((await server.waitJob(job.id)).state).toBe('succeeded')
  const { status } = await server.api('/api/characters/hero')
  const units = status.units as { state: string }[]
  expect(units.length).toBeGreaterThan(0)
  expect(units.every((u) => u.state === 'accepted' || u.state === 'mirrored')).toBe(true)

  // dashboard: the card still leads to export, the extra button opens the studio
  await page.goto('/')
  await expect(page.getByTestId('character-card-hero')).toHaveAttribute('href', '/c/hero/export')
  await page.getByTestId('character-studio-hero').click()
  await expect(page.getByTestId('studio-page')).toBeVisible()
  await expect(page).toHaveURL(/\/c\/hero\/studio\//)
  // the studio is really usable for an accepted unit: its accepted attempt is shown and regenerating is enabled
  await expect(page.locator('[data-testid^="accepted-badge-"]').first()).toBeVisible()
  await expect(page.getByTestId('generate-button')).toBeEnabled()

  // export page: the tab bar leads back to the studio, although nothing is missing
  await page.goto('/c/hero/export')
  await expect(page.getByTestId('export-missing-alert')).toHaveCount(0)
  await page.getByTestId('tab-studio').click()
  await expect(page.getByTestId('studio-page')).toBeVisible()
})

const batch = (server: Server, id: string, actions: string[]) =>
  server.api(`/api/characters/${id}/generate-all`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ auto_accept: true, actions }),
  }).then(({ job }) => server.waitJob(job.id))

const expectSelected = async (page: Page, tab: 'studio' | 'view' | 'export') => {
  for (const t of ['studio', 'view', 'export']) await expect(page.getByTestId(`tab-${t}`)).toHaveAttribute('aria-selected', String(t === tab))
}

test('a fully adopted character moves between studio, viewer and export through the tabs', async ({ page, server }) => {
  await server.start()
  await server.seedCharacter('hero', 'npc')
  expect((await batch(server, 'hero', ['idle', 'walk'])).state).toBe('succeeded')

  await page.goto('/c/hero/studio/idle')
  await expect(page.getByTestId('studio-page')).toBeVisible()
  await expectSelected(page, 'studio')
  await page.getByTestId('tab-view').click()
  await expect(page.getByTestId('viewer-page')).toBeVisible()
  await expectSelected(page, 'view')
  await expect(page.getByTestId('tab-export')).toHaveAttribute('data-disabled', 'false')
  await page.getByTestId('tab-export').click()
  await expect(page.getByTestId('export-run')).toBeVisible()
  await expectSelected(page, 'export')
})

test('the export tab stays disabled until the last unit is adopted', async ({ page, server }) => {
  await server.start()
  await server.seedCharacter('hero', 'npc')
  expect((await batch(server, 'hero', ['idle'])).state).toBe('succeeded')

  await page.goto('/c/hero/studio/idle')
  const exportTab = page.getByTestId('tab-export')
  await expect(exportTab).toHaveAttribute('data-disabled', 'true')
  await exportTab.click({ force: true })
  await expect(page).toHaveURL(/\/c\/hero\/studio\/idle$/)
  await expect(page.getByTestId('studio-page')).toBeVisible()

  expect((await batch(server, 'hero', ['walk'])).state).toBe('succeeded')
  await page.reload()
  await expect(exportTab).toHaveAttribute('data-disabled', 'false')
  await exportTab.click()
  await expect(page).toHaveURL(/\/c\/hero\/export$/)
  await expect(page.getByTestId('export-run')).toBeVisible()
})
